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
@pytest.mark.parametrize("source", ["telegram", "feishu"])
async def test_pause_for_auth_bot_source_calls_tg_notify(source):
    """source in (telegram, feishu) + tg_adapter 存在 → 调 notify_auth_expired。"""
    tg = MagicMock()
    tg.notify_auth_expired = AsyncMock()
    runner = build_minimal_runner(tg_adapter=tg)

    task_mock = MagicMock()
    task_mock.id = 42
    task_mock.source = source
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


# ---------- 端到端集成（Task 11）----------


@pytest.mark.asyncio
async def test_full_pipeline_telegram_source_succeeds(tmp_path):
    """端到端：telegram 任务成功，target_path 来自 path_resolver，
    _resolve_cid 返回非 0 cid，transfer_task 收到正确参数。
    """
    from app.models import Base, Task
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{tmp_path}/e2e.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    with Session() as s:
        s.add(Task(
            id=1, source="telegram", source_ref="m1",
            raw_input="https://115.com/s/abc",
            share_url="https://115.com/s/abc", share_hash="h1",
            status="pending", created_at=0,
        ))
        s.commit()

    lm = MagicMock()
    lm.is_logged_in.return_value = True
    client = MagicMock()
    client.fs_makedirs.return_value = {"state": True, "data": {"id": 999}}
    lm.get_client.return_value = client

    share_fetcher = MagicMock()
    share_fetcher.fetch = AsyncMock(return_value=MagicMock(
        file_names=["a.mkv"], root_name="Movie.Name.2024",
    ))

    path_resolver = MagicMock()
    path_resolver.resolve = AsyncMock(return_value="/电影/Movie.Name (2024)")

    transfer_task = MagicMock()
    transfer_task.run = AsyncMock()

    runner = TaskRunner(
        session_factory=lambda: Session(),
        login_manager=lm,
        share_fetcher=share_fetcher,
        classifier=lambda files: "电影",
        metadata_scraper=None,
        path_resolver=path_resolver,
        transfer_task=transfer_task,
        broadcaster=MagicMock(),
    )
    await runner.process_once(1)

    transfer_task.run.assert_awaited_once()
    call_kwargs = transfer_task.run.call_args.kwargs
    assert call_kwargs["target_cid"] == 999

    with Session() as s:
        t = s.get(Task, 1)
        assert t.status == "done"
        assert t.target_path == "/电影/Movie.Name (2024)"


@pytest.mark.asyncio
async def test_auth_expired_telegram_source_triggers_tg_notify(tmp_path):
    """端到端：telegram 任务 AuthExpired → tg_adapter.notify_auth_expired 被调。"""
    from app.models import Base, Task
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.services.transfer_task import AuthExpiredError

    engine = create_engine(f"sqlite:///{tmp_path}/e2e2.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    with Session() as s:
        s.add(Task(
            id=1, source="telegram", source_ref="m1",
            raw_input="https://115.com/s/abc",
            share_url="https://115.com/s/abc", share_hash="h1",
            status="pending", created_at=0,
        ))
        s.commit()

    lm = MagicMock()
    lm.is_logged_in.return_value = True
    share_fetcher = MagicMock()
    share_fetcher.fetch = AsyncMock(return_value=MagicMock(
        file_names=["a.mkv"], root_name="x",
    ))
    transfer_task = MagicMock()
    transfer_task.run = AsyncMock(side_effect=AuthExpiredError("expired"))

    tg = MagicMock()
    tg.notify_auth_expired = AsyncMock()

    runner = TaskRunner(
        session_factory=lambda: Session(),
        login_manager=lm,
        share_fetcher=share_fetcher,
        classifier=lambda files: "电影",
        metadata_scraper=None,
        path_resolver=MagicMock(resolve=AsyncMock(return_value="/电影/x")),
        transfer_task=transfer_task,
        broadcaster=MagicMock(),
        tg_adapter=tg,
    )
    lm.get_client.return_value = MagicMock(
        fs_makedirs=MagicMock(return_value={"state": True, "data": {"id": 1}})
    )

    await runner.process_once(1)

    tg.notify_auth_expired.assert_awaited_once_with("expired")

    with Session() as s:
        t = s.get(Task, 1)
        assert t.status == "pending"
        assert "需重新登录" in (t.error_msg or "")
