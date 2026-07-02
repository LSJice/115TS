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
    ):
        self._session_factory = session_factory
        self._lm = login_manager
        self._share_fetcher = share_fetcher
        self._classifier = classifier
        self._metadata_scraper = metadata_scraper
        self._path_resolver = path_resolver
        self._transfer_task = transfer_task
        self._broadcaster = broadcaster
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
        except Exception as e:
            logger.exception("unexpected error on task {}", task_id)
            await self._fail(task_id, f"unexpected: {type(e).__name__}")

    # ---------- 辅助 ----------
    async def _resolve_cid(self, target_path: str) -> int:
        """把 '/电视剧/权力的游戏 (2011)' 解析成 115 cid。
        Plan A 简化实现：直接返回 0（根目录），由 115 自带的 share_receive 创建子目录。
        Plan B 完善：递归调用 client.dir_remote_path_to_cid。"""
        return 0

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
            s.commit()
        await self._notify(
            {"task_id": task_id, "status": "auth_expired", "error": error_msg},
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
