import asyncio
from typing import AsyncIterator, Set


class Broadcaster:
    """简单 async 事件广播器：多个订阅者，无订阅时丢弃事件。

    订阅者通过 ``subscribe()`` 拿到一个 async iterator，按需消费事件 dict。
    SSE wire 格式（``data: {...}\\n\\n``）由 API 层在推送给 HTTP 客户端时再加，
    本模块只负责事件路由。
    """

    def __init__(self) -> None:
        self._subscribers: Set[asyncio.Queue] = set()

    def subscribe(self) -> AsyncIterator[dict]:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.add(q)
        return self._iter(q)

    async def _iter(self, q: asyncio.Queue) -> AsyncIterator[dict]:
        try:
            while True:
                yield await q.get()
        finally:
            # 消费者断开 / 任务取消时清理，防止订阅者泄漏
            self._subscribers.discard(q)

    async def publish(self, event: dict) -> None:
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # 慢消费者直接丢弃事件，不阻塞其他订阅者
                pass


broadcaster = Broadcaster()
