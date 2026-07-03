"""LoginManager 单元测试：覆盖 qrcode 图片代理 + status 字段映射修复。

测试用 respx mock 115 qrcodeapi 域名，避免依赖网络。
"""
import base64
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from app.services.login_manager import LoginManager


@pytest.fixture
def lm(tmp_path, monkeypatch):
    """构造 LoginManager；mock _load_cookies 返回 None（未登录），
    _client 用 MagicMock 避免真实 P115Client 初始化。"""
    m = LoginManager(app_data_dir=str(tmp_path))
    monkeypatch.setattr(m, "_load_cookies", lambda: None)
    fake_client = MagicMock()
    fake_client.cookies = {}
    fake_client.login_qrcode_token.return_value = {
        "data": {"uid": "abc", "time": 1700000000, "sign": "xyz", "qrcode": "https://115.com/scan/dg-abc"}
    }
    fake_client.login_qrcode_scan_status.return_value = {"data": {"status": 0}}
    monkeypatch.setattr(m, "_client", fake_client)
    # 单元测试不依赖真实 DB；mock 持久化层避免与其他测试的 SQLite 状态互相污染
    monkeypatch.setattr("app.services.login_manager._upsert_qr_payload", lambda d: None)
    monkeypatch.setattr("app.services.login_manager._load_qr_payload", lambda: None)
    return m


@respx.mock
async def test_start_qrcode_returns_data_uri_png(lm):
    """start_qrcode_login 返回 data:image/png;base64,...（不是 115 scan 页面 URL）。"""
    # Mock token 接口
    respx.get("https://qrcodeapi.115.com/api/1.0/web/1.0/token/").mock(
        return_value=httpx.Response(200, json={
            "state": True, "code": 0, "message": "",
            "data": {
                "uid": "abc123",
                "time": 1700000000,
                "sign": "deadbeef",
                "qrcode": "https://115.com/scan/dg-abc123",  # 故意是 HTML 页面 URL
            }
        })
    )
    # Mock 图片接口
    fake_png = b"\x89PNG\r\n\x1a\nFAKE_PNG_BYTES"
    respx.get("https://qrcodeapi.115.com/api/1.0/web/1.0/qrcode").mock(
        return_value=httpx.Response(200, content=fake_png, headers={"content-type": "image/png"})
    )

    status = await lm.start_qrcode_login()

    assert status.state == "waiting"
    assert status.qrcode_url is not None
    assert status.qrcode_url.startswith("data:image/png;base64,")
    # 验证 base64 解码后是原 PNG 字节
    b64_part = status.qrcode_url.split(",", 1)[1]
    assert base64.b64decode(b64_part) == fake_png


@respx.mock
async def test_start_qrcode_image_fetch_failure_returns_error(lm):
    """图片接口返回 500 → 返回 state=error，不抛异常。"""
    respx.get("https://qrcodeapi.115.com/api/1.0/web/1.0/token/").mock(
        return_value=httpx.Response(200, json={
            "data": {"uid": "x", "time": 1, "sign": "y", "qrcode": "https://115.com/scan/dg-x"}
        })
    )
    respx.get("https://qrcodeapi.115.com/api/1.0/web/1.0/qrcode").mock(
        return_value=httpx.Response(500, text="server error")
    )

    status = await lm.start_qrcode_login()

    assert status.state == "error"
    assert status.qrcode_url is None


async def test_poll_status_waiting(lm, monkeypatch):
    """status=0 → waiting。"""
    monkeypatch.setattr(
        "app.services.login_manager._load_qr_payload",
        lambda: {"uid": "x", "time": 1, "sign": "y"},
    )
    lm._client.login_qrcode_scan_status.return_value = {"data": {"status": 0}}
    status = await lm.poll_qrcode_status()
    assert status.state == "waiting"


async def test_poll_status_scanned(lm, monkeypatch):
    """status=1 → scanned。"""
    monkeypatch.setattr(
        "app.services.login_manager._load_qr_payload",
        lambda: {"uid": "x", "time": 1, "sign": "y"},
    )
    lm._client.login_qrcode_scan_status.return_value = {"data": {"status": 1}}
    status = await lm.poll_qrcode_status()
    assert status.state == "scanned"


async def test_poll_status_expired(lm, monkeypatch):
    """status=-1 → expired。"""
    monkeypatch.setattr(
        "app.services.login_manager._load_qr_payload",
        lambda: {"uid": "x", "time": 1, "sign": "y"},
    )
    lm._client.login_qrcode_scan_status.return_value = {"data": {"status": -1}}
    status = await lm.poll_qrcode_status()
    assert status.state == "expired"


async def test_poll_status_cancel(lm, monkeypatch):
    """status=-2 → expired（取消归类为过期）。"""
    monkeypatch.setattr(
        "app.services.login_manager._load_qr_payload",
        lambda: {"uid": "x", "time": 1, "sign": "y"},
    )
    lm._client.login_qrcode_scan_status.return_value = {"data": {"status": -2}}
    status = await lm.poll_qrcode_status()
    assert status.state == "expired"


async def test_poll_status_success_saves_cookies(lm, monkeypatch):
    """status=2 → confirmed + 调用 _save_cookies。"""
    monkeypatch.setattr(
        "app.services.login_manager._load_qr_payload",
        lambda: {"uid": "x", "time": 1, "sign": "y"},
    )
    lm._client.login_qrcode_scan_status.return_value = {"data": {"status": 2}}
    lm._client.cookies = {"UID": "abc", "CID": "def"}

    saved = {}
    monkeypatch.setattr(lm, "_save_cookies", lambda c: saved.update(c))

    status = await lm.poll_qrcode_status()

    assert status.state == "confirmed"
    assert saved == {"UID": "abc", "CID": "def"}


async def test_poll_status_no_qr_payload_returns_error(lm, monkeypatch):
    """无活跃会话（_load_qr_payload 返回 None）→ error。"""
    monkeypatch.setattr(
        "app.services.login_manager._load_qr_payload", lambda: None
    )
    status = await lm.poll_qrcode_status()
    assert status.state == "error"
