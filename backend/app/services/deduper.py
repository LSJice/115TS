from typing import Callable, Literal, Union

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.models import Task


class Deduper:
    def __init__(self, session_factory: Callable[[], Session]):
        self._session_factory = session_factory

    def is_processed(self, share_hash: str) -> Union[dict, Literal[False]]:
        """返回 {task_id, finished_at, target_path, status} 或 False（未处理过）。

        注意：未找到时返回 False（不是 None），以匹配测试断言 ``is False``。
        """
        with self._session_factory() as s:
            t = s.query(Task).filter_by(share_hash=share_hash).filter(
                Task.status.in_(["done", "skipped"])
            ).first()
            if t is None:
                return False
            return {
                "task_id": t.id,
                "finished_at": t.finished_at,
                "target_path": t.target_path,
                "status": t.status,
            }

    def mark_processed(self, share_hash: str, task_id: int) -> None:
        """标记某 task_id 对应的 share_hash 为已处理。

        通过 Task.share_hash 上的 UNIQUE 约束兜底；
        如果该 hash 已被其他 task_id 占用，抛 IntegrityError。

        TODO(T14-TaskRunner): 当前实现写入占位行（source='system', status='done'）
        以让 is_processed 能立即查到。任务 14 实现 TaskRunner 时需复核：
        1. TaskRunner 是否应负责创建真实 Task 行（包含完整字段），让 Deduper 仅查询；
        2. 或者保留 Deduper 写占位行的语义，但需要清理逻辑避免占位行污染。
        现状下，占位行写入后不会被 TaskRunner 覆盖（status 已 done），
        生产部署前必须明确这条边界。
        """
        with self._session_factory() as s:
            existing = s.query(Task).filter_by(share_hash=share_hash).first()
            if existing is not None and existing.id != task_id:
                raise IntegrityError(
                    statement="INSERT INTO tasks (share_hash)",
                    params={"share_hash": share_hash},
                    orig=Exception(f"share_hash already used by task#{existing.id}"),
                )
            if existing is None:
                # 写入占位行，status='done' 让 is_processed 能查到
                # 注：source/raw_input/share_url/created_at 是 NOT NULL 字段，
                # 这里用占位值填充（生产中由 TaskRunner 写入真实值）
                t = Task(
                    id=task_id,
                    source="system",
                    raw_input="",
                    share_url="",
                    share_hash=share_hash,
                    status="done",
                    created_at=0,
                )
                s.add(t)
                s.commit()
