from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.db import get_session
from app.models import Task
from app.schemas import HistoryOut

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("", response_model=List[HistoryOut])
async def list_history(
    q: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
):
    with get_session() as s:
        query = s.query(Task).filter(Task.status.in_(["done", "failed", "skipped"]))
        if q:
            like = f"%{q}%"
            query = query.filter(
                (Task.raw_input.like(like)) | (Task.target_path.like(like))
            )
        if category:
            query = query.filter(Task.category == category)
        items = query.order_by(Task.finished_at.desc()).offset(offset).limit(limit).all()
        return [HistoryOut.model_validate(i) for i in items]


@router.delete("/{task_id}")
async def delete_history(task_id: int):
    with get_session() as s:
        t = s.get(Task, task_id)
        if t is None:
            raise HTTPException(404, "not found")
        if t.status not in ("done", "failed", "skipped"):
            raise HTTPException(400, "仅允许删除已完成/失败/跳过的任务历史")
        s.delete(t)
        s.commit()
    return {"ok": True}
