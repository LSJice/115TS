# Plan B2 实施设计 — Telegram 适配器 / 飞书适配器 / _resolve_cid 完善

- **创建日期**：2026-07-03
- **作者**：用户 + Claude（brainstorming）
- **状态**：已通过 brainstorming，待编写实施计划
- **前置依赖**：Plan B1（Web UI）已完成并合并

---

## 1. 背景与目标

### 1.1 问题陈述

Plan B1 完成了 Web UI 手动粘贴链路与基础转存流水线，但仍有三块未交付：

1. **Telegram Bot 入站**：用户在 TG 群/私聊中收到 115 链接时，需手工复制粘贴到 Web UI
2. **飞书共享 Excel 轮询**：用户共享的飞书 Bitable 表是新链接的主要来源，目前完全人工
3. **`_resolve_cid` 占位实现**：`task_runner.py:146-150` 直接 `return 0`，导致 path_resolver 算出的 `/电视剧/权力的游戏 (2011)` 完全失效，所有转存落到 115 根目录

### 1.2 目标

- **G1**：Telegram Bot 收到白名单消息后，自动入队任务（含多链接支持）
- **G2**：APScheduler 每 N 分钟轮询飞书 Bitable，全量拉取 + hash 去重入队
- **G3**：`_resolve_cid` 递归解析路径到 cid；缺失目录自动 mkdir_p
- **G4**：Cookie 过期时，TG/飞书来源任务由 Bot 兜底推送提醒到 admin user_id
- **G5**：`POST /api/config/feishu/test` 实际调用飞书 API 拉一行验证连通性

### 1.3 非目标（YAGNI）

- ❌ 微信消息监听（逆向方案不稳定）
- ❌ 飞书表写入（用户表为只读共享）
- ❌ Telegram webhook 模式（个人工具无公网域名）
- ❌ 多管理员通知（仅首个 allowed_user_id）
- ❌ 飞书位点持久化（hash 去重已足够；个人表 <1000 行）

---

## 2. 范围

### 2.1 子系统划分（单一计划三段顺序实施）

| 段 | 子系统 | 实施顺序 | 阻塞下游 |
|---|---|---|---|
| ① | _resolve_cid 完善 | 先做 | 是（飞书/TG 任务都依赖正确路径解析） |
| ② | task_service 共享入队服务 | 中间 | 是（TG/飞书适配器都依赖） |
| ③ | TelegramAdapter + FeishuAdapter | 最后 | 否 |

### 2.2 与 Plan B1 的兼容性

- 不修改 Plan B1 已交付的 17 个 commit 的接口签名
- tasks API 行为不变（仅内部重构为复用 task_service）
- 前端无需改动（source 字段值变化不影响 UI 展示）

---

## 3. 架构总览

### 3.1 系统结构

```
┌──────────────────────────────────────────────────────────────┐
│  FastAPI lifespan（main.py）                                  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  1. init_db / reset_running_to_pending（已有）          │  │
│  │  2. wiring services（已有）                             │  │
│  │  3. TaskRunner.start()（已有 + tg_adapter 注入）        │  │
│  │  4. 【新】TelegramAdapter.start()（token 缺失跳过）     │  │
│  │  5. 【新】FeishuAdapter.start_scheduler()               │  │
│  │  finally:                                               │  │
│  │    - TaskRunner.stop()（已有）                          │  │
│  │    - 【新】TelegramAdapter.stop()                       │  │
│  │    - 【新】FeishuAdapter.stop_scheduler()               │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘

入队路径统一（DRY）：
   Web UI  ─→ POST /api/tasks ─┐
   TG Bot  ─→ task_service ────┼─→ parse + dedup + create Task + runner.enqueue
   飞书    ─→ task_service ────┘

_resolve_cid：递归解析 → 缺失目录 mkdir_p → 返回目标 cid
```

### 3.2 关键设计决策（已与用户确认）

| 决策点 | 选择 | 理由 |
|---|---|---|
| 计划拆分 | 单一计划三段顺序实施 | 子系统共享 enqueue 接口与 AuthExpired 策略；放一起易保持一致性 |
| `_resolve_cid` 失败回退 | 仅"目录确实不存在"时自动 mkdir_p；未预期异常直接失败 | 鲁棒且不掩盖 bug；逐级 mkdir 不会因 115 目录结构差异失败，同时避免把未知错误也悄悄当作"降级"处理 |
| TG Bot token 缺失 | 警告后跳过适配器加载 | 个人工具多场景部署；其他来源不受影响 |
| AuthExpired 推送 | TG 推首个 allowed_user_id；飞书复用 TG 兜底 | 飞书表只读不能写回；TG 是唯一可达通道 |
| 飞书位点 | 不持久化，全量拉取 + hash 去重 | 飞书表只读；hash UNIQUE 约束已实现幂等 |
| feishu/test 行为 | 拉一行验证连通性 | 同时验证 token + 表访问 + 列读取 |
| TG 消息规则 | 识别不到链接时 Bot 提示；多链接逐个入队 | UX 友好；用户能感知格式问题 |
| 整体架构 | 薄适配器 + 共享入队服务（task_service） | DRY；逻辑单一来源；测试好写 |

### 3.3 飞书约束（关键）

用户场景明确：**飞书表是只读共享表**。所有设计点必须围绕此约束：

- ❌ 不能写回"备注"列做位点标记
- ❌ 不能写回"已转存"状态
- ✅ 全量拉取 + 本地 hash 去重
- ✅ AuthExpired 推送走 TG Bot（飞书不可达）

---

## 4. 文件清单

### 4.1 新增文件

| 路径 | 责任 |
|---|---|
| `backend/app/services/task_service.py` | 统一入队入口 `enqueue_from_external(source, raw_input, source_ref)` |
| `backend/app/adapters/__init__.py` | 包标记 |
| `backend/app/adapters/telegram_bot.py` | `TelegramAdapter` 长轮询 + 白名单 + 消息处理 + AuthExpired 推送 |
| `backend/app/adapters/feishu_client.py` | httpx 封装：tenant_token 缓存 + list_records 翻页 + 字段展平 |
| `backend/app/adapters/feishu_sheet.py` | `FeishuAdapter` APScheduler 周期轮询 |
| `backend/tests/unit/test_task_service.py` | task_service 单元测试 |
| `backend/tests/unit/test_telegram_bot.py` | TelegramAdapter 单元测试 |
| `backend/tests/unit/test_feishu_client.py` | FeishuClient 单元测试（respx mock） |
| `backend/tests/unit/test_feishu_sheet.py` | FeishuAdapter 单元测试 |
| `backend/tests/integration/test_resolve_cid.py` | _resolve_cid 集成测试 |
| `backend/tests/integration/test_task_runner_with_adapters.py` | TG/飞书任务端到端测试 |
| `backend/tests/integration/test_api_feishu_test.py` | POST /api/config/feishu/test 集成测试 |

### 4.2 修改文件

| 路径 | 改动 |
|---|---|
| `backend/app/services/task_runner.py` | `_resolve_cid` 真正实现递归解析 + mkdir_p；`_pause_for_auth` 增加 TG 推送；构造函数新增 `tg_adapter` 可选参数 |
| `backend/app/main.py` | lifespan 增加 TG/飞书启停；TaskRunner 注入 tg_adapter |
| `backend/app/api/tasks.py` | create_task 复用 task_service（保持现有 API 行为） |
| `backend/app/api/config.py` | `POST /api/config/feishu/test` 实际调用 FeishuClient |
| `backend/app/config.py` | 新增 `telegram_admin_user_id`（默认 0，未配置则取 allowed_user_ids[0]） |
| `backend/requirements.txt` | 新增 `python-telegram-bot~=21.0`（异步 `Application`/`ApplicationBuilder` API，v20+ 才有；13.x 是纯同步 API，与 5.2 节代码不兼容） / `apscheduler~=3.10` |

---

## 5. 组件接口设计

### 5.1 `services/task_service.py`（新增）

```python
import time
from typing import Optional, Tuple

from app.db import get_session
from app.models import Task
from app.services.link_parser import parse


def enqueue_from_external(
    source: str,            # 'telegram' | 'feishu' | 'web'
    raw_input: str,
    source_ref: Optional[str] = None,  # TG message_id / 飞书 record_id
) -> Tuple[Optional[Task], str]:
    """统一入队入口。

    返回 (task_or_None, status_msg)：
      - status_msg == 'created'：新任务，task 非 None
      - status_msg == 'duplicate'：同 hash 已存在，task 为已存在 Task
      - status_msg == 'invalid'：link_parser 无法解析，task=None

    注意：函数内部调用 get_runner().enqueue()；调用方无需关心入队细节。
    """
    link = parse(raw_input)
    if link is None:
        return None, "invalid"
    with get_session() as s:
        existing = s.query(Task).filter_by(share_hash=link.share_hash).first()
        if existing is not None:
            return existing, "duplicate"
        t = Task(
            source=source,
            source_ref=source_ref,
            raw_input=raw_input,
            share_url=f"https://115.com/s/{link.share_id}",
            share_code=link.password,
            share_hash=link.share_hash,
            status="pending",
            created_at=int(time.time()),
        )
        s.add(t)
        s.commit()
        s.refresh(t)
    # 懒导入避免循环依赖
    from app.main import get_runner
    runner = get_runner()
    if runner:
        runner.enqueue(t.id)
    return t, "created"
```

### 5.2 `adapters/telegram_bot.py`（新增）

```python
import re
from typing import Optional

from loguru import logger
from telegram import Update
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler,
    MessageHandler, ContextTypes, filters,
)

from app.services import task_service

# 切出"链接 + 提取码"片段（用 link_parser 的 URL_RE + 周边文本）
from app.services.link_parser import URL_RE, SHORT_RE
_LINK_SLICE_RE = re.compile(
    r"(https?://(?:anyme\.)?115\.com/s/[A-Za-z0-9_-]+(?:\?[^\s]*)?\.?|"
    r"115\.com/s/[A-Za-z0-9_-]+)"
    r"[\s　]*(?:提取码|访问码|密码|password)[:：]?\s*[A-Za-z0-9]{1,12}",
    re.IGNORECASE,
)


class TelegramAdapter:
    """115 链接入站 Bot。长轮询模式接入 FastAPI lifespan。

    白名单：chat_id 或 user_id 任一命中即放行（覆盖群 + 私聊）。
    Admin：用于 AuthExpired 推送，默认取 allowed_user_ids[0]。
    """

    def __init__(
        self,
        bot_token: str,
        allowed_chat_ids: list[int],
        allowed_user_ids: list[int],
        admin_user_id: int = 0,
    ):
        self._token = bot_token
        self._allowed_chat = set(allowed_chat_ids or [])
        self._allowed_user = set(allowed_user_ids or [])
        self._admin_user_id = admin_user_id or (
            allowed_user_ids[0] if allowed_user_ids else 0
        )
        self._app: Optional[Application] = None

    # ---------- 消息处理 ----------
    def _is_allowed(self, update: Update) -> bool:
        chat_ok = update.effective_chat and update.effective_chat.id in self._allowed_chat
        user_ok = update.effective_user and update.effective_user.id in self._allowed_user
        return bool(chat_ok or user_ok)

    @staticmethod
    def _extract_115_links(text: str) -> list[str]:
        """从消息文本切出含链接（含可能的提取码后缀）的片段。

        先切出"链接+提取码"片段，再从**挖空这些片段后剩余的文本**里补抓裸链接——
        避免一条消息里"一个带提取码的链接 + 一个裸链接"混发时，裸链接被整体丢弃
        （旧实现是 slices 非空就直接 return，裸链接永远够不到 fallback 分支）。
        """
        slices = [m.group(0) for m in _LINK_SLICE_RE.finditer(text)]
        remaining = _LINK_SLICE_RE.sub("", text)
        bare = URL_RE.findall(remaining) or SHORT_RE.findall(remaining)
        return slices + bare

    async def _handle_message(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update):
            return  # 静默忽略非白名单
        text = update.effective_message.text or ""
        links = self._extract_115_links(text)
        if not links:
            await ctx.bot.send_message(
                chat_id=update.effective_chat.id,
                reply_to_message_id=update.message.message_id,
                text="未识别到 115 链接，请检查格式",
            )
            return
        created, dup, failed = 0, 0, 0
        for raw in links:
            _, status = task_service.enqueue_from_external(
                source="telegram",
                raw_input=raw,
                source_ref=str(update.message.message_id),
            )
            if status == "created":
                created += 1
            elif status == "duplicate":
                dup += 1
            else:
                failed += 1
        await ctx.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"已入队 {created} / 重复 {dup} / 失败 {failed}",
        )

    async def _cmd_ping(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await ctx.bot.send_message(chat_id=update.effective_chat.id, text="pong")

    # ---------- AuthExpired 推送 ----------
    async def notify_auth_expired(self, error_msg: str):
        """由 TaskRunner._pause_for_auth 回调。"""
        if self._admin_user_id == 0:
            logger.warning("AuthExpired 但未配置 admin user id；跳过推送")
            return
        if self._app is None:
            logger.warning("TelegramAdapter 未启动；跳过推送")
            return
        try:
            await self._app.bot.send_message(
                chat_id=self._admin_user_id,
                text=f"⚠️ 115 Cookie 过期：{error_msg}\n请到 Web UI 扫码重新登录",
            )
        except Exception as e:
            logger.error("notify_auth_expired failed: {}", type(e).__name__)

    # ---------- 生命周期 ----------
    async def start(self):
        if not self._token:
            logger.warning("telegram_bot_token 未配置，跳过 TelegramAdapter 启动")
            return
        self._app = ApplicationBuilder().token(self._token).build()
        self._app.add_handler(CommandHandler("ping", self._cmd_ping))
        self._app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(drop_pending_updates=True)
        logger.info("TelegramAdapter started")

    async def stop(self):
        if self._app is None:
            return
        try:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
        except Exception as e:
            logger.error("TelegramAdapter stop failed: {}", type(e).__name__)
        finally:
            self._app = None
```

### 5.3 `adapters/feishu_client.py`（新增）

```python
from dataclasses import dataclass
from typing import Optional

import httpx


@dataclass
class FeishuRow:
    record_id: str
    link: str          # 链接列原文（含或不含提取码）
    code: str = ""     # 提取码（独立列）
    remark: str = ""


def _to_text(v) -> str:
    """飞书字段可能是 str / list[dict({'text': ...})] / None。统一展平。"""
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        return "".join(
            x.get("text", "") if isinstance(x, dict) else str(x) for x in v
        )
    return str(v)


class FeishuClient:
    """飞书 Bitable 只读客户端（共享表场景）。"""

    BASE = "https://open.feishu.cn/open-apis"

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        app_token: str,
        table_id: str,
        link_column: str = "链接",
        code_column: str = "提取码",
        remark_column: str = "备注",
    ):
        self._app_id = app_id
        self._app_secret = app_secret
        self._app_token = app_token
        self._table_id = table_id
        self._cols = {
            "link": link_column,
            "code": code_column,
            "remark": remark_column,
        }
        self._tenant_token: Optional[str] = None

    async def _ensure_token(self, force_refresh: bool = False) -> str:
        if self._tenant_token and not force_refresh:
            return self._tenant_token
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(
                f"{self.BASE}/auth/v3/tenant_access_token/internal",
                json={"app_id": self._app_id, "app_secret": self._app_secret},
            )
            r.raise_for_status()
            self._tenant_token = r.json()["tenant_access_token"]
            return self._tenant_token

    async def _get_records_page(self, c: httpx.AsyncClient, params: dict) -> dict:
        """请求一页记录；tenant_access_token 过期（401）时清缓存重试一次。

        飞书 tenant_access_token 有效期约 2 小时，若只在首次拿一次并永久缓存
        （旧写法），过期后所有后续轮询都会 401 失败到重启服务为止。这里在拿到
        401 时强制刷新 token 并重试一次，使行为与 §7.1 错误矩阵的描述一致。
        """
        url = (
            f"{self.BASE}/bitable/v1/apps/{self._app_token}"
            f"/tables/{self._table_id}/records"
        )
        token = await self._ensure_token()
        r = await c.get(url, params=params, headers={"Authorization": f"Bearer {token}"})
        if r.status_code == 401:
            token = await self._ensure_token(force_refresh=True)
            r = await c.get(url, params=params, headers={"Authorization": f"Bearer {token}"})
        r.raise_for_status()
        return r.json().get("data", {})

    async def list_records(self, page_size: int = 100) -> list[FeishuRow]:
        """全量拉取（自动翻页）。飞书表只读，不做写入。"""
        rows: list[FeishuRow] = []
        page_token = None
        async with httpx.AsyncClient(timeout=15) as c:
            while True:
                params = {"page_size": page_size}
                if page_token:
                    params["page_token"] = page_token
                data = await self._get_records_page(c, params)
                for item in data.get("items", []):
                    fields = item.get("fields", {})
                    rows.append(FeishuRow(
                        record_id=item.get("record_id", ""),
                        link=_to_text(fields.get(self._cols["link"])),
                        code=_to_text(fields.get(self._cols["code"])),
                        remark=_to_text(fields.get(self._cols["remark"])),
                    ))
                if not data.get("has_more"):
                    break
                page_token = data.get("page_token")
        return rows
```

### 5.4 `adapters/feishu_sheet.py`（新增）

```python
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from app.adapters.feishu_client import FeishuClient
from app.services import task_service


class FeishuAdapter:
    """APScheduler 周期拉飞书表 → task_service 入队。"""

    def __init__(
        self,
        client: FeishuClient,
        interval_minutes: int,
        tg_adapter=None,
    ):
        self._client = client
        self._interval = interval_minutes
        self._tg = tg_adapter  # 兜底推送 AuthExpired（飞书表只读，无法写回）
        self._scheduler: Optional[AsyncIOScheduler] = None

    async def poll_once(self):
        """单次轮询：拉全量 + 逐行入队。"""
        try:
            rows = await self._client.list_records()
        except Exception as e:
            logger.error("feishu poll failed: {}", type(e).__name__)
            return
        for row in rows:
            if not row.link:
                continue
            raw = row.link if not row.code else f"{row.link} 提取码: {row.code}"
            try:
                task_service.enqueue_from_external(
                    source="feishu",
                    raw_input=raw,
                    source_ref=row.record_id,
                )
            except Exception as e:
                logger.error("feishu enqueue failed for {}: {}", row.record_id, type(e).__name__)

    def start_scheduler(self):
        self._scheduler = AsyncIOScheduler()
        self._scheduler.add_job(
            self.poll_once,
            IntervalTrigger(minutes=self._interval),
            id="feishu_poll",
            max_instances=1,
            coalesce=True,
        )
        self._scheduler.start()
        logger.info(
            "FeishuAdapter scheduler started (interval={}min)", self._interval
        )

    def stop_scheduler(self):
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
```

### 5.5 `services/task_runner._resolve_cid`（修改）

```python
async def _resolve_cid(self, target_path: str) -> int:
    """递归解析 /电视剧/权力的游戏 (2011) 到 cid；缺失中间目录 mkdir_p。

    target_path 形如 '/电视剧/权力的游戏 (2011)'。

    降级策略仅覆盖"该级目录确实不存在"这一种情况（接口返回 cid=0 → mkdir；
    mkdir 本身又拿不到新 cid → 回退用上一级已解析 cid，文件落到父目录而非中断）。
    调用本身抛出的未预期异常（网络错误、p115 接口契约变化等）**不在这里吞掉**，
    直接向上抛给 TaskRunner 走既有的任务失败流程（status=failed，可重试）。
    这个函数本来就是为了修"_resolve_cid 失效导致文件全部静默落到根目录"这个
    bug 存在的；如果这里再用一个大 except Exception 把所有未知错误也当成
    "正常降级"处理，等于把同一类 bug 换了个隐蔽的位置重新引入一遍——只是从
    "总是落根目录"变成"某次悄悄落错中间目录"，而且没有任何用户可见的失败信号。
    """
    if not self._lm.is_logged_in():
        return 0
    client = self._lm.get_client()
    parts = [p for p in target_path.strip("/").split("/") if p]
    cur_cid = 0  # 根目录
    for name in parts:
        resp = client.dir_remote_path_to_cid(path=f"/{name}", cid=cur_cid)
        cid = resp.get("data", {}).get("cid", 0) if isinstance(resp, dict) else 0
        if cid:
            cur_cid = cid
            continue
        # 该级不存在 → mkdir
        mk = client.mkdir(pid=cur_cid, name=name)
        new_cid = mk.get("data", {}).get("file_id", 0) if isinstance(mk, dict) else 0
        if not new_cid:
            # mkdir 明确返回"无 cid"（非异常）→ 回退到上一级，降级而非中断
            logger.warning("_resolve_cid mkdir returned no cid at {!r}", name)
            return cur_cid
        cur_cid = new_cid
    return cur_cid
```

### 5.6 AuthExpired 推送挂载（TaskRunner 修改）

```python
# task_runner.py 构造函数新增参数：
def __init__(
    self,
    session_factory,
    login_manager,
    share_fetcher,
    classifier=classify,
    metadata_scraper=None,
    path_resolver=None,
    transfer_task=None,
    broadcaster=None,
    tg_adapter=None,    # 【新】可选，用于 AuthExpired 兜底推送
):
    # ...
    self._tg_adapter = tg_adapter

# _pause_for_auth 修改：
async def _pause_for_auth(self, task_id: int, error_msg: str) -> None:
    with self._session_factory() as s:
        t = s.get(Task, task_id)
        if t is None:
            return
        t.status = "pending"
        t.error_msg = f"需重新登录: {error_msg}"
        source = t.source  # 【新】读取 source 字段
        s.commit()
    await self._notify(
        {"task_id": task_id, "status": "auth_expired", "error": error_msg}
    )
    # 【新】非 Web 来源且 TG 可达 → Bot 兜底推送
    if source in ("telegram", "feishu") and self._tg_adapter:
        try:
            await self._tg_adapter.notify_auth_expired(error_msg)
        except Exception as e:
            logger.error(
                "tg_adapter.notify_auth_expired failed: {}", type(e).__name__
            )
    self.enqueue(task_id)
```

### 5.7 `main.py` lifespan 集成（修改）

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _runner
    init_db()
    n = reset_running_to_pending(get_session)
    if n > 0:
        logger.info("启动时恢复 {} 个未完成任务", n)

    # 装配核心服务
    lm, share_fetcher, md_scraper, path_resolver, transfer_task = _wiring_services()

    # 装配 TG 适配器（token 缺失时 start() 内部跳过）
    tg_adapter = TelegramAdapter(
        bot_token=settings.telegram_bot_token,
        allowed_chat_ids=settings.telegram_allowed_chat_ids,
        allowed_user_ids=settings.telegram_allowed_user_ids,
        admin_user_id=settings.telegram_admin_user_id,
    )

    _runner = TaskRunner(
        session_factory=get_session,
        login_manager=lm,
        share_fetcher=share_fetcher,
        classifier=classify,
        metadata_scraper=md_scraper,
        path_resolver=path_resolver,
        transfer_task=transfer_task,
        broadcaster=broadcaster,
        tg_adapter=tg_adapter,  # 【新】
    )
    _runner.start()

    # 装配飞书适配器（缺失配置时 start_scheduler 内部抛错或跳过）
    feishu_adapter = None
    if settings.feishu_app_id and settings.feishu_app_token:
        feishu_client = FeishuClient(
            app_id=settings.feishu_app_id,
            app_secret=settings.feishu_app_secret,
            app_token=settings.feishu_app_token,
            table_id=settings.feishu_table_id,
            link_column=settings.feishu_link_column,
            code_column=settings.feishu_code_column,
            remark_column=settings.feishu_remark_column,
        )
        feishu_adapter = FeishuAdapter(
            client=feishu_client,
            interval_minutes=settings.feishu_poll_interval_minutes,
            tg_adapter=tg_adapter,
        )
        try:
            feishu_adapter.start_scheduler()
        except Exception as e:
            logger.error("feishu scheduler start failed: {}", type(e).__name__)

    # 启动 TG 适配器（最后启动，避免漏消息）
    try:
        await tg_adapter.start()
    except Exception as e:
        logger.error("telegram adapter start failed: {}", type(e).__name__)

    logger.info("TaskRunner + adapters started")
    try:
        yield
    finally:
        if feishu_adapter:
            feishu_adapter.stop_scheduler()
        try:
            await tg_adapter.stop()
        except Exception:
            pass
        _runner.stop()
        logger.info("TaskRunner + adapters stopped")
```

### 5.8 `api/config.py` feishu/test 实现（修改）

```python
@router.post("/feishu/test", response_model=FeishuTestResp)
async def test_feishu():
    """实际拉一行验证连通性：tenant_token + 表访问 + 列读取。"""
    if not settings.feishu_app_id or not settings.feishu_app_token:
        return FeishuTestResp(
            ok=False, message="未配置 FEISHU_APP_ID / FEISHU_APP_TOKEN"
        )
    try:
        from app.adapters.feishu_client import FeishuClient
        client = FeishuClient(
            app_id=settings.feishu_app_id,
            app_secret=settings.feishu_app_secret,
            app_token=settings.feishu_app_token,
            table_id=settings.feishu_table_id,
            link_column=settings.feishu_link_column,
            code_column=settings.feishu_code_column,
            remark_column=settings.feishu_remark_column,
        )
        rows = await client.list_records(page_size=1)
    except httpx.HTTPStatusError as e:
        return FeishuTestResp(
            ok=False, message=f"飞书 API 错误：{e.response.status_code} {e.response.text[:200]}",
        )
    except Exception as e:
        return FeishuTestResp(ok=False, message=f"未知错误：{type(e).__name__}")
    if not rows:
        return FeishuTestResp(
            ok=True, message="连通正常，但表为空或列名未匹配"
        )
    return FeishuTestResp(ok=True, message=f"连通正常，首行链接列：{rows[0].link[:50]}")
```

### 5.9 `config.py` 新增字段（修改）

```python
# 在 Settings 类中追加：
telegram_admin_user_id: int = 0  # 0 表示取 allowed_user_ids[0]
```

---

## 6. 数据流

### 6.1 Telegram 入站典型流程

```
[1] 用户在白名单群/私聊发送：
    "https://115.com/s/abc1234 提取码: x9yz"

[2] Telegram 长轮询拉到 Update
    └─ TelegramAdapter._handle_message(update, ctx)
        ├─ _is_allowed(update) = True  → 继续
        ├─ links = _extract_115_links(text) = ["https://115.com/s/abc1234 提取码: x9yz"]
        └─ task_service.enqueue_from_external(
              source="telegram",
              raw_input=raw,
              source_ref="<message_id>",
           )
           └─ parse(raw) → ShareLink(share_id="abc1234", password="x9yz")
           └─ Task(share_hash=sha256("abc1234")) 入库 status=pending
           └─ runner.enqueue(t.id)

[3] Bot 回复："已入队 1 / 重复 0 / 失败 0"

[4] TaskRunner worker 消费：
    ├─ ShareFetcher.fetch → 拿到分享内容
    ├─ Classifier → "电视剧"
    ├─ MetadataScraper → 权力的游戏 (2011)
    ├─ PathResolver.resolve → "/电视剧/权力的游戏 (2011)"
    ├─ _resolve_cid("/电视剧/权力的游戏 (2011)")
    │   ├─ client.dir_remote_path_to_cid(path="/电视剧", cid=0) → cid=12345
    │   ├─ client.dir_remote_path_to_cid(path="/权力的游戏 (2011)", cid=12345) → cid=0（不存在）
    │   ├─ client.mkdir(pid=12345, name="权力的游戏 (2011)") → cid=67890
    │   └─ return 67890
    ├─ TransferTask.run(share_id, password, target_cid=67890)
    │   └─ client.share_receive({share_code, file_id=0, cid=67890, receive_code})
    └─ status=done → broadcaster.publish({task_id, status:"done"})

[5] Web SSE 推送 → 前端任务列表实时更新
```

### 6.2 飞书轮询典型流程

```
[1] APScheduler 每 5 分钟触发 FeishuAdapter.poll_once()

[2] FeishuClient.list_records()
    └─ _ensure_token() → tenant_access_token（首次缓存）
    └─ GET /bitable/v1/apps/{app_token}/tables/{table_id}/records
        └─ 自动翻页（has_more / page_token）
        └─ 字段展平（_to_text 兼容 str / list[dict] / None）

[3] for row in rows:
    ├─ row.link 为空 → continue
    └─ raw = "https://115.com/s/xyz999 提取码: abcd"
        └─ task_service.enqueue_from_external(
              source="feishu", raw_input=raw, source_ref=row.record_id,
           )
           └─ parse → ShareLink
           └─ Task.share_hash UNIQUE 命中 → status="duplicate" → 跳过（不入队）
           └─ 或 status="created" → runner.enqueue
```

### 6.3 AuthExpired 兜底推送流程

```
[1] TransferTask.run 抛 AuthExpiredError
    └─ TaskRunner._pause_for_auth(task_id, error_msg)
        ├─ Task.status = "pending"（回退队列）
        ├─ broadcaster.publish({status:"auth_expired", error})
        ├─ if task.source in ("telegram", "feishu") and self._tg_adapter:
        │       await tg_adapter.notify_auth_expired(error_msg)
        │       └─ Bot.send_message(chat_id=admin_user_id,
        │             text="⚠️ 115 Cookie 过期：...\n请到 Web UI 扫码重新登录")
        └─ runner.enqueue(task_id)

[2] Web 用户看到 SSE 通知 → 扫码
[3] 扫码完成 → cookie 更新 → 后台 worker 重新消费 pending 任务 → 成功
```

### 6.4 任务状态转换（完整图）

```
                       ┌────────────────────────────┐
                       │                            ▼
pending ──→ running ──┬─→ done           (AuthExpiredError)
   ▲                  │                  │
   │                  ├─→ failed         └── pending (回退队列)
   │                  │                     ▲
   │                  └─→ pending (AuthExpired)
   │                                         │
   └──────────────────────────────────────────┘
       (Web 用户扫码后，runner 重试 pending 任务)
```

---

## 7. 错误处理

### 7.1 错误矩阵

| 故障点 | 检测 | 恢复策略 | 用户感知 |
|---|---|---|---|
| TG Bot token 缺失 | `settings.telegram_bot_token == ""` | lifespan 跳过 TG 适配器 | logger.warning；Web/飞书不受影响 |
| TG 长轮询连接断开 | python-telegram-bot 内部重试 | 库自动 backoff 重连 | 静默；最多漏掉几条消息 |
| TG 非白名单消息 | `_is_allowed(update) == False` | 静默忽略 | 用户无感（防探测） |
| TG 多链接中有失败 | parse 返回 None | 计入 failed 计数 | Bot 回复"已入队 X / 重复 Y / 失败 Z" |
| 飞书 tenant_access_token 失效 | 401 / 异常 | 清缓存重试一次 | 单次轮询失败，下次自动恢复 |
| 飞书表 token / 列名错 | list_records 抛 httpx.HTTPStatusError | logger.error；本次跳过 | 轮询停摆直到用户改配置 |
| 飞书拉取异常（网络） | list_records 抛 Exception | logger.error；本次跳过 | 下次重试 |
| 飞书字段格式异常 | `_to_text` 兜底返回 "" | link 为空跳过；其他字段忽略 | 静默 |
| 链接已存在（dedup 命中） | Task.share_hash UNIQUE | 跳过创建；不入队 | 静默；幂等性保证 |
| _resolve_cid 中间目录缺失 | dir_remote_path_to_cid 返回 cid=0 | mkdir 创建；继续递归 | 静默；自动 mkdir_p |
| _resolve_cid mkdir 返回无 cid（非异常） | mkdir 响应中拿不到 file_id | 回退到上一级已解析 cid | 文件落到父目录（降级而非失败） |
| _resolve_cid 遇到未预期异常（网络/接口契约变化） | dir_remote_path_to_cid / mkdir 抛出异常 | 不捕获，向上抛给 TaskRunner | 任务标记 failed，前端可见 + 可重试；不会静默落错目录 |
| AuthExpired (TG/飞书来源) | AuthExpiredError | pending 回退 + Bot 推送 admin | Bot 收到"扫码提醒" |
| AuthExpired (Web 来源) | AuthExpiredError | pending 回退 + SSE 通知 | 前端弹扫码页 |
| APScheduler 任务堆积 | max_instances=1 + coalesce=True | 跳过重叠执行 | 静默 |

### 7.2 安全性核查（与 CLAUDE.md 一致）

- ✅ Cookie 不写日志：所有 `logger.error("...: {}", type(e).__name__)` 模式
- ✅ 飞书 app_secret 加密存 SQLite（沿用 Plan B1 机制）
- ✅ TG Bot 不响应非白名单消息（防探测）
- ✅ AuthExpired 推送仅发 admin_user_id（不泄露给群）
- ✅ Web Bearer Token 中间件已就位（Plan B1）；TG/飞书入队是内部调用，不经 HTTP
- ✅ 始终 UTF-8 编码（pydantic-settings `env_file_encoding="utf-8"` 已就位）

---

## 8. 测试策略

### 8.1 测试矩阵（TDD）

| 测试文件 | 覆盖点 | 关键用例 |
|---|---|---|
| `tests/unit/test_task_service.py`（新） | `enqueue_from_external` | (a) 创建新任务；(b) duplicate 返回已存在；(c) invalid 链接返回 None；(d) source_ref 正确填充 |
| `tests/unit/test_telegram_bot.py`（新） | TelegramAdapter | (a) `_is_allowed` chat_id 命中；(b) `_is_allowed` user_id 命中；(c) 非白名单忽略；(d) `_handle_message` 入队单链接；(e) 多链接多次入队；(f) 无链接提示"未识别"；(g) `notify_auth_expired` 调用 bot.send_message；(h) 一条消息里"带提取码的链接 + 裸链接"混发，两个都被提取（回归：旧实现 slices 非空即 return，会丢裸链接） |
| `tests/unit/test_feishu_client.py`（新） | FeishuClient | (a) `list_records` 单页 + 翻页；(b) `_to_text` str/list[dict]/None；(c) token 缓存；(d) HTTP 错误抛异常；(e) 首次请求 401 → 清缓存重试一次并成功 |
| `tests/unit/test_feishu_sheet.py`（新） | FeishuAdapter | (a) `poll_once` 入队所有行；(b) 空行跳过；(c) hash 命中跳过；(d) 飞书异常不抛出（仅 log） |
| `tests/integration/test_resolve_cid.py`（新） | _resolve_cid | (a) 全路径存在直接返回；(b) 中间缺失 mkdir；(c) mkdir 返回无 cid 时回退父级（非异常路径）；(d) 未登录返回 0；(e) client 抛出未预期异常时向上传播（不吞掉、不降级） |
| `tests/integration/test_task_runner_with_adapters.py`（新） | 端到端 | (a) telegram 任务成功；(b) feishu 任务 AuthExpired 触发 notify_auth_expired |
| `tests/integration/test_api_feishu_test.py`（新） | POST /api/config/feishu/test | (a) 配置正确 → ok=True；(b) 配置错 → ok=False + 可读 message |

### 8.2 TDD 节奏

- 严格 red-green-refactor：先写失败测试 → 最小实现 → 重构
- `_resolve_cid` 测试用 `MagicMock` 模拟 p115client；不实际请求 115
- `TelegramAdapter` 测试用 `python-telegram-bot` 的 `Update.de_json()` 构造假 Update
- `FeishuClient` 测试用 `respx` mock httpx（已有依赖）

### 8.3 验收标准（部署后人工核查）

- [ ] 在 .env 配置 TG Bot Token + allowed_user_ids，启动服务 → 日志出现 "TelegramAdapter started"
- [ ] 在白名单私聊中发送 `https://115.com/s/<test_id> 提取码: <code>` → Bot 回复"已入队 1 / 重复 0 / 失败 0"
- [ ] 在白名单私聊中发送非 115 链接 → Bot 回复"未识别到 115 链接"
- [ ] 在非白名单私聊中发送 115 链接 → 无任何回复
- [ ] 在 .env 配置飞书凭证，启动服务 → 日志出现 "FeishuAdapter scheduler started"
- [ ] 飞书表新增一行 → 5 分钟内任务列表出现新 task（source=feishu）
- [ ] 重复链接再次入表 → 跳过（无新 task）
- [ ] POST /api/config/feishu/test（配置正确）→ `{"ok": true, "message": "连通正常..."}`
- [ ] 手动让 Cookie 过期（清空 AuthState 表）+ 触发飞书任务 → Bot 推送"扫码提醒"

---

## 9. 部署清单

### 9.1 用户准备

1. **飞书应用**：飞书开放平台创建自建应用，授予 Bitable 读取权限
2. **Telegram Bot**：通过 @BotFather 创建 Bot，拿到 token
3. **Telegram user_id**：通过 @userinfobot 拿到自己的 user_id
4. **飞书 Bitable app_token / table_id**：从飞书表 URL 中提取

### 9.2 .env 完整字段

```dotenv
# 既有字段（Plan B1 已就位）
DATABASE_URL=sqlite:///data/config.db
ENCRYPTION_KEY=<Fernet key>
WEB_API_TOKEN=<Bearer token>
TMDB_API_KEY=<TMDB key>
P115_APP_DATA_DIR=data/p115

# Plan B2 新增
TELEGRAM_BOT_TOKEN=<from BotFather>
TELEGRAM_ALLOWED_CHAT_IDS=-1001234567890   # 可选，群 ID
TELEGRAM_ALLOWED_USER_IDS=123456789        # 必填，至少一个
TELEGRAM_ADMIN_USER_ID=0                   # 0 表示取 ALLOWED_USER_IDS[0]

FEISHU_APP_ID=<自建应用 App ID>
FEISHU_APP_SECRET=<自建应用 App Secret>     # 写入后加密存 SQLite
FEISHU_APP_TOKEN=<Bitable app_token>
FEISHU_TABLE_ID=<Bitable table_id>
FEISHU_LINK_COLUMN=链接
FEISHU_CODE_COLUMN=提取码
FEISHU_REMARK_COLUMN=备注
FEISHU_POLL_INTERVAL_MINUTES=5
```

### 9.3 启动

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
# 或开发模式
uvicorn app.main:app --reload
```

启动日志预期：
```
TaskRunner started
FeishuAdapter scheduler started (interval=5min)
TelegramAdapter started
TaskRunner + adapters started
```

---

## 10. 自审清单

- ✅ 占位符扫描：无 "TBD" / "TODO" / 模糊表述
- ✅ 内部一致性：所有 source 取值统一为 `'web' | 'telegram' | 'feishu'`
- ✅ 范围检查：单一计划三段实施，每段独立可测
- ✅ 歧义检查：飞书表只读约束已贯穿全文（5.4/6.2/7.1 均受其约束）
- ✅ 类型一致：`task_service.enqueue_from_external` 返回 `Tuple[Optional[Task], str]` 在 5.1/5.2/5.4 中保持一致

---

## 11. 后续步骤

- **下一步**：调用 `superpowers:writing-plans` skill 把本设计转为可执行实施计划，保存到 `docs/superpowers/plans/2026-07-03-plan-b2.md`
- **执行方式**：subagent-driven-development（用户已默认偏好）
- **完成验收**：所有单元/集成测试通过 + 部署后人工核查清单全部勾选
- **实施前必须核实**：`p115client` 的 `dir_remote_path_to_cid(path, cid)` 实际签名与语义——5.5 节 `_resolve_cid` 的逐级递归解析假设该接口"以 `cid` 为基准解析单层相对路径"；本机未安装 `p115client`，这个假设没有被验证过。若实际语义是"必须传从根开始的完整绝对路径"或返回结构不同，需要重新设计这段逻辑，写实施计划前先翻一下这个方法的真实实现。
