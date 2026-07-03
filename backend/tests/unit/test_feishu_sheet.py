import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.adapters.feishu_client import FeishuRow
from app.adapters.feishu_sheet import FeishuAdapter


@pytest.mark.asyncio
async def test_poll_once_enqueues_all_rows_with_code():
    client = MagicMock()
    client.list_records = AsyncMock(return_value=[
        FeishuRow(record_id="r1", link="https://115.com/s/a", code="x"),
        FeishuRow(record_id="r2", link="https://115.com/s/b", code=""),
    ])
    a = FeishuAdapter(client=client, interval_minutes=5)
    with patch("app.adapters.feishu_sheet.task_service") as ts:
        ts.enqueue_from_external.return_value = (MagicMock(), "created")
        await a.poll_once()
    assert ts.enqueue_from_external.call_count == 2
    first_call = ts.enqueue_from_external.call_args_list[0]
    assert first_call.kwargs["source"] == "feishu"
    assert first_call.kwargs["source_ref"] == "r1"
    assert "提取码: x" in first_call.kwargs["raw_input"]
    second_call = ts.enqueue_from_external.call_args_list[1]
    assert second_call.kwargs["source_ref"] == "r2"
    assert "提取码" not in second_call.kwargs["raw_input"]


@pytest.mark.asyncio
async def test_poll_once_skips_empty_link():
    client = MagicMock()
    client.list_records = AsyncMock(return_value=[
        FeishuRow(record_id="r1", link=""),  # 空链接
        FeishuRow(record_id="r2", link="https://115.com/s/b"),
    ])
    a = FeishuAdapter(client=client, interval_minutes=5)
    with patch("app.adapters.feishu_sheet.task_service") as ts:
        ts.enqueue_from_external.return_value = (MagicMock(), "created")
        await a.poll_once()
    assert ts.enqueue_from_external.call_count == 1


@pytest.mark.asyncio
async def test_poll_once_swallows_client_exception():
    """飞书异常不抛出（仅 log），等下次轮询自动恢复（spec §7.1）。"""
    client = MagicMock()
    client.list_records = AsyncMock(side_effect=RuntimeError("network down"))
    a = FeishuAdapter(client=client, interval_minutes=5)
    # 不应抛
    await a.poll_once()


@pytest.mark.asyncio
async def test_poll_once_swallows_enqueue_exception():
    """单行入队失败不影响后续行（log + continue）。"""
    client = MagicMock()
    client.list_records = AsyncMock(return_value=[
        FeishuRow(record_id="r1", link="https://115.com/s/a"),
        FeishuRow(record_id="r2", link="https://115.com/s/b"),
    ])
    a = FeishuAdapter(client=client, interval_minutes=5)
    with patch("app.adapters.feishu_sheet.task_service") as ts:
        ts.enqueue_from_external.side_effect = [
            RuntimeError("db locked"),
            (MagicMock(), "created"),
        ]
        await a.poll_once()
    assert ts.enqueue_from_external.call_count == 2


def test_start_scheduler_registers_job():
    a = FeishuAdapter(client=MagicMock(), interval_minutes=5)
    with patch("app.adapters.feishu_sheet.AsyncIOScheduler") as Sched:
        sched = MagicMock()
        Sched.return_value = sched
        a.start_scheduler()
    Sched.assert_called_once()
    sched.add_job.assert_called_once()
    job_kwargs = sched.add_job.call_args.kwargs
    assert job_kwargs["id"] == "feishu_poll"
    assert job_kwargs["max_instances"] == 1
    assert job_kwargs["coalesce"] is True
    sched.start.assert_called_once()
    assert a._scheduler is sched


def test_start_scheduler_idempotent_when_already_started():
    """重复 start 不创建第二个 scheduler（避免生命周期泄漏）。"""
    a = FeishuAdapter(client=MagicMock(), interval_minutes=5)
    with patch("app.adapters.feishu_sheet.AsyncIOScheduler") as Sched:
        first_sched = MagicMock()
        Sched.return_value = first_sched
        a.start_scheduler()
        a.start_scheduler()  # 第二次应被忽略
    Sched.assert_called_once()
    assert a._scheduler is first_sched


def test_start_scheduler_swallows_start_exception():
    """scheduler.start() 抛错时不污染 _scheduler 字段。"""
    a = FeishuAdapter(client=MagicMock(), interval_minutes=5)
    with patch("app.adapters.feishu_sheet.AsyncIOScheduler") as Sched:
        sched = MagicMock()
        sched.start.side_effect = RuntimeError("boom")
        Sched.return_value = sched
        a.start_scheduler()  # 不抛
    assert a._scheduler is None


def test_stop_scheduler_shutdown():
    a = FeishuAdapter(client=MagicMock(), interval_minutes=5)
    sched = MagicMock()
    a._scheduler = sched
    a.stop_scheduler()
    sched.shutdown.assert_called_once_with(wait=False)
    assert a._scheduler is None


def test_stop_scheduler_idempotent_when_not_started():
    a = FeishuAdapter(client=MagicMock(), interval_minutes=5)
    a.stop_scheduler()  # 不抛
