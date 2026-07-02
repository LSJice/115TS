import pytest


def create_engine_for_path(path):
    from sqlalchemy import create_engine

    return create_engine(
        f"sqlite:///{path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    from app import db as db_mod

    db_mod._engine = None
    db_mod._SessionLocal = None
    monkeypatch.setattr(
        db_mod,
        "_build_engine",
        lambda: create_engine_for_path(tmp_path / "test.db"),
    )
    db_mod.init_db()
    yield db_mod.get_session
    db_mod.drop_db()


def test_tables_created(isolated_db):
    from sqlalchemy import inspect

    from app import db as db_mod

    insp = inspect(db_mod.engine)
    tables = insp.get_table_names()
    assert "tasks" in tables
    assert "auth_state" in tables
    assert "feishu_state" in tables


def test_insert_task_and_query_by_hash(isolated_db):
    from app.models import Task

    with isolated_db() as s:
        t = Task(
            source="web",
            raw_input="https://115.com/s/abc",
            share_url="https://115.com/s/abc",
            share_hash="hash-abc",
            status="pending",
            created_at=1700000000,
        )
        s.add(t)
        s.commit()
        assert t.id is not None

    with isolated_db() as s:
        found = s.query(Task).filter_by(share_hash="hash-abc").first()
        assert found is not None
        assert found.status == "pending"


def test_share_hash_unique(isolated_db):
    from sqlalchemy.exc import IntegrityError

    from app.models import Task

    with isolated_db() as s:
        s.add(
            Task(
                source="web",
                raw_input="x",
                share_url="u1",
                share_hash="dup",
                status="pending",
                created_at=1,
            )
        )
        s.commit()

    with isolated_db() as s:
        s.add(
            Task(
                source="web",
                raw_input="x",
                share_url="u2",
                share_hash="dup",
                status="pending",
                created_at=2,
            )
        )
        with pytest.raises(IntegrityError):
            s.commit()
