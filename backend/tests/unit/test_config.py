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
