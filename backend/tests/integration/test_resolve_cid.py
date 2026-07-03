import pytest
from unittest.mock import MagicMock

from app.services.task_runner import TaskRunner


def make_runner(login_manager, client_mock):
    """构造一个仅供测试 _resolve_cid 的 TaskRunner（其他依赖给 None）。"""
    login_manager.get_client.return_value = client_mock
    return TaskRunner(
        session_factory=MagicMock(),
        login_manager=login_manager,
        share_fetcher=MagicMock(),
        classifier=lambda files: "_未分类",
        metadata_scraper=None,
        path_resolver=None,
        transfer_task=None,
        broadcaster=None,
    )


@pytest.mark.asyncio
async def test_resolve_cid_path_exists_returns_existing_id():
    """路径已存在：fs_makedirs 返回 data.id，直接用作 target_cid。"""
    lm = MagicMock()
    lm.is_logged_in.return_value = True
    client = MagicMock()
    client.fs_makedirs.return_value = {
        "state": True,
        "data": {"id": 67890, "parent_id": 12345},
    }
    runner = make_runner(lm, client)
    cid = await runner._resolve_cid("/电视剧/权力的游戏 (2011)")
    assert cid == 67890
    client.fs_makedirs.assert_called_once_with("/电视剧/权力的游戏 (2011)")


@pytest.mark.asyncio
async def test_resolve_cid_path_missing_creates_and_returns_new_id():
    """路径不存在：fs_makedirs 内部自动 mkdir_p，调用方拿到的仍是最终 cid。"""
    lm = MagicMock()
    lm.is_logged_in.return_value = True
    client = MagicMock()
    client.fs_makedirs.return_value = {
        "state": True,
        "data": {"id": 99999},
    }
    runner = make_runner(lm, client)
    cid = await runner._resolve_cid("/电视剧/新剧 (2024)")
    assert cid == 99999


@pytest.mark.asyncio
async def test_resolve_cid_not_logged_in_returns_zero():
    """未登录：直接返回 0（与 Plan B1 既有行为一致，share_receive 会以 cid=0 兜底）。"""
    lm = MagicMock()
    lm.is_logged_in.return_value = False
    runner = make_runner(lm, MagicMock())
    cid = await runner._resolve_cid("/电视剧/foo")
    assert cid == 0


@pytest.mark.asyncio
async def test_resolve_cid_state_false_raises_runtime_error():
    """fs_makedirs 返回 state=False（如非法字符、权限拒绝）→ 抛 RuntimeError，不静默降级。

    依据 spec §5.5：未预期的失败不应被吞掉（避免文件悄悄落到错误目录）。
    """
    lm = MagicMock()
    lm.is_logged_in.return_value = True
    client = MagicMock()
    client.fs_makedirs.return_value = {"state": False, "error": "目录名包含非法字符"}
    runner = make_runner(lm, client)
    with pytest.raises(RuntimeError, match="fs_makedirs failed"):
        await runner._resolve_cid("/电视剧/<invalid>")


@pytest.mark.asyncio
async def test_resolve_cid_client_exception_propagates():
    """fs_makedirs 抛异常（网络/契约变化）→ 异常向上传播，不吞。

    依据 spec §5.5 + §7.1 错误矩阵：让 TaskRunner 把任务标 failed。
    """
    lm = MagicMock()
    lm.is_logged_in.return_value = True
    client = MagicMock()
    client.fs_makedirs.side_effect = RuntimeError("connection reset")
    runner = make_runner(lm, client)
    with pytest.raises(RuntimeError, match="connection reset"):
        await runner._resolve_cid("/电视剧/foo")


@pytest.mark.asyncio
async def test_resolve_cid_data_missing_id_falls_back_to_fs_dir_getid():
    """data 中无 id 字段（响应契约变化）→ 用 fs_dir_getid 复查一次，再不行抛错。"""
    lm = MagicMock()
    lm.is_logged_in.return_value = True
    client = MagicMock()
    client.fs_makedirs.return_value = {"state": True, "data": {"unrelated": 1}}
    client.fs_dir_getid.return_value = {"state": True, "data": {"id": 55555}}
    runner = make_runner(lm, client)
    cid = await runner._resolve_cid("/电视剧/foo")
    assert cid == 55555
    client.fs_dir_getid.assert_called_once()
