import time
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Task


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    yield Session, engine
    engine.dispose()


def test_running_tasks_reset_to_pending(db):
    Session, _ = db
    now = int(time.time())
    with Session() as s:
        s.add_all([
            Task(source="web", raw_input="x", share_url="u1", share_hash="h1",
                 status="running", started_at=now, created_at=now),
            Task(source="web", raw_input="x", share_url="u2", share_hash="h2",
                 status="pending", created_at=now),
            Task(source="web", raw_input="x", share_url="u3", share_hash="h3",
                 status="done", finished_at=now, created_at=now),
        ])
        s.commit()

    from app.db import reset_running_to_pending
    reset_running_to_pending(Session)

    with Session() as s:
        statuses = {t.share_hash: t.status for t in s.query(Task).all()}
    assert statuses == {"h1": "pending", "h2": "pending", "h3": "done"}
