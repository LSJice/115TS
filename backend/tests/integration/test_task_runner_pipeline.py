import asyncio
import time
import pytest
from unittest.mock import MagicMock, AsyncMock

from app.models import Base, Task
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    yield Session, engine
    engine.dispose()


@pytest.fixture
def mocks():
    """mock 所有外部服务"""
    lm = MagicMock()
    lm.is_logged_in.return_value = True

    share_fetcher = MagicMock()
    share_fetcher.fetch = AsyncMock(return_value=MagicMock(
        root_name="Game.of.Thrones.S01",
        file_names=["Game.of.Thrones.S01E01.mkv", "Game.of.Thrones.S01E02.mkv"],
    ))

    classifier = MagicMock(return_value="电视剧")

    md_scraper = MagicMock()
    md_scraper.search = AsyncMock(return_value=MagicMock(
        title="权力的游戏", year=2011, kind="tv", tmdb_id=1399, seasons=1,
    ))

    path_resolver = MagicMock()
    path_resolver.resolve = AsyncMock(return_value="/电视剧/权力的游戏 (2011)")

    transfer_task = MagicMock()
    transfer_task.run = AsyncMock(return_value=MagicMock(success=True, already_in=False))

    return {
        "login_manager": lm,
        "share_fetcher": share_fetcher,
        "classifier": classifier,
        "metadata_scraper": md_scraper,
        "path_resolver": path_resolver,
        "transfer_task": transfer_task,
    }


@pytest.mark.asyncio
async def test_pipeline_success(db, mocks):
    from app.services.task_runner import TaskRunner

    Session, _ = db
    # 先插入一个 pending 任务
    with Session() as s:
        s.add(Task(
            id=1, source="web", raw_input="https://115.com/s/abc",
            share_url="https://115.com/s/abc", share_hash="hash1",
            status="pending", created_at=int(time.time()),
        ))
        s.commit()

    runner = TaskRunner(session_factory=Session, **mocks, broadcaster=MagicMock())
    runner.start()
    await runner.process_once(task_id=1)
    runner.stop()

    with Session() as s:
        t = s.get(Task, 1)
        assert t.status == "done"
        assert t.category == "电视剧"
        assert t.target_path == "/电视剧/权力的游戏 (2011)"
        assert t.finished_at is not None


@pytest.mark.asyncio
async def test_pipeline_already_processed_skips(db, mocks):
    """任务表里已是 done 状态，不应再调用任何服务"""
    from app.services.task_runner import TaskRunner

    Session, _ = db
    with Session() as s:
        s.add(Task(
            id=99, source="web", raw_input="x", share_url="u",
            share_hash="h-done", status="done", created_at=int(time.time()),
            finished_at=int(time.time()),
        ))
        s.commit()

    runner = TaskRunner(session_factory=Session, **mocks, broadcaster=MagicMock())
    await runner.process_once(task_id=99)
    runner.stop()

    mocks["share_fetcher"].fetch.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_transfer_failure_marks_failed(db, mocks):
    from app.services.task_runner import TaskRunner
    from app.services.transfer_task import TransferError

    Session, _ = db
    with Session() as s:
        s.add(Task(
            id=2, source="web", raw_input="x", share_url="u",
            share_hash="h-fail", status="pending", created_at=int(time.time()),
        ))
        s.commit()

    mocks["transfer_task"].run = AsyncMock(side_effect=TransferError("提取码错误"))

    runner = TaskRunner(session_factory=Session, **mocks, broadcaster=MagicMock())
    await runner.process_once(task_id=2)
    runner.stop()

    with Session() as s:
        t = s.get(Task, 2)
        assert t.status == "failed"
        assert "提取码" in (t.error_msg or "")


@pytest.mark.asyncio
async def test_pipeline_cookie_expired_marks_paused(db, mocks):
    from app.services.task_runner import TaskRunner
    from app.services.transfer_task import AuthExpiredError

    Session, _ = db
    with Session() as s:
        s.add(Task(
            id=3, source="web", raw_input="x", share_url="u",
            share_hash="h-paused", status="pending", created_at=int(time.time()),
        ))
        s.commit()

    mocks["transfer_task"].run = AsyncMock(side_effect=AuthExpiredError("过期"))

    bc = MagicMock()
    bc.publish = AsyncMock()
    runner = TaskRunner(session_factory=Session, **mocks, broadcaster=bc)
    await runner.process_once(task_id=3)
    runner.stop()

    with Session() as s:
        t = s.get(Task, 3)
        # Cookie 过期：状态回退到 pending（保留重试），但错误信息已记录
        assert t.status == "pending"
        assert "过期" in (t.error_msg or "")
    bc.publish.assert_called()
