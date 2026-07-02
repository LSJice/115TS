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

    # 认证失效的字符串关键词回退（HTTP 状态码优先，见 _is_auth_expired）
    _AUTH_EXPIRED_KEYWORDS = (
        "401", "403",
        "login", "auth",
        "登录", "过期", "失效",
    )

    # 幂等性检测的关键词（中文 + 英文回退）
    _ALREADY_IN_KEYWORDS_ZH = ("已", "网盘")
    _ALREADY_IN_KEYWORDS_EN = ("already",)

    def __init__(self, login_manager: LoginManager):
        self._lm = login_manager

    @classmethod
    def _is_auth_expired(cls, e: Exception) -> bool:
        """判断异常是否表示认证失效（Cookie 过期）。

        优先检查 HTTP 状态码属性（更可靠），字符串匹配作为回退。
        """
        # 优先：HTTP 状态码属性
        resp = getattr(e, "response", None)
        if resp is not None:
            status = getattr(resp, "status_code", None)
            if status in (401, 403):
                return True
        # 回退：字符串匹配（中英文关键词）
        msg = str(e).lower()
        return any(kw.lower() in msg for kw in cls._AUTH_EXPIRED_KEYWORDS)

    @classmethod
    def _is_already_in(cls, err: str) -> bool:
        """判断错误消息是否表示分享内容已在网盘中（幂等性场景）。"""
        # 中文关键词匹配（保持原行为）
        if all(kw in err for kw in cls._ALREADY_IN_KEYWORDS_ZH):
            return True
        # 英文回退
        err_lower = err.lower()
        if any(kw in err_lower for kw in cls._ALREADY_IN_KEYWORDS_EN):
            return True
        return False

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
            # 仅记录异常类型名，避免泄露 cookie 等敏感信息到日志
            logger.error("share_receive failed: {}", type(e).__name__)
            if self._is_auth_expired(e):
                raise AuthExpiredError(str(e)) from e
            raise TransferError(str(e)) from e
        if not resp.get("state", False):
            err = resp.get("error", "")
            if "提取码" in err or "password" in err.lower():
                raise TransferError(f"提取码错误: {err}")
            if self._is_already_in(err):
                return TransferResult(success=True, already_in=True, raw=resp)
            raise TransferError(err)
        data = resp.get("data", {}) or {}
        already = bool(data.get("already_in", False))
        return TransferResult(success=True, already_in=already, raw=resp)
