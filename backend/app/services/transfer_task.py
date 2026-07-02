from dataclasses import dataclass
from typing import Optional

from loguru import logger

from app.services.login_manager import LoginManager


class TransferError(Exception):
    pass


class AuthExpiredError(TransferError):
    """Cookie 过期，需要重新扫码"""
    pass


@dataclass
class TransferResult:
    success: bool
    already_in: bool = False
    raw: dict | None = None


class TransferTask:
    """转存分享内容到 115 网盘指定目录。

    通过 p115client 的 share_receive 方法（POST /share/receive）将分享保存到网盘。
    注意：share_receive 的第一个位置参数是 payload dict（包含 share_code/receive_code/file_id/cid），
    而非关键字参数。该方法对应官方"保存到我的网盘"接口。
    """

    POLL_INTERVAL = 2.0
    POLL_TIMEOUT = 30 * 60  # 30 分钟

    def __init__(self, login_manager: LoginManager):
        self._lm = login_manager

    async def run(
        self,
        share_id: str,
        password: Optional[str],
        target_cid: int,
    ) -> TransferResult:
        client = self._lm.get_client()
        try:
            # share_receive 接受位置参数 payload dict（参考 share_snap 调用模式）
            # file_id=0 表示接收整个分享根目录
            payload: dict = {
                "share_code": share_id,
                "file_id": 0,
                "cid": target_cid,
            }
            if password:
                payload["receive_code"] = password
            resp = client.share_receive(payload)
        except Exception as e:
            msg = str(e).lower()
            if "401" in msg or "login" in msg or "auth" in msg:
                raise AuthExpiredError(str(e)) from e
            raise TransferError(str(e)) from e
        if not resp.get("state", False):
            err = resp.get("error", "")
            if "提取码" in err or "password" in err.lower():
                raise TransferError(f"提取码错误: {err}")
            if "已" in err and "网盘" in err:
                return TransferResult(success=True, already_in=True, raw=resp)
            raise TransferError(err)
        data = resp.get("data", {}) or {}
        already = bool(data.get("already_in", False))
        return TransferResult(success=True, already_in=already, raw=resp)
