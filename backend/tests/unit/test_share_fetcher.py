import pytest
from unittest.mock import MagicMock


def make_login_manager_mock(resp_data: dict):
    lm = MagicMock()
    client = MagicMock()
    client.share_snap = MagicMock(return_value=resp_data)
    lm.get_client.return_value = client
    lm.is_logged_in.return_value = True
    return lm


@pytest.mark.asyncio
async def test_fetch_returns_root_name_and_filenames():
    from tests.fixtures.p115_responses import SHARE_CONTENT_GOT
    from app.services.share_fetcher import ShareFetcher, ShareContent

    lm = make_login_manager_mock(SHARE_CONTENT_GOT)
    fetcher = ShareFetcher(lm)
    content = await fetcher.fetch(share_id="abc", password="xyz")
    assert isinstance(content, ShareContent)
    assert content.root_name == "Game.of.Thrones.Complete"
    assert content.file_names == ["Game.of.Thrones.S01E01.mkv", "Game.of.Thrones.S01E02.mkv"]


@pytest.mark.asyncio
async def test_fetch_no_password_omits_password_param():
    from tests.fixtures.p115_responses import SHARE_CONTENT_FLAT
    from app.services.share_fetcher import ShareFetcher

    lm = make_login_manager_mock(SHARE_CONTENT_FLAT)
    fetcher = ShareFetcher(lm)
    await fetcher.fetch(share_id="abc", password=None)
    args, kwargs = lm.get_client.return_value.share_snap.call_args
    # share_snap 的第一个位置参数是 payload dict；无密码时不应包含 receive_code
    payload = args[0] if args else kwargs.get("payload", {})
    assert "receive_code" not in payload


@pytest.mark.asyncio
async def test_fetch_handles_error_state():
    from app.services.share_fetcher import ShareFetcher, ShareFetchError

    lm = make_login_manager_mock({"state": False, "error": "invalid share"})
    fetcher = ShareFetcher(lm)
    with pytest.raises(ShareFetchError):
        await fetcher.fetch(share_id="bad", password=None)


@pytest.mark.asyncio
async def test_fetch_wraps_client_exception():
    """share_snap 抛异常时包装为 ShareFetchError。"""
    from app.services.share_fetcher import ShareFetcher, ShareFetchError

    lm = MagicMock()
    client = MagicMock()
    client.share_snap = MagicMock(side_effect=RuntimeError("network down"))
    lm.get_client.return_value = client
    lm.is_logged_in.return_value = True

    fetcher = ShareFetcher(lm)
    with pytest.raises(ShareFetchError):
        await fetcher.fetch(share_id="abc", password=None)


@pytest.mark.asyncio
async def test_fetch_empty_file_list_returns_empty_names():
    """file_list 为空时返回空列表，root_name 回退到 share_id。"""
    from app.services.share_fetcher import ShareFetcher

    lm = make_login_manager_mock({"data": {"file_name": "x"}, "state": True})
    fetcher = ShareFetcher(lm)
    content = await fetcher.fetch(share_id="abc", password=None)
    assert content.file_names == []
    assert content.root_name == "x"


@pytest.mark.asyncio
async def test_fetch_data_none_uses_share_id_as_root():
    """data 为 None 时 root_name 回退到 share_id。"""
    from app.services.share_fetcher import ShareFetcher

    lm = make_login_manager_mock({"state": True, "data": None})
    fetcher = ShareFetcher(lm)
    content = await fetcher.fetch(share_id="abc", password=None)
    assert content.root_name == "abc"
    assert content.file_names == []
