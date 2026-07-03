import pytest
from pydantic_settings import SettingsConfigDict


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", "dGVzdC1rZXktMzItYnl0ZXMtbG9uZy1lbm91Z2g=")
    monkeypatch.setenv("TMDB_API_KEY", "tmdb-fake-key")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///data/test.db")
    from app.config import Settings

    s = Settings()
    assert s.encryption_key == "dGVzdC1rZXktMzItYnl0ZXMtbG9uZy1lbm91Z2g="
    assert s.tmdb_api_key == "tmdb-fake-key"
    assert str(s.database_url).endswith("test.db")


def test_feishu_poll_interval_default(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", "dGVzdC1rZXktMzItYnl0ZXMtbG9uZy1lbm91Z2g=")
    from app.config import Settings

    s = Settings()
    assert s.feishu_poll_interval_minutes == 5


def test_telegram_allowed_ids_parses_csv(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", "dGVzdC1rZXktMzItYnl0ZXMtbG9uZy1lbm91Z2g=")
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "-100123456, -100987654")
    from app.config import Settings

    s = Settings()
    assert s.telegram_allowed_chat_ids == [-100123456, -100987654]


def test_telegram_admin_user_id_defaults_zero(monkeypatch):
    """未配置时默认 0（main.py 取 allowed_user_ids[0] 兜底）。"""
    monkeypatch.delenv("TELEGRAM_ADMIN_USER_ID", raising=False)
    monkeypatch.setenv("ENCRYPTION_KEY", "dGVzdC1rZXktMzItYnl0ZXMtbG9uZy1lbm91Z2g=")
    from app.config import Settings

    s = Settings()
    assert s.telegram_admin_user_id == 0


def test_telegram_admin_user_id_loaded_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ADMIN_USER_ID", "999")
    monkeypatch.setenv("ENCRYPTION_KEY", "dGVzdC1rZXktMzItYnl0ZXMtbG9uZy1lbm91Z2g=")
    from app.config import Settings

    s = Settings()
    assert s.telegram_admin_user_id == 999
