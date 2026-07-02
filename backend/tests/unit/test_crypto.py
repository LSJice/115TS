import base64
import pytest


@pytest.fixture
def crypto_with_key(monkeypatch):
    key = base64.b64encode(b"0123456789abcdef0123456789abcdef").decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    from importlib import reload
    import app.utils.crypto
    reload(app.utils.crypto)
    from app.utils.crypto import encrypt, decrypt
    return encrypt, decrypt


def test_round_trip(crypto_with_key):
    encrypt, decrypt = crypto_with_key
    cipher = encrypt("hello 世界")
    assert cipher != "hello 世界"
    assert decrypt(cipher) == "hello 世界"


def test_decrypt_invalid_returns_none(crypto_with_key):
    encrypt, decrypt = crypto_with_key
    assert decrypt("not-a-valid-token") is None


def test_empty_key_returns_plaintext(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", "")
    from importlib import reload
    import app.utils.crypto
    reload(app.utils.crypto)
    from app.utils.crypto import encrypt, decrypt
    assert encrypt("x") == "x"
    assert decrypt("x") == "x"
