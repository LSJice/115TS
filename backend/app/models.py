from sqlalchemy import Column, Integer, String, Text, Index
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(32), nullable=False)
    source_ref = Column(Text, nullable=True)
    raw_input = Column(Text, nullable=False)
    share_url = Column(Text, nullable=False)
    share_code = Column(String(64), nullable=True)
    share_hash = Column(String(128), nullable=False, unique=True)
    status = Column(String(16), nullable=False)
    category = Column(String(32), nullable=True)
    target_path = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)
    error_msg = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    created_at = Column(Integer, nullable=False)
    started_at = Column(Integer, nullable=True)
    finished_at = Column(Integer, nullable=True)

    __table_args__ = (
        Index("idx_tasks_status", "status"),
    )


class AuthState(Base):
    __tablename__ = "auth_state"

    key = Column(String(64), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(Integer, nullable=False)


class FeishuState(Base):
    __tablename__ = "feishu_state"

    sheet_id = Column(String(64), primary_key=True)
    last_row = Column(Integer, nullable=False)
    updated_at = Column(Integer, nullable=False)
