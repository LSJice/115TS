import httpx
import respx
from fastapi.testclient import TestClient

from app.main import app


def test_feishu_test_unconfigured_returns_helpful_message(monkeypatch):
    """未配置 FEISHU_APP_ID/TOKEN → 返回 ok=False，message 说明缺什么。"""
    monkeypatch.setattr("app.api.config.settings.feishu_app_id", "")
    monkeypatch.setattr("app.api.config.settings.feishu_app_token", "")
    client = TestClient(app)
    r = client.post("/api/config/feishu/test")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "FEISHU_APP_ID" in body["message"] or "FEISHU_APP_TOKEN" in body["message"]


@respx.mock
def test_feishu_test_configured_ok(monkeypatch):
    """配置正确 + 飞书表有数据 → ok=True，message 包含首行链接预览。"""
    monkeypatch.setattr("app.api.config.settings.feishu_app_id", "id")
    monkeypatch.setattr("app.api.config.settings.feishu_app_secret", "secret")
    monkeypatch.setattr("app.api.config.settings.feishu_app_token", "app_tok")
    monkeypatch.setattr("app.api.config.settings.feishu_table_id", "tbl")
    monkeypatch.setattr("app.api.config.settings.feishu_link_column", "链接")

    respx.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal").mock(
        return_value=httpx.Response(200, json={"tenant_access_token": "tok"})
    )
    respx.get("https://open.feishu.cn/open-apis/bitable/v1/apps/app_tok/tables/tbl/records").mock(
        return_value=httpx.Response(200, json={
            "data": {"has_more": False, "items": [
                {"record_id": "r1", "fields": {"链接": "https://115.com/s/abc"}},
            ]},
        })
    )
    client = TestClient(app)
    r = client.post("/api/config/feishu/test")
    body = r.json()
    assert body["ok"] is True
    assert "https://115.com/s/abc" in body["message"]


@respx.mock
def test_feishu_test_table_not_found(monkeypatch):
    """配置错（app_token 不对）→ 飞书返回 4xx → ok=False，message 含状态码。"""
    monkeypatch.setattr("app.api.config.settings.feishu_app_id", "id")
    monkeypatch.setattr("app.api.config.settings.feishu_app_secret", "secret")
    monkeypatch.setattr("app.api.config.settings.feishu_app_token", "bad")
    monkeypatch.setattr("app.api.config.settings.feishu_table_id", "tbl")

    respx.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal").mock(
        return_value=httpx.Response(200, json={"tenant_access_token": "tok"})
    )
    respx.get("https://open.feishu.cn/open-apis/bitable/v1/apps/bad/tables/tbl/records").mock(
        return_value=httpx.Response(404, json={"msg": "table not found"})
    )
    client = TestClient(app)
    r = client.post("/api/config/feishu/test")
    body = r.json()
    assert body["ok"] is False
    assert "404" in body["message"]
