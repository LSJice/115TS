import pytest
from unittest.mock import MagicMock
from telegram import Chat, Message, Update, User

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
