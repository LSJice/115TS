import base64
import os

from cryptography.fernet import Fernet, InvalidToken


def _get_key() -> bytes | None:
    raw = os.getenv("ENCRYPTION_KEY", "").strip()
    if not raw:
        return None
    try:
        return base64.b64decode(raw)
    except Exception:
        return None


def _get_fernet() -> Fernet | None:
    key = _get_key()
    if key is None or len(key) != 32:
        return None
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt(plaintext: str) -> str:
    f = _get_fernet()
    if f is None:
        return plaintext  # 未配置密钥时透传（仅开发环境）
    return f.encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt(ciphertext: str) -> str | None:
    f = _get_fernet()
    if f is None:
        return ciphertext
    try:
        return f.decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, Exception):
        return None
