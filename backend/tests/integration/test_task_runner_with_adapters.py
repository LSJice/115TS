import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.task_runner import TaskRunner


def build_minimal_runner(tg_adapter=None):
    """构造最小 TaskRunner：只测 _pause_for_auth，不跑 process_once。"""
    return TaskRunner(
        session_factory=MagicMock(),
        login_manager=MagicMock(),
        share_fetcher=MagicMock(),
        tg_adapter=tg_adapter,
    )


@pytest.mark.asyncio
async def test_pause_for_auth_telegram_source_calls_tg_notify():
    """source=telegram + tg_adapter 存在 → 调 notify_auth_expired。"""
    tg = MagicMock()
    tg.notify_auth_expired = AsyncMock()
    runner = build_minimal_runner(tg_adapter=tg)

    task_mock = MagicMock()
    task_mock.id = 42
    task_mock.source = "telegram"
    session_mock = MagicMock()
    session_mock.__enter__ = MagicMock(return_value=session_mock)
    session_mock.__exit__ = MagicMock(return_value=False)
    session_mock.get.return_value = task_mock
    runner._session_factory = MagicMock(return_value=session_mock)
    runner._notify = AsyncMock()
    runner.enqueue = MagicMock()

    await runner._pause_for_auth(42, "cookie expired")

    tg.notify_auth_expired.assert_awaited_once_with("cookie expired")


@pytest.mark.asyncio
async def test_pause_for_auth_web_source_does_not_call_tg():
    """source=web → 不调 tg（前端 SSE 处理）。"""
    tg = MagicMock()
    tg.notify_auth_expired = AsyncMock()
    runner = build_minimal_runner(tg_adapter=tg)

    task_mock = MagicMock()
    task_mock.source = "web"
    session_mock = MagicMock()
    session_mock.__enter__ = MagicMock(return_value=session_mock)
    session_mock.__exit__ = MagicMock(return_value=False)
    session_mock.get.return_value = task_mock
    runner._session_factory = MagicMock(return_value=session_mock)
    runner._notify = AsyncMock()
    runner.enqueue = MagicMock()

    await runner._pause_for_auth(1, "err")
    tg.notify_auth_expired.assert_not_awaited()


@pytest.mark.asyncio
async def test_pause_for_auth_no_tg_adapter_does_not_error():
    """未注入 tg_adapter → 跳过推送，不抛。"""
    runner = build_minimal_runner(tg_adapter=None)
    task_mock = MagicMock()
    task_mock.source = "feishu"
    session_mock = MagicMock()
    session_mock.__enter__ = MagicMock(return_value=session_mock)
    session_mock.__exit__ = MagicMock(return_value=False)
    session_mock.get.return_value = task_mock
    runner._session_factory = MagicMock(return_value=session_mock)
    runner._notify = AsyncMock()
    runner.enqueue = MagicMock()

    await runner._pause_for_auth(1, "err")  # 不抛


@pytest.mark.asyncio
async def test_pause_for_auth_tg_exception_does_not_break_enqueue():
    """tg_adapter.notify_auth_expired 抛异常 → 不影响任务入队回退。"""
    tg = MagicMock()
    tg.notify_auth_expired = AsyncMock(side_effect=RuntimeError("tg down"))
    runner = build_minimal_runner(tg_adapter=tg)

    task_mock = MagicMock()
    task_mock.source = "telegram"
    session_mock = MagicMock()
    session_mock.__enter__ = MagicMock(return_value=session_mock)
    session_mock.__exit__ = MagicMock(return_value=False)
    session_mock.get.return_value = task_mock
    runner._session_factory = MagicMock(return_value=session_mock)
    runner._notify = AsyncMock()
    runner.enqueue = MagicMock()

    await runner._pause_for_auth(1, "err")
    runner.enqueue.assert_called_once_with(1)
