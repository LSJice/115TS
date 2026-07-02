import pytest
from unittest.mock import MagicMock, AsyncMock


def make_lm_mock(post_save_resp: dict, offline_resp: dict | None = None):
    lm = MagicMock()
    client = MagicMock()
    client.share_receive = MagicMock(return_value=post_save_resp)
    if offline_resp is not None:
        client.officer_copy_or_save = MagicMock(return_value=offline_resp)
    lm.get_client.return_value = client
    lm.is_logged_in.return_value = True
    return lm


@pytest.mark.asyncio
async def test_transfer_success():
    from app.services.transfer_task import TransferTask, TransferResult

    lm = make_lm_mock(post_save_resp={"state": True, "data": {"already_in": False}})
    task = TransferTask(lm)
    result = await task.run(share_id="abc", password="xyz", target_cid=12345)
    assert isinstance(result, TransferResult)
    assert result.success is True


@pytest.mark.asyncio
async def test_transfer_already_in_is_success():
    from app.services.transfer_task import TransferTask, TransferResult

    lm = make_lm_mock(post_save_resp={"state": True, "data": {"already_in": True, "msg": "已在网盘"}})
    task = TransferTask(lm)
    result = await task.run(share_id="abc", password="xyz", target_cid=12345)
    assert result.success is True
    assert result.already_in is True


@pytest.mark.asyncio
async def test_transfer_failure_raises():
    from app.services.transfer_task import TransferTask, TransferError

    lm = make_lm_mock(post_save_resp={"state": False, "error": "提取码错误"})
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
