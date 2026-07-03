"""Telegram Bot 适配器：长轮询 + 白名单 + 消息处理 + AuthExpired 推送。

接入 FastAPI lifespan（main.py）：
- start() 分阶段 initialize/start/updater.start_polling
- stop() 反序清理
"""
import re
from typing import Optional

from loguru import logger  # noqa: F401  (Task 5 会用)
from telegram import Update
from telegram.ext import (
    Application,  # noqa: F401  (Task 5 会用)
    ApplicationBuilder,  # noqa: F401  (Task 5 会用)
    CommandHandler,  # noqa: F401  (Task 5 会用)
    ContextTypes,  # noqa: F401  (Task 5 会用)
    MessageHandler,  # noqa: F401  (Task 5 会用)
    filters,  # noqa: F401  (Task 5 会用)
)

from app.services import task_service  # noqa: F401  (Task 5 会用)
from app.services.link_parser import SHORT_RE, URL_RE

# "链接 + 提取码"组合切片：先抓 URL（或短链），后跟可选空白 + 提取码关键词 + 1-12 字符码
_LINK_SLICE_RE = re.compile(
    r"(https?://(?:anyme\.)?115\.com/s/[A-Za-z0-9_-]+(?:\?[^\s]*)?\.?"
    r"|115\.com/s/[A-Za-z0-9_-]+)"
    r"[\s　]*(?:提取码|访问码|密码|password)[:：]?\s*[A-Za-z0-9]{1,12}",
    re.IGNORECASE,
)
# 已知限制：_LINK_SLICE_RE 只匹配"链接 + 提取码关键字 + 码"形式。
# query string 形式（如 https://115.com/s/abc?password=xyz）的 password
# 不在 _LINK_SLICE_RE 覆盖范围；会落入 bare 分支只返回 URL 字符串本身。
# 但 password 不会真的丢失——下游 task_service.enqueue_from_external →
# link_parser.parse(raw_input) 内部会从 query string 中提取 password，
# 因此 URL 形式的 password 由 parse() 兜底处理。


class TelegramAdapter:
    """115 链接入站 Bot。

    白名单：chat_id 或 user_id 任一命中即放行（覆盖群 + 私聊）。
    Admin：用于 AuthExpired 推送；默认取 allowed_user_ids[0]，可显式覆盖。
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

    # ---------- 白名单 ----------
    def _is_allowed(self, update: Update) -> bool:
        chat_ok = update.effective_chat and update.effective_chat.id in self._allowed_chat
        user_ok = update.effective_user and update.effective_user.id in self._allowed_user
        return bool(chat_ok or user_ok)

    # ---------- 链接切片 ----------
    @staticmethod
    def _extract_115_links(text: str) -> list[str]:
        """先切"链接+提取码"组合片段，再从剩余文本补抓裸链接。

        返回值：list[str]，每个元素是完整 URL（或 URL+提取码）字符串。
        下游消费方（_handle_message）会逐个调 task_service.enqueue_from_external。

        旧实现的 bug：slices 非空即 return，导致"一条带码链接 + 一条裸链接"
        混发时裸链接被丢。这里把切片挖空后再扫一遍剩余文本。

        实现：bare 分支用 finditer + m.group(0) 拿完整 URL 字符串，
        与 slices 元素形态一致；旧 findall 因 pattern 含命名 group
        只返回 share_id 字符串，导致异质列表。
        """
        slices = [m.group(0) for m in _LINK_SLICE_RE.finditer(text)]
        remaining = _LINK_SLICE_RE.sub("", text)
        # 用 finditer 取 m.group(0) 拿完整 URL 字符串，与 slices 元素形态一致
        url_matches = [m.group(0) for m in URL_RE.finditer(remaining)]
        short_matches = [m.group(0) for m in SHORT_RE.finditer(remaining)]
        bare = url_matches or short_matches
        return slices + bare

    # ---------- 以下方法在 Task 5 实现 ----------
    async def _handle_message(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        raise NotImplementedError

    async def _cmd_ping(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        raise NotImplementedError

    async def notify_auth_expired(self, error_msg: str):
        raise NotImplementedError

    async def start(self):
        raise NotImplementedError

    async def stop(self):
        raise NotImplementedError
