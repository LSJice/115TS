from dataclasses import dataclass
from typing import Optional

from loguru import logger

from app.services.login_manager import LoginManager


class ShareFetchError(Exception):
    pass


@dataclass
class ShareContent:
    root_name: str            # 分享根目录/根文件名
    file_names: list[str]     # 分享内所有文件的扁平路径（含子目录）
    raw: dict                 # 原始响应，调试用


class ShareFetcher:
    """从 115 分享链接拉取文件列表。

    通过 p115client 的 share_snap 方法（GET /share/snap）获取分享根目录下的文件。
    注意：share_snap 的第一个位置参数是 payload dict（包含 share_code/receive_code/cid/...），
    而非关键字参数。
    """

    def __init__(self, login_manager: LoginManager):
        self._lm = login_manager

    async def fetch(self, share_id: str, password: Optional[str]) -> ShareContent:
        client = self._lm.get_client()
        try:
            payload: dict = {"share_code": share_id}
            if password:
                payload["receive_code"] = password
            resp = client.share_snap(payload)
        except Exception as e:
            logger.error("share_snap failed: {}", type(e).__name__)
            raise ShareFetchError(str(e)) from e
        if not resp.get("state", False):
            raise ShareFetchError(resp.get("error", "未知错误"))
        data = resp.get("data", {}) or {}
        root_name = data.get("file_name", share_id)
        file_list = data.get("file_list", []) or []
        file_names = [f["file_name"] for f in file_list if "file_name" in f]
        return ShareContent(root_name=root_name, file_names=file_names, raw=resp)
