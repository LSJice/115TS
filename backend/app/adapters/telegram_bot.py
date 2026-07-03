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

from app.services import task_service
from app.services.link_parser import SHORT_RE, URL_RE

# "链接 + 提取码"组合切片：先抓 URL（或短链），后跟可选空白 + 提取码关键词 + 1-12 字符码
_LINK_SLICE_RE = re.compile(
    r"(https?://(?:anyme\.)?115\.com/s/[A-Za-z0-9_-]+(?:\?[^\s]*)?\.?"
    r"|115\.com/s/[A-Za-z0-9_-]+)"
    r"[\s　]*(?:提取码|访问码|密码|password)[:：]?\s*[A-Za-z0-9]{1,12}",
    re.IGNORECASE,
)
# 已知限制：_LINK_SLICE_RE 只匹配"链接 + 提取码关键字 + 码"形式。
# query string 形式（如 https://115.com/s/abc?password=xyz）的密码
# 不在 _LINK_SLICE_RE 覆盖范围；落入 bare 分支时仅返回 URL，
# 密码需要下游 task_service.enqueue_from_external → parse() 内部处理
# （parse 会从 query string 中提取 password）。


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
        """
        slices = [m.group(0) for m in _LINK_SLICE_RE.finditer(text)]
        remaining = _LINK_SLICE_RE.sub("", text)
        url_matches = [m.group(0) for m in URL_RE.finditer(remaining)]
        short_matches = [m.group(0) for m in SHORT_RE.finditer(remaining)]
        bare = url_matches or short_matches
        return slices + bare

    # ---------- 消息处理 ----------
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
        if self._app is not None:
            logger.warning("TelegramAdapter 已启动；跳过重复 start")
            return
        if not self._token:
            logger.warning("telegram_bot_token 未配置，跳过 TelegramAdapter 启动")
            return
        try:
            self._app = ApplicationBuilder().token(self._token).build()
            self._app.add_handler(CommandHandler("ping", self._cmd_ping))
            self._app.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
            )
            await self._app.initialize()
            await self._app.start()
            await self._app.updater.start_polling(drop_pending_updates=True)
            logger.info("TelegramAdapter started")
        except Exception as e:
            # 启动失败：清空 _app 让下次 start 可重试；不在 except 内尝试清理（避免二次异常）
            logger.error("TelegramAdapter start failed: {}", type(e).__name__)
            self._app = None

    async def stop(self):
        if self._app is None:
            return
        app = self._app
        self._app = None  # 提前清空，避免重复 stop
        # 三步独立 try：保证 shutdown 一定执行
        try:
            await app.updater.stop()
        except Exception as e:
            logger.error("updater.stop failed: {}", type(e).__name__)
        try:
            await app.stop()
        except Exception as e:
            logger.error("app.stop failed: {}", type(e).__name__)
        try:
            await app.shutdown()
        except Exception as e:
            logger.error("app.shutdown failed: {}", type(e).__name__)
