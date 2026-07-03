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
            if plain is None:
                logger.warning("cookie row exists but decrypt returned None (key rotated or corrupted?)")
                return None
            try:
                return json.loads(plain)
            except json.JSONDecodeError:
                logger.warning("cookie row exists but JSON decode failed")
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

    def get_client(self) -> "P115Client":
        if self._client is not None:
            return self._client
        from p115client import P115Client

        cookies = self._load_cookies()
        client = P115Client(cookies=cookies or None, app="web", console_qrcode=False)
        self._client = client
        return client

    async def start_qrcode_login(self) -> QRStatus:
        """启动一次扫码登录，返回二维码 PNG 的 data URI。

        115 的 token 接口返回的 data.qrcode 是扫码引导页面（HTML），
        不是图片本身。真正的图片在 /api/1.0/web/1.0/qrcode?uid=&time=&sign=。
        后端代理拉取后转 base64 data URI，避免前端跨域 / 误把 HTML 当图片。

        直接用 httpx 调 token 接口，不依赖 P115Client —— 后者在 cookies=None
        时会强制触发自动登录流程，与扫码登录语义冲突。
        """
        import base64

        import httpx

        try:
            token_resp = httpx.get(
                "https://qrcodeapi.115.com/api/1.0/web/1.0/token/",
                params={"app": "web"},
                timeout=10,
            )
            token_resp.raise_for_status()
            token_json = token_resp.json()
            data = (token_json or {}).get("data") or {}
            uid = data.get("uid")
            ts = data.get("time")
            sign = data.get("sign")
            if not (uid and ts and sign):
                return QRStatus(state="error", message="二维码响应缺少 uid/time/sign")
            img_url = "https://qrcodeapi.115.com/api/1.0/web/1.0/qrcode"
            img_resp = httpx.get(
                img_url,
                params={"uid": uid, "time": ts, "sign": sign},
                timeout=10,
            )
            img_resp.raise_for_status()
            b64 = base64.b64encode(img_resp.content).decode("ascii")
            data_uri = f"data:image/png;base64,{b64}"
            # 持久化整个 data（含 uid/time/sign，轮询时需要）
            _upsert_qr_payload(data)
            return QRStatus(state="waiting", qrcode_url=data_uri)
        except Exception as e:
            logger.error("start_qrcode_login failed: {}", type(e).__name__)
            return QRStatus(state="error", message=str(e))

    async def poll_qrcode_status(self) -> QRStatus:
        client = self.get_client()
        payload = _load_qr_payload()
        if payload is None:
            return QRStatus(state="error", message="无活跃的二维码会话")
        try:
            resp = client.login_qrcode_scan_status(payload)
            # 115 接口字段：data.status（不是 data.code）
            # 映射：0=waiting, 1=scanned, 2=success, -1=expired, -2=cancel
            status = (resp.get("data") or {}).get("status")
            if status == 2:
                cookies = client.cookies
                # 优先用 requests.utils.dict_from_cookiejar（处理 RequestsCookieJar）
                try:
                    from requests.utils import dict_from_cookiejar
                    cookies_dict = dict_from_cookiejar(cookies)
                except Exception:
                    # 兜底尝试 dict()
                    try:
                        cookies_dict = dict(cookies)
                    except (TypeError, ValueError) as e:
                        logger.error("login confirmed but cookies conversion failed: {}", type(e).__name__)
                        return QRStatus(state="error", message="cookies 转换失败")
                self._save_cookies(cookies_dict)
                return QRStatus(state="confirmed", message="登录成功")
            if status == 1:
                return QRStatus(state="scanned", message="已扫码，请在手机确认")
            if status == 0:
                return QRStatus(state="waiting", message="等待扫码")
            if status == -1:
                return QRStatus(state="expired", message="二维码过期")
            if status == -2:
                return QRStatus(state="expired", message="已取消")
            return QRStatus(state="error", message=f"未知 status={status}")
        except Exception as e:
            logger.error("poll_qrcode_status failed: {}", type(e).__name__)
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
