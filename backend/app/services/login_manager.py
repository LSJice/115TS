import json
import time
from dataclasses import dataclass
from typing import Optional

from loguru import logger

from app.db import get_session
from app.models import AuthState
from app.utils.crypto import encrypt, decrypt

COOKIE_KEY = "p115_cookies"
QR_TOKEN_KEY = "p115_qr_token"


@dataclass
class QRStatus:
    state: str  # 'waiting' | 'scanned' | 'confirmed' | 'expired' | 'error'
    qrcode_url: Optional[str] = None
    message: str = ""


class LoginManager:
    """115 网盘二维码登录与 Cookie 管理。

    Cookie 经 Fernet 加密后存入 AuthState 表。
    QR token（含 uid/time/sign）作为 JSON 存入 AuthState 表，明文（仅临时会话凭证）。
    """

    def __init__(self, app_data_dir: str):
        # app_data_dir 当前未直接传给 P115Client（其 app 参数语义为应用标识，非目录路径）。
        # 保留为成员以支持未来 cookie 文件持久化备份。
        self.app_data_dir = app_data_dir
        self._client = None

    def _load_cookies(self) -> dict | None:
        with get_session() as s:
            row = s.query(AuthState).filter_by(key=COOKIE_KEY).first()
            if row is None:
                return None
            plain = decrypt(row.value)
            try:
                return json.loads(plain) if plain else None
            except json.JSONDecodeError:
                return None

    def _save_cookies(self, cookies: dict) -> None:
        with get_session() as s:
            payload = encrypt(json.dumps(cookies))
            existing = s.query(AuthState).filter_by(key=COOKIE_KEY).first()
            now = int(time.time())
            if existing:
                existing.value = payload
                existing.updated_at = now
            else:
                s.add(AuthState(key=COOKIE_KEY, value=payload, updated_at=now))
            s.commit()

    def is_logged_in(self) -> bool:
        return self._load_cookies() is not None

    def get_client(self):
        if self._client is not None:
            return self._client
        from p115client import P115Client

        cookies = self._load_cookies()
        client = P115Client(cookies=cookies or None, app="web", console_qrcode=False)
        self._client = client
        return client

    async def start_qrcode_login(self) -> QRStatus:
        """启动一次扫码登录，返回二维码 URL。"""
        client = self.get_client()
        try:
            resp = client.login_qrcode_token(app="web")
            data = resp.get("data") or {}
            qrcode = data.get("qrcode")
            # 持久化整个 data（含 uid/time/sign，轮询时需要）
            _upsert_qr_payload(data)
            return QRStatus(state="waiting", qrcode_url=qrcode)
        except Exception as e:
            logger.exception("start_qrcode_login failed")
            return QRStatus(state="error", message=str(e))

    async def poll_qrcode_status(self) -> QRStatus:
        client = self.get_client()
        payload = _load_qr_payload()
        if payload is None:
            return QRStatus(state="error", message="无活跃的二维码会话")
        try:
            # 注意：响应字段 data.code / data.msg 基于 115 /login/qrcode/get/status/ 的常见返回结构假设；
            # 若集成测试发现不一致，在此调整解析。
            resp = client.login_qrcode_scan_status(payload)
            code = (resp.get("data") or {}).get("code")
            msg = (resp.get("data") or {}).get("msg", "")
            if code == 0:
                cookies = client.cookies
                # cookies 可能是 RequestsCookieJar/dict，统一转 dict 存储
                try:
                    cookies_dict = dict(cookies)
                except (TypeError, ValueError):
                    cookies_dict = {"raw": str(cookies)}
                self._save_cookies(cookies_dict)
                return QRStatus(state="confirmed", message="登录成功")
            if code == 1:
                return QRStatus(state="waiting", message="等待扫码")
            if code == 2:
                return QRStatus(state="scanned", message="已扫码，请在手机确认")
            if code == -1:
                return QRStatus(state="expired", message="二维码过期")
            return QRStatus(state="error", message=f"未知 code={code} msg={msg}")
        except Exception as e:
            logger.exception("poll_qrcode_status failed")
            return QRStatus(state="error", message=str(e))

    def logout(self) -> None:
        with get_session() as s:
            for k in (COOKIE_KEY, QR_TOKEN_KEY):
                row = s.query(AuthState).filter_by(key=k).first()
                if row:
                    s.delete(row)
            s.commit()
        self._client = None


def _upsert_qr_payload(data: dict) -> None:
    """将 QR token 响应 data 持久化为 JSON（明文，仅临时会话凭证）。"""
    with get_session() as s:
        existing = s.query(AuthState).filter_by(key=QR_TOKEN_KEY).first()
        now = int(time.time())
        payload = json.dumps(data)
        if existing:
            existing.value = payload
            existing.updated_at = now
        else:
            s.add(AuthState(key=QR_TOKEN_KEY, value=payload, updated_at=now))
        s.commit()


def _load_qr_payload() -> dict | None:
    with get_session() as s:
        row = s.query(AuthState).filter_by(key=QR_TOKEN_KEY).first()
        if row is None:
            return None
        try:
            return json.loads(row.value)
        except json.JSONDecodeError:
            return None
