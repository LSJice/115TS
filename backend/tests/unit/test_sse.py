import asyncio
import pytest


@pytest.mark.asyncio
async def test_subscribe_and_publish():
    from app.utils.sse import Broadcaster

    bc = Broadcaster()
    received = []

    async def consumer():
        async for evt in bc.subscribe():
            received.append(evt)
            if len(received) >= 2:
                break

    task = asyncio.create_task(consumer())
    await asyncio.sleep(0.05)
    await bc.publish({"id": 1, "status": "running"})
    await bc.publish({"id": 1, "status": "done"})
    await asyncio.wait_for(task, timeout=1.0)
    assert received == [{"id": 1, "status": "running"}, {"id": 1, "status": "done"}]


@pytest.mark.asyncio
async def test_no_subscribers_publish_doesnt_error():
    from app.utils.sse import Broadcaster

    bc = Broadcaster()
    await bc.publish({"x": 1})  # 不应抛异常
