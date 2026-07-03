"""飞书 Bitable 只读客户端。

设计要点：
- 飞书表只读共享，不做任何写入（spec §3.3）
- tenant_access_token 缓存（约 2 小时有效期），401 自动刷新重试一次
- 翻页拉取所有 records
- 字段展平：飞书字段可能是 str / list[dict({'text': ...})] / None
"""
from dataclasses import dataclass
from typing import Optional

import httpx


@dataclass
class FeishuRow:
    record_id: str
    link: str          # 链接列原文（含或不含提取码）
    code: str = ""     # 提取码（独立列）
    remark: str = ""


def _to_text(v) -> str:
    """飞书字段统一展平为字符串。"""
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        # 富文本字段：[{text: "..."}, ...]
        return "".join(
            x.get("text", "") if isinstance(x, dict) else str(x) for x in v
        )
    return str(v)


class FeishuClient:
    """飞书 Bitable 只读客户端（共享表场景）。"""

    BASE = "https://open.feishu.cn/open-apis"

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        app_token: str,
        table_id: str,
        link_column: str = "链接",
        code_column: str = "提取码",
        remark_column: str = "备注",
    ):
        self._app_id = app_id
        self._app_secret = app_secret
        self._app_token = app_token
        self._table_id = table_id
        self._cols = {
            "link": link_column,
            "code": code_column,
            "remark": remark_column,
        }
        self._tenant_token: Optional[str] = None

    async def _ensure_token(self, force_refresh: bool = False) -> str:
        if self._tenant_token and not force_refresh:
            return self._tenant_token
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(
                f"{self.BASE}/auth/v3/tenant_access_token/internal",
                json={"app_id": self._app_id, "app_secret": self._app_secret},
            )
            r.raise_for_status()
            self._tenant_token = r.json()["tenant_access_token"]
            return self._tenant_token

    async def _get_records_page(self, c: httpx.AsyncClient, params: dict) -> dict:
        """请求一页；401 → 清缓存刷 token → 重试一次。"""
        url = (
            f"{self.BASE}/bitable/v1/apps/{self._app_token}"
            f"/tables/{self._table_id}/records"
        )
        token = await self._ensure_token()
        r = await c.get(
            url, params=params, headers={"Authorization": f"Bearer {token}"}
        )
        if r.status_code == 401:
            token = await self._ensure_token(force_refresh=True)
            r = await c.get(
                url, params=params, headers={"Authorization": f"Bearer {token}"}
            )
        r.raise_for_status()
        return r.json().get("data", {})

    async def list_records(self, page_size: int = 100) -> list[FeishuRow]:
        """全量拉取（自动翻页）。"""
        rows: list[FeishuRow] = []
        page_token = None
        async with httpx.AsyncClient(timeout=15) as c:
            while True:
                params = {"page_size": page_size}
                if page_token:
                    params["page_token"] = page_token
                data = await self._get_records_page(c, params)
                for item in data.get("items", []):
                    fields = item.get("fields", {})
                    rows.append(FeishuRow(
                        record_id=item.get("record_id", ""),
                        link=_to_text(fields.get(self._cols["link"])),
                        code=_to_text(fields.get(self._cols["code"])),
                        remark=_to_text(fields.get(self._cols["remark"])),
                    ))
                if not data.get("has_more"):
                    break
                page_token = data.get("page_token")
        return rows
