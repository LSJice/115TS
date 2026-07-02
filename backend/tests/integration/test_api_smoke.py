import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch, tmp_path):
    db_file = tmp_path / "test-smoke.db"
    monkeypatch.setenv("ENCRYPTION_KEY", "dGVzdC1rZXktMzItYnl0ZXMtbG9uZy1lbm91Z2g=")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    # 阻止 TaskRunner worker 真实运行：冒烟测试只验证 API 层，
    # 不应触发 share_fetcher / transfer_task 等真实外部调用
    import app.services.task_runner as runner_mod
    monkeypatch.setattr(runner_mod.TaskRunner, "start", lambda self: None)
    # 重置已缓存的 settings（reload 后读取新环境变量）
    from importlib import reload
    import app.config
    reload(app.config)
    from app import db as db_mod
    db_mod._engine = None
    db_mod._SessionLocal = None
    import app.main
    reload(app.main)
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True


def test_create_task_invalid_link_rejected(client):
    r = client.post("/api/tasks", json={"raw_input": "no link here"})
    assert r.status_code == 400


def test_create_task_parses_link(client):
    r = client.post("/api/tasks", json={"raw_input": "https://115.com/s/abc123?password=xyz"})
    assert r.status_code == 200
    body = r.json()
    assert body["share_url"].endswith("/abc123")
    assert body["status"] == "pending"


def test_duplicate_link_returns_same_task(client):
    payload = {"raw_input": "https://115.com/s/dup456?password=p"}
    r1 = client.post("/api/tasks", json=payload)
    r2 = client.post("/api/tasks", json=payload)
    assert r1.json()["id"] == r2.json()["id"]


def test_list_tasks_pagination(client):
    for i in range(5):
        client.post("/api/tasks", json={"raw_input": f"https://115.com/s/x{i}?password=p"})
    r = client.get("/api/tasks", params={"limit": 3})
    body = r.json()
    assert len(body) <= 3


def test_history_empty(client):
    r = client.get("/api/history")
    assert r.status_code == 200
    assert r.json() == []


def test_config_masked(client):
    r = client.get("/api/config")
    body = r.json()
    # 未配置时是空串；有值则应脱敏
    if body["tmdb_api_key"]:
        assert "*" in body["tmdb_api_key"]
