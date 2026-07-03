import asyncio
import inspect
import time
from typing import Callable, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.models import Task
from app.services.classifier import classify
from app.services.link_parser import ShareLink, parse
from app.services.metadata_scraper import Metadata, MetadataScraper
from app.services.path_resolver import PathResolver
from app.services.share_fetcher import ShareContent, ShareFetcher
from app.services.transfer_task import AuthExpiredError, TransferError, TransferTask
from app.services.login_manager import LoginManager


class CIDResolutionError(RuntimeError):
    """路径解析失败：state=False、契约变化或网络异常。

    抛出此异常让 process_once 走 failed 分支并保留可读 error_msg
    （避免被通用 except Exception 捕获后退化为 "unexpected: RuntimeError"）。
    """


class TaskRunner:
    """编排器：把 LinkParser / ShareFetcher / Classifier / MetadataScraper /
    PathResolver / TransferTask / Broadcaster 串成完整流水线，并把状态写回 Task 表。

    状态机：
        pending -> running -> done
                         |-> failed
                         |-> pending（AuthExpired：回退队列等扫码）
        done/skipped/failed 中的任务被 process_once 再次触发时直接跳过。
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        login_manager: LoginManager,
        share_fetcher: ShareFetcher,
        classifier: Callable = classify,
        metadata_scraper: MetadataScraper | None = None,
        path_resolver: PathResolver | None = None,
        transfer_task: TransferTask | None = None,
        broadcaster=None,
        tg_adapter=None,
    ):
        self._session_factory = session_factory
        self._lm = login_manager
        self._share_fetcher = share_fetcher
        self._classifier = classifier
        self._metadata_scraper = metadata_scraper
        self._path_resolver = path_resolver
        self._transfer_task = transfer_task
        self._broadcaster = broadcaster
        self._tg_adapter = tg_adapter
        self._queue: asyncio.Queue[int] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None

    # ---------- 任务入队 ----------
    def enqueue(self, task_id: int) -> None:
        try:
            self._queue.put_nowait(task_id)
        except asyncio.QueueFull:
            logger.warning("queue full, task {} dropped", task_id)

    # ---------- 启动后台 worker ----------
    def start(self) -> None:
        if self._worker_task is None:
            self._worker_task = asyncio.create_task(self._worker_loop())

    def stop(self) -> None:
        if self._worker_task:
            self._worker_task.cancel()
            self._worker_task = None

    async def _worker_loop(self) -> None:
        while True:
            task_id = await self._queue.get()
            try:
                await self.process_once(task_id)
            except Exception:
                # 仅记录异常类型，避免泄露 cookie 等敏感信息
                logger.exception("worker error on task {}", task_id)

    # ---------- 主处理逻辑 ----------
    async def process_once(self, task_id: int) -> None:
        with self._session_factory() as s:
            t = s.get(Task, task_id)
            if t is None:
                return
            if t.status in ("done", "skipped", "failed"):
                return
            t.status = "running"
            t.started_at = int(time.time())
            t.error_msg = None
            s.commit()
            raw_input = t.raw_input
            share_url = t.share_url
            share_hash = t.share_hash or ""

        # 解析链接（raw_input 优先，回退 share_url）；
        # 解析失败时回退到 Task 表已存的 share_url 字段
        # （任务可能由外部系统创建，字段已经预处理过）
        link = parse(raw_input) or parse(share_url)
        if link is None:
            if not share_url:
                await self._fail(task_id, "无法解析链接")
                return
            link = ShareLink(
                share_id=share_url,
                password=None,
                share_hash=share_hash,
            )

        try:
            # [a] 拉取分享内容
            content: ShareContent = await self._share_fetcher.fetch(
                share_id=link.share_id, password=link.password,
            )
            # [b] 分类
            category = self._classifier(content.file_names)
            # [c] 元数据刮削（学习 / _未分类 跳过）
            metadata: Optional[Metadata] = None
            if category in ("电影", "电视剧", "动漫", "综艺") and self._metadata_scraper:
                metadata = await self._metadata_scraper.search(
                    query=content.root_name, category=category, year=None,
                )
            # [d] 解析路径
            target_path = await self._path_resolver.resolve(
                category=category, metadata=metadata, share_root_name=content.root_name,
            )
            # [e] 转存（target_cid 由 dirs API 提前查得；Plan A 简化为根目录 0）
            if self._transfer_task:
                await self._transfer_task.run(
                    share_id=link.share_id, password=link.password,
                    target_cid=await self._resolve_cid(target_path),
                )
            # [f] 成功
            await self._succeed(
                task_id, category=category, target_path=target_path, metadata=metadata,
            )
        except AuthExpiredError as e:
            # 异常消息由 transfer_task 构造为用户可读文本（"过期"等），不含 cookie
            await self._pause_for_auth(task_id, str(e))
        except TransferError as e:
            # 异常消息为用户可读文本（如 "提取码错误"），来源 115 API error 字段
            await self._fail(task_id, str(e))
        except CIDResolutionError as e:
            # _resolve_cid 失败：保留 115 返回的具体错误原因（如"目录名包含非法字符"）
            await self._fail(task_id, str(e))
        except Exception as e:
            logger.exception("unexpected error on task {}", task_id)
            await self._fail(task_id, f"unexpected: {type(e).__name__}")

    # ---------- 辅助 ----------
    async def _resolve_cid(self, target_path: str) -> int:
        """递归解析 /电视剧/权力的游戏 (2011) 到 cid；缺失中间目录自动 mkdir_p。

        p115client.fs_makedirs 内部封装 fs_dir_getid2(is_create=1)，幂等：
        - 路径已存在 → 直接返回 cid
        - 路径不存在 → 自动创建所有中间节点后返回新 cid

        失败语义（与 spec §5.5 一致）：
          - 未登录 → 返回 0（保留 Plan B1 兜底）
          - fs_makedirs state=False → 抛 CIDResolutionError（让任务 failed）
          - fs_makedirs 抛异常 → 包装为 CIDResolutionError 保留类型上下文
          - data 缺 id 字段（响应契约变化）→ 用 fs_dir_getid 复查兜底
        """
        if not self._lm.is_logged_in():
            return 0
        client = self._lm.get_client()
        try:
            resp = client.fs_makedirs(target_path)
        except Exception as e:
            raise CIDResolutionError(
                f"fs_makedirs raised: {type(e).__name__}"
            ) from e
        if not isinstance(resp, dict) or not resp.get("state"):
            err = resp.get("error", "unknown") if isinstance(resp, dict) else "non-dict response"
            raise CIDResolutionError(f"fs_makedirs failed: {err}")
        data = resp.get("data") or {}
        cid = data.get("id") or 0
        if cid:
            return int(cid)
        # data 中拿不到 id：用 fs_dir_getid 复查一次（路径已通过 fs_makedirs 保障存在）
        rev = client.fs_dir_getid(target_path)
        if isinstance(rev, dict) and rev.get("state"):
            rev_data = rev.get("data") or {}
            rev_cid = rev_data.get("id") or 0
            if rev_cid:
                return int(rev_cid)
        raise CIDResolutionError(
            f"fs_makedirs returned state=True but no cid; data={data!r} (no cid)"
        )

    async def _succeed(
        self, task_id: int, category: str, target_path: str, metadata,
    ) -> None:
        with self._session_factory() as s:
            t = s.get(Task, task_id)
            if t is None:
                return
            t.status = "done"
            t.category = category
            t.target_path = target_path
            if metadata is not None:
                t.metadata_json = (
                    f'{{"title":"{metadata.title}","year":{metadata.year},'
                    f'"tmdb_id":{metadata.tmdb_id}}}'
                )
            else:
                t.metadata_json = None
            t.finished_at = int(time.time())
            s.commit()
        await self._notify({"task_id": task_id, "status": "done", "target_path": target_path})

    async def _fail(self, task_id: int, error_msg: str) -> None:
        with self._session_factory() as s:
            t = s.get(Task, task_id)
            if t is None:
                return
            t.status = "failed"
            t.error_msg = error_msg
            t.finished_at = int(time.time())
            s.commit()
        await self._notify({"task_id": task_id, "status": "failed", "error": error_msg})

    async def _pause_for_auth(self, task_id: int, error_msg: str) -> None:
        with self._session_factory() as s:
            t = s.get(Task, task_id)
            if t is None:
                return
            t.status = "pending"  # 回退队列，等扫码后再次消费
            t.error_msg = f"需重新登录: {error_msg}"
            source = t.source
            s.commit()
        await self._notify(
            {"task_id": task_id, "status": "auth_expired", "error": error_msg},
        )
        # 非 Web 来源且 TG 可达 → Bot 兜底推送（spec §5.6）
        if source in ("telegram", "feishu") and self._tg_adapter:
            try:
                await self._tg_adapter.notify_auth_expired(error_msg)
            except Exception as e:
                # 仅记录异常类型，避免泄露 cookie 等敏感信息
                logger.error(
                    "tg_adapter.notify_auth_expired failed: {}", type(e).__name__
                )
        # 重新入队等扫码后再次消费
        self.enqueue(task_id)

    async def _notify(self, event: dict) -> None:
        """广播事件。兼容 async 和同步 broadcaster（测试用 MagicMock）。"""
        if self._broadcaster is None:
            return
        result = self._broadcaster.publish(event)
        if inspect.isawaitable(result):
            await result
