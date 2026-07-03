"""统一入队入口：parse → dedup → create Task → runner.enqueue。

Web API（tasks.create_task）和适配器（TelegramAdapter / FeishuAdapter）共用此模块，
避免 parse/dedup/create 逻辑在 3 处重复（spec §3.2 DRY 决策）。
"""
import time
from typing import Optional, Tuple

from app.db import get_session
from app.main import get_runner
from app.models import Task
from app.services.link_parser import parse


def enqueue_from_external(
    source: str,
    raw_input: str,
    source_ref: Optional[str] = None,
) -> Tuple[Optional[Task], str]:
    """统一入队入口。

    :param source: 'web' | 'telegram' | 'feishu'
    :param raw_input: 原始文本（含 115 链接 + 可选提取码）
    :param source_ref: 来源标识（TG message_id / 飞书 record_id / None）
    :return: (task_or_None, status)
        - status='created'：新任务，task 非 None
        - status='duplicate'：同 hash 已存在，task 为已存在 Task
        - status='invalid'：无法解析，task=None
    """
    link = parse(raw_input)
    if link is None:
        return None, "invalid"
    with get_session() as s:
        existing = s.query(Task).filter_by(share_hash=link.share_hash).first()
        if existing is not None:
            return existing, "duplicate"
        t = Task(
            source=source,
            source_ref=source_ref,
            raw_input=raw_input,
            share_url=f"https://115.com/s/{link.share_id}",
            share_code=link.password,
            share_hash=link.share_hash,
            status="pending",
            created_at=int(time.time()),
        )
        s.add(t)
        s.commit()
        s.refresh(t)
    runner = get_runner()
    if runner:
        runner.enqueue(t.id)
    return t, "created"
