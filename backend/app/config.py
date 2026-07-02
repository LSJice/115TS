from pathlib import Path
from typing import Annotated, List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 数据库
    database_url: str = "sqlite:///data/config.db"

    # 加密
    encryption_key: str = ""

    # Web 访问控制
    web_api_token: str = ""

    # TMDB
    tmdb_api_key: str = ""
    tmdb_language: str = "zh-CN"

    # 115
    p115_app_data_dir: str = "data/p115"

    # Telegram（Plan B 用，先留配置位）
    telegram_bot_token: str = ""
    telegram_allowed_chat_ids: Annotated[List[int], NoDecode] = Field(default_factory=list)
    telegram_allowed_user_ids: Annotated[List[int], NoDecode] = Field(default_factory=list)

    # 飞书（Plan B 用）
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_app_token: str = ""
    feishu_table_id: str = ""
    feishu_link_column: str = "链接"
    feishu_code_column: str = "提取码"
    feishu_remark_column: str = "备注"
    feishu_poll_interval_minutes: int = 5

    # 日志
    log_level: str = "INFO"
    log_dir: str = "data/logs"

    @field_validator("telegram_allowed_chat_ids", "telegram_allowed_user_ids", mode="before")
    @classmethod
    def _split_csv(cls, v):
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        return v or []

    @property
    def db_path(self) -> Path:
        # sqlite:///data/config.db -> data/config.db
        return Path(self.database_url.replace("sqlite:///", "", 1))


settings = Settings()
