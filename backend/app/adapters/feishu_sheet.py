"""飞书适配器：APScheduler 周期拉表 → task_service 入队。

设计要点：
- max_instances=1 + coalesce=True：避免重叠执行和堆积
- 飞书表只读共享：不做任何写入
- poll_once 内吞 list_records 异常，避免拖垮 scheduler
"""
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from app.adapters.feishu_client import FeishuClient
from app.services import task_service


class FeishuAdapter:
    """APScheduler 周期拉飞书表 → task_service 入队。"""

    def __init__(
        self,
        client: FeishuClient,
        interval_minutes: int,
        tg_adapter=None,
    ):
        self._client = client
        self._interval = interval_minutes
        self._tg = tg_adapter  # 兜底推送 AuthExpired（飞书表只读，无法写回）
        self._scheduler: Optional[AsyncIOScheduler] = None

    async def poll_once(self):
        """单次轮询：拉全量 + 逐行入队。"""
        try:
            rows = await self._client.list_records()
        except Exception as e:
            logger.error("feishu poll failed: {}", type(e).__name__)
            return
        for row in rows:
            if not row.link:
                continue
            raw = row.link if not row.code else f"{row.link} 提取码: {row.code}"
            try:
                task_service.enqueue_from_external(
                    source="feishu",
                    raw_input=raw,
                    source_ref=row.record_id,
                )
            except Exception as e:
                logger.error(
                    "feishu enqueue failed for {}: {}",
                    row.record_id, type(e).__name__,
                )

    def start_scheduler(self):
        self._scheduler = AsyncIOScheduler()
        self._scheduler.add_job(
            self.poll_once,
            IntervalTrigger(minutes=self._interval),
            id="feishu_poll",
            max_instances=1,
            coalesce=True,
        )
        self._scheduler.start()
        logger.info(
            "FeishuAdapter scheduler started (interval={}min)", self._interval
        )

    def stop_scheduler(self):
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
