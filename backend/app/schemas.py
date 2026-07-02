from typing import Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field


T = TypeVar("T")


class Paginated(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int


# ---------- Auth ----------
class QRStartResp(BaseModel):
    qrcode_url: str
    state: str


class QRStatusResp(BaseModel):
    state: str
    message: str = ""


class AuthCheckResp(BaseModel):
    logged_in: bool


# ---------- Tasks ----------
class TaskCreate(BaseModel):
    raw_input: str = Field(..., description="原始提交内容（含 115 链接）")


class TaskOut(BaseModel):
    id: int
    source: str
    raw_input: str
    share_url: str
    share_code: Optional[str]
    status: str
    category: Optional[str]
    target_path: Optional[str]
    error_msg: Optional[str]
    retry_count: int
    created_at: int
    started_at: Optional[int]
    finished_at: Optional[int]

    class Config:
        from_attributes = True


class TaskCategoryUpdate(BaseModel):
    category: str
    target_path_override: Optional[str] = None


# ---------- History ----------
class HistoryOut(TaskOut):
    pass


# ---------- Config ----------
class ConfigOut(BaseModel):
    tmdb_api_key: str  # 已脱敏
    tmdb_language: str
    feishu_app_id: str
    feishu_app_token: str
    feishu_table_id: str
    feishu_link_column: str
    feishu_code_column: str
    feishu_remark_column: str
    feishu_poll_interval_minutes: int
    telegram_allowed_chat_ids: List[int]
    telegram_allowed_user_ids: List[int]


class ConfigUpdate(BaseModel):
    tmdb_api_key: Optional[str] = None
    tmdb_language: Optional[str] = None
    feishu_app_id: Optional[str] = None
    feishu_app_secret: Optional[str] = None
    feishu_app_token: Optional[str] = None
    feishu_table_id: Optional[str] = None
    feishu_link_column: Optional[str] = None
    feishu_code_column: Optional[str] = None
    feishu_remark_column: Optional[str] = None
    feishu_poll_interval_minutes: Optional[int] = None
    telegram_allowed_chat_ids: Optional[List[int]] = None
    telegram_allowed_user_ids: Optional[List[int]] = None


class FeishuTestResp(BaseModel):
    ok: bool
    message: str
