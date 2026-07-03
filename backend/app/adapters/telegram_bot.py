"""Telegram Bot 适配器：长轮询 + 白名单 + 消息处理 + AuthExpired 推送。

接入 FastAPI lifespan（main.py）：
- start() 分阶段 initialize/start/updater.start_polling
- stop() 反序清理
"""
import re
from typing import Optional

from loguru import logger
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
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

        旧实现的 bug：slices 非空即 return，导致"一条带码链接 + 一条裸链接"
        混发时裸链接被丢。这里把切片挖空后再扫一遍剩余文本。
        """
        slices = [m.group(0) for m in _LINK_SLICE_RE.finditer(text)]
        remaining = _LINK_SLICE_RE.sub("", text)
        bare = URL_RE.findall(remaining) or SHORT_RE.findall(remaining)
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
