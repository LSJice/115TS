import pytest
from unittest.mock import MagicMock, patch

from app.db import get_session
from app.models import Task
from app.services import task_service


@pytest.fixture
def clean_db(tmp_path, monkeypatch):
    """每个测试用临时 sqlite，避免互相污染。"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models import Base
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr("app.services.task_service.get_session", lambda: Session())
    return Session


def test_enqueue_invalid_link_returns_none(clean_db):
    task, status = task_service.enqueue_from_external(
        source="telegram", raw_input="not a link"
    )
    assert task is None
    assert status == "invalid"


def test_enqueue_creates_new_task(clean_db):
    with patch("app.services.task_service.get_runner", return_value=MagicMock()):
        task, status = task_service.enqueue_from_external(
            source="telegram",
            raw_input="https://115.com/s/abc1234 提取码: xyz",
            source_ref="msg42",
        )
    assert status == "created"
    assert task is not None
    assert task.source == "telegram"
    assert task.source_ref == "msg42"
    assert task.status == "pending"
    assert task.share_url == "https://115.com/s/abc1234"
    assert task.share_code == "xyz"


def test_enqueue_duplicate_returns_existing(clean_db):
    with patch("app.services.task_service.get_runner", return_value=MagicMock()):
        t1, s1 = task_service.enqueue_from_external(
            source="web", raw_input="https://115.com/s/abc1234",
        )
        t2, s2 = task_service.enqueue_from_external(
            source="feishu",
            raw_input="https://115.com/s/abc1234 提取码: xyz",
            source_ref="rec_001",
        )
    assert s1 == "created"
    assert s2 == "duplicate"
    assert t2.id == t1.id  # 返回已存在的同一个 Task


def test_enqueue_calls_runner_enqueue(clean_db):
    runner_mock = MagicMock()
    with patch("app.services.task_service.get_runner", return_value=runner_mock):
        task, status = task_service.enqueue_from_external(
            source="web", raw_input="https://115.com/s/abc1234",
        )
    assert status == "created"
    runner_mock.enqueue.assert_called_once_with(task.id)


def test_enqueue_duplicate_does_not_call_runner(clean_db):
    """幂等：重复链接不入队（避免重复转存）。"""
    runner_mock = MagicMock()
    with patch("app.services.task_service.get_runner", return_value=runner_mock):
        task_service.enqueue_from_external(
            source="web", raw_input="https://115.com/s/abc1234",
        )
        task_service.enqueue_from_external(
            source="web", raw_input="https://115.com/s/abc1234",
        )
    assert runner_mock.enqueue.call_count == 1


def test_enqueue_runner_not_ready_still_creates_task(clean_db):
    """get_runner() 返回 None（启动期/停机期）→ Task 仍正常创建，状态 created。

    Task 落库为 pending；启动后由 reset_running_to_pending 或下一次扫描处理。
    不会因 runner 缺失而丢任务。
    """
    with patch("app.services.task_service.get_runner", return_value=None):
        task, status = task_service.enqueue_from_external(
            source="telegram", raw_input="https://115.com/s/abc1234",
        )
    assert status == "created"
    assert task is not None
    assert task.status == "pending"


def test_enqueue_runner_raises_propagates_but_task_committed(clean_db):
    """runner.enqueue 抛异常 → 异常向上传播，但 Task 已 commit 为 pending。"""
    from app.models import Task
    runner_mock = MagicMock()
    runner_mock.enqueue.side_effect = RuntimeError("queue full")
    with patch("app.services.task_service.get_runner", return_value=runner_mock):
        with pytest.raises(RuntimeError, match="queue full"):
            task_service.enqueue_from_external(
                source="web", raw_input="https://115.com/s/abc1234",
            )
    # 验证 Task 已落库（不依赖 hash 计算）
    from app.services.task_service import get_session
    with get_session() as s:
        rows = s.query(Task).all()
        assert len(rows) == 1
        assert rows[0].status == "pending"
