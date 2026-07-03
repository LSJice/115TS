import pytest
from telegram import Chat, Message, Update, User
from unittest.mock import AsyncMock, MagicMock, patch

from app.adapters.telegram_bot import TelegramAdapter


def make_update(text: str, chat_id: int, user_id: int, message_id: int = 1) -> Update:
    """构造最小可用 Update 对象（python-telegram-bot 21.x 兼容）。"""
    chat = Chat(id=chat_id, type=Chat.PRIVATE)
    user = User(id=user_id, is_bot=False, first_name="tester")
    msg = Message(message_id=message_id, date=None, chat=chat, from_user=user, text=text)
    return Update(update_id=1, message=msg)


def test_is_allowed_user_id_match():
    a = TelegramAdapter(
        bot_token="t", allowed_chat_ids=[], allowed_user_ids=[123],
    )
    upd = make_update("hi", chat_id=999, user_id=123)
    assert a._is_allowed(upd) is True


def test_is_allowed_chat_id_match():
    a = TelegramAdapter(
        bot_token="t", allowed_chat_ids=[-100123], allowed_user_ids=[],
    )
    upd = make_update("hi", chat_id=-100123, user_id=999)
    assert a._is_allowed(upd) is True


def test_is_allowed_neither_match():
    a = TelegramAdapter(
        bot_token="t", allowed_chat_ids=[1], allowed_user_ids=[2],
    )
    upd = make_update("hi", chat_id=999, user_id=888)
    assert a._is_allowed(upd) is False


def test_admin_user_id_defaults_to_first_allowed():
    a = TelegramAdapter(
        bot_token="t", allowed_chat_ids=[], allowed_user_ids=[555, 666],
    )
    assert a._admin_user_id == 555


def test_admin_user_id_explicit_overrides():
    a = TelegramAdapter(
        bot_token="t", allowed_chat_ids=[], allowed_user_ids=[555], admin_user_id=777,
    )
    assert a._admin_user_id == 777


def test_extract_single_link_with_code():
    text = "https://115.com/s/abc1234 提取码: xyz"
    links = TelegramAdapter._extract_115_links(text)
    assert len(links) == 1
    assert "abc1234" in links[0]
    assert "xyz" in links[0]


def test_extract_bare_link_only():
    text = "https://115.com/s/abc1234"
    links = TelegramAdapter._extract_115_links(text)
    assert len(links) == 1
    assert "abc1234" in links[0]


def test_extract_chinese_password_keyword():
    text = "https://115.com/s/abc1234 密码 abcd"
    links = TelegramAdapter._extract_115_links(text)
    assert len(links) == 1
    assert "abcd" in links[0]


def test_extract_mixed_coded_plus_bare_does_not_drop_bare():
    """回归：旧实现 slices 非空即 return，导致裸链接被丢。"""
    text = (
        "https://115.com/s/abc1234 提取码: xyz "
        "https://115.com/s/def5678"
    )
    links = TelegramAdapter._extract_115_links(text)
    assert len(links) == 2
    assert "abc1234" in links[0]
    assert "def5678" in links[1]


def test_extract_no_link_returns_empty():
    links = TelegramAdapter._extract_115_links("hello world")
    assert links == []


@pytest.mark.asyncio
async def test_handle_message_single_link_enqueues_and_replies():
    a = TelegramAdapter(
        bot_token="t", allowed_chat_ids=[100], allowed_user_ids=[],
    )
    upd = make_update(
        "https://115.com/s/abc1234 提取码: xyz",
        chat_id=100, user_id=999, message_id=42,
    )
    ctx = MagicMock()
    ctx.bot.send_message = AsyncMock()

    with patch("app.adapters.telegram_bot.task_service") as ts:
        ts.enqueue_from_external.return_value = (MagicMock(), "created")
        await a._handle_message(upd, ctx)

    ts.enqueue_from_external.assert_called_once_with(
        source="telegram",
        raw_input="https://115.com/s/abc1234 提取码: xyz",
        source_ref="42",
    )
    # Bot 应回复入队统计
    ctx.bot.send_message.assert_called_once()
    text = ctx.bot.send_message.call_args.kwargs.get("text", "")
    assert "已入队" in text and "1" in text


@pytest.mark.asyncio
async def test_handle_message_no_link_replies_unrecognized():
    a = TelegramAdapter(
        bot_token="t", allowed_chat_ids=[100], allowed_user_ids=[],
    )
    upd = make_update("hello", chat_id=100, user_id=999, message_id=1)
    ctx = MagicMock()
    ctx.bot.send_message = AsyncMock()
    await a._handle_message(upd, ctx)
    text = ctx.bot.send_message.call_args.kwargs.get("text", "")
    assert "未识别" in text


@pytest.mark.asyncio
async def test_handle_message_non_allowed_is_silent():
    a = TelegramAdapter(
        bot_token="t", allowed_chat_ids=[100], allowed_user_ids=[],
    )
    upd = make_update("https://115.com/s/abc", chat_id=999, user_id=888)
    ctx = MagicMock()
    ctx.bot.send_message = AsyncMock()
    with patch("app.adapters.telegram_bot.task_service") as ts:
        await a._handle_message(upd, ctx)
    ts.enqueue_from_external.assert_not_called()
    ctx.bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_handle_message_counts_duplicate_and_failed():
    """一条消息含 3 个链接：1 新建、1 重复、1 无效（parse 失败）。"""
    a = TelegramAdapter(
        bot_token="t", allowed_chat_ids=[100], allowed_user_ids=[],
    )
    text = (
        "https://115.com/s/aaa111 提取码: a "
        "https://115.com/s/bbb222 提取码: b "
        "https://115.com/s/ccc333 提取码: c"
    )
    upd = make_update(text, chat_id=100, user_id=999, message_id=5)
    ctx = MagicMock()
    ctx.bot.send_message = AsyncMock()

    statuses = ["created", "duplicate", "invalid"]
    with patch("app.adapters.telegram_bot.task_service") as ts:
        ts.enqueue_from_external.side_effect = [
            (MagicMock(), s) for s in statuses
        ]
        await a._handle_message(upd, ctx)

    assert ts.enqueue_from_external.call_count == 3
    text = ctx.bot.send_message.call_args.kwargs.get("text", "")
    assert "1" in text and "1" in text and "1" in text  # created/dup/failed 各 1


@pytest.mark.asyncio
async def test_notify_auth_expired_sends_to_admin():
    a = TelegramAdapter(
        bot_token="t", allowed_chat_ids=[], allowed_user_ids=[555],
    )
    a._app = MagicMock()
    a._app.bot.send_message = AsyncMock()
    await a.notify_auth_expired("cookie expired")
    a._app.bot.send_message.assert_awaited_once()
    kwargs = a._app.bot.send_message.call_args.kwargs
    assert kwargs["chat_id"] == 555
    assert "cookie expired" in kwargs["text"]


@pytest.mark.asyncio
async def test_notify_auth_expired_no_admin_skips():
    a = TelegramAdapter(
        bot_token="t", allowed_chat_ids=[], allowed_user_ids=[],
    )
    a._app = MagicMock()
    a._app.bot.send_message = AsyncMock()
    await a.notify_auth_expired("err")
    a._app.bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_start_without_token_skips():
    a = TelegramAdapter(bot_token="", allowed_chat_ids=[], allowed_user_ids=[])
    await a.start()
    assert a._app is None


@pytest.mark.asyncio
async def test_start_with_token_initializes_and_polls():
    """验证 start() 分阶段调用 initialize/start/updater.start_polling。"""
    a = TelegramAdapter(
        bot_token="t", allowed_chat_ids=[], allowed_user_ids=[],
    )
    with patch("app.adapters.telegram_bot.ApplicationBuilder") as AB:
        app_mock = MagicMock()
        app_mock.initialize = AsyncMock()
        app_mock.start = AsyncMock()
        app_mock.updater.start_polling = AsyncMock()
        app_mock.add_handler = MagicMock()
        AB.return_value.token.return_value.build.return_value = app_mock
        await a.start()
    app_mock.initialize.assert_awaited_once()
    app_mock.start.assert_awaited_once()
    app_mock.updater.start_polling.assert_awaited_once()
    assert app_mock.add_handler.call_count == 2  # ping + message


@pytest.mark.asyncio
async def test_stop_idempotent_when_never_started():
    a = TelegramAdapter(
        bot_token="t", allowed_chat_ids=[], allowed_user_ids=[],
    )
    await a.stop()  # 不应抛异常


@pytest.mark.asyncio
async def test_cmd_ping_replies_pong():
    """_cmd_ping 回复 pong。"""
    a = TelegramAdapter(
        bot_token="t", allowed_chat_ids=[100], allowed_user_ids=[],
    )
    upd = make_update("/ping", chat_id=100, user_id=999, message_id=1)
    ctx = MagicMock()
    ctx.bot.send_message = AsyncMock()
    await a._cmd_ping(upd, ctx)
    ctx.bot.send_message.assert_awaited_once()
    kwargs = ctx.bot.send_message.call_args.kwargs
    assert kwargs["chat_id"] == 100
    assert kwargs["text"] == "pong"
