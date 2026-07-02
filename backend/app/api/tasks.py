import time
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from sse_starlette.sse import EventSourceResponse

from app.db import get_session
from app.models import Task
from app.schemas import TaskCategoryUpdate, TaskCreate, TaskOut
from app.services.link_parser import parse
from app.utils.sse import broadcaster

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("", response_model=TaskOut)
async def create_task(body: TaskCreate):
    link = parse(body.raw_input)
    if link is None:
        raise HTTPException(400, "无法解析 115 链接")
    with get_session() as s:
        existing = s.query(Task).filter_by(share_hash=link.share_hash).first()
        if existing is not None:
            # 幂等：返回已存在任务
            return TaskOut.model_validate(existing)
        t = Task(
            source="web",
            raw_input=body.raw_input,
            share_url=f"https://115.com/s/{link.share_id}",
            share_code=link.password,
            share_hash=link.share_hash,
            status="pending",
            created_at=int(time.time()),
        )
        s.add(t)
        s.commit()
        s.refresh(t)
        # 入队
        from app.main import get_runner
        runner = get_runner()
        if runner:
            runner.enqueue(t.id)
        return TaskOut.model_validate(t)


@router.get("", response_model=List[TaskOut])
async def list_tasks(
    status: Optional[List[str]] = Query(default=None),
    limit: int = Query(default=100, le=500),
    offset: int = 0,
):
    with get_session() as s:
        q = s.query(Task)
        if status:
            q = q.filter(Task.status.in_(status))
        items = q.order_by(Task.id.desc()).offset(offset).limit(limit).all()
        return [TaskOut.model_validate(i) for i in items]


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(task_id: int):
    with get_session() as s:
        t = s.get(Task, task_id)
        if t is None:
            raise HTTPException(404, "task not found")
        return TaskOut.model_validate(t)


@router.post("/{task_id}/retry", response_model=TaskOut)
async def retry_task(task_id: int):
    with get_session() as s:
        t = s.get(Task, task_id)
        if t is None:
            raise HTTPException(404, "task not found")
        t.status = "pending"
        t.error_msg = None
        t.retry_count += 1
        s.commit()
        s.refresh(t)
        from app.main import get_runner
        runner = get_runner()
        if runner:
            runner.enqueue(t.id)
        return TaskOut.model_validate(t)


@router.put("/{task_id}/category", response_model=TaskOut)
async def update_category(task_id: int, body: TaskCategoryUpdate):
    """人工修正分类/目标路径，并重新入队转存"""
    with get_session() as s:
        t = s.get(Task, task_id)
        if t is None:
            raise HTTPException(404, "task not found")
        t.category = body.category
        if body.target_path_override:
            t.target_path = body.target_path_override
        t.status = "pending"
        t.error_msg = None
        s.commit()
        s.refresh(t)
        from app.main import get_runner
        runner = get_runner()
        if runner:
            runner.enqueue(t.id)
        return TaskOut.model_validate(t)


@router.get("/stream")
async def stream():
    """SSE 推送任务状态变更事件。

    broadcaster.publish() 接收 dict（参见 TaskRunner._notify），
    因此订阅者拿到的也是 dict，直接序列化为 JSON。
    """
    import json

    async def gen():
        async for evt in broadcaster.subscribe():
            yield {
                "event": "task",
                "data": json.dumps(evt, ensure_ascii=False),
            }

    return EventSourceResponse(gen())
