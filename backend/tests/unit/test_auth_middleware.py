import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def build_app(token: str):
    from app.utils.auth_middleware import BearerTokenMiddleware
    app = FastAPI()
    app.add_middleware(BearerTokenMiddleware, expected_token=token)
    app.routes.clear()
    from fastapi import APIRouter
    r = APIRouter()

    @r.get("/api/ping")
    def ping():
        return {"ok": True}

    @r.get("/healthz")
    def health():
        return {"ok": True}

    app.include_router(r)
    return app


def test_no_token_required_when_unconfigured():
    app = build_app(token="")
    client = TestClient(app)
    r = client.get("/api/ping")
    assert r.status_code == 200


def test_missing_token_returns_401():
    app = build_app(token="secret")
    client = TestClient(app)
    r = client.get("/api/ping")
    assert r.status_code == 401


def test_wrong_token_returns_401():
    app = build_app(token="secret")
    client = TestClient(app)
    r = client.get("/api/ping", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401


def test_correct_token_passes():
    app = build_app(token="secret")
    client = TestClient(app)
    r = client.get("/api/ping", headers={"Authorization": "Bearer secret"})
    assert r.status_code == 200


def test_healthz_bypasses_auth():
    app = build_app(token="secret")
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
