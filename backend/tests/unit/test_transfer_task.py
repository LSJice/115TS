import pytest
from unittest.mock import MagicMock


def make_lm_mock(share_receive_resp: dict):
    lm = MagicMock()
    client = MagicMock()
    client.share_receive = MagicMock(return_value=share_receive_resp)
    lm.get_client.return_value = client
    lm.is_logged_in.return_value = True
    return lm


@pytest.mark.asyncio
async def test_transfer_success():
    from app.services.transfer_task import TransferTask, TransferResult

    lm = make_lm_mock(share_receive_resp={"state": True, "data": {"already_in": False}})
    task = TransferTask(lm)
    result = await task.run(share_id="abc", password="xyz", target_cid=12345)
    assert isinstance(result, TransferResult)
    assert result.success is True


@pytest.mark.asyncio
async def test_transfer_already_in_is_success():
    from app.services.transfer_task import TransferTask, TransferResult

    lm = make_lm_mock(share_receive_resp={"state": True, "data": {"already_in": True, "msg": "已在网盘"}})
    task = TransferTask(lm)
    result = await task.run(share_id="abc", password="xyz", target_cid=12345)
    assert result.success is True
    assert result.already_in is True


@pytest.mark.asyncio
async def test_transfer_failure_raises():
    from app.services.transfer_task import TransferTask, TransferError

    lm = make_lm_mock(share_receive_resp={"state": False, "error": "提取码错误"})
    task = TransferTask(lm)
    with pytest.raises(TransferError):
        await task.run(share_id="abc", password="bad", target_cid=12345)


@pytest.mark.asyncio
async def test_transfer_cookie_expired_raises_auth_error():
    from app.services.transfer_task import TransferTask, AuthExpiredError

    lm = MagicMock()
    client = MagicMock()
    client.share_receive = MagicMock(side_effect=Exception("401 unauthorized"))
    lm.get_client.return_value = client
    lm.is_logged_in.return_value = True
    task = TransferTask(lm)
    with pytest.raises(AuthExpiredError):
        await task.run(share_id="abc", password=None, target_cid=12345)


@pytest.mark.asyncio
async def test_transfer_non_auth_exception_raises_transfer_error():
    """非 401 异常（如网络错误）应抛出 TransferError，而不是 AuthExpiredError。"""
    from app.services.transfer_task import TransferTask, TransferError, AuthExpiredError

    lm = MagicMock()
    client = MagicMock()
    client.share_receive = MagicMock(side_effect=RuntimeError("connection reset"))
    lm.get_client.return_value = client
    lm.is_logged_in.return_value = True
    task = TransferTask(lm)
    with pytest.raises(TransferError) as exc_info:
        await task.run(share_id="abc", password=None, target_cid=12345)
    # 确保不是 AuthExpiredError
    assert not isinstance(exc_info.value, AuthExpiredError)


@pytest.mark.asyncio
async def test_transfer_state_false_but_already_in_returns_success():
    """state=False 但错误消息含"已在网盘"应返回 already_in=True（幂等性回退路径）。"""
    from app.services.transfer_task import TransferTask, TransferResult

    lm = make_lm_mock(share_receive_resp={"state": False, "error": "该分享已在网盘中"})
    task = TransferTask(lm)
    result = await task.run(share_id="abc", password="xyz", target_cid=12345)
    assert isinstance(result, TransferResult)
    assert result.success is True
    assert result.already_in is True


@pytest.mark.asyncio
async def test_transfer_state_false_but_already_in_english_fallback():
    """state=False 但错误消息含英文 'already' 也应触发幂等性回退。"""
    from app.services.transfer_task import TransferTask, TransferResult

    lm = make_lm_mock(share_receive_resp={"state": False, "error": "file already in your drive"})
    task = TransferTask(lm)
    result = await task.run(share_id="abc", password="xyz", target_cid=12345)
    assert isinstance(result, TransferResult)
    assert result.success is True
    assert result.already_in is True
