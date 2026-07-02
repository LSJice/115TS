import pytest


@pytest.fixture
def deduper(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models import Base
    from app.services.deduper import Deduper

    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    return Deduper(session_factory=Session)


def test_first_occurrence_not_seen(deduper):
    assert deduper.is_processed("hash1") is False


def test_after_record_seen(deduper):
    deduper.mark_processed(share_hash="hash1", task_id=42)
    result = deduper.is_processed("hash1")
    assert result is not None
    assert result["task_id"] == 42


def test_concurrent_insert_only_one_wins(deduper):
    from sqlalchemy.exc import IntegrityError
    deduper.mark_processed(share_hash="dup", task_id=1)
    with pytest.raises(IntegrityError):
        deduper.mark_processed(share_hash="dup", task_id=2)
