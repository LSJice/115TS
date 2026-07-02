from fastapi import APIRouter

from app.config import settings
from app.schemas import ConfigOut, ConfigUpdate, FeishuTestResp
from app.utils.crypto import encrypt

router = APIRouter(prefix="/api/config", tags=["config"])


def _mask(s: str) -> str:
    if not s or len(s) <= 4:
        return "*" * len(s) if s else ""
    return s[:2] + "*" * (len(s) - 4) + s[-2:]


@router.get("", response_model=ConfigOut)
async def get_config():
    return ConfigOut(
        tmdb_api_key=_mask(settings.tmdb_api_key),
        tmdb_language=settings.tmdb_language,
        feishu_app_id=_mask(settings.feishu_app_id),
        feishu_app_token=_mask(settings.feishu_app_token),
        feishu_table_id=settings.feishu_table_id,
        feishu_link_column=settings.feishu_link_column,
        feishu_code_column=settings.feishu_code_column,
        feishu_remark_column=settings.feishu_remark_column,
        feishu_poll_interval_minutes=settings.feishu_poll_interval_minutes,
        telegram_allowed_chat_ids=settings.telegram_allowed_chat_ids,
        telegram_allowed_user_ids=settings.telegram_allowed_user_ids,
    )


@router.put("", response_model=ConfigOut)
async def update_config(body: ConfigUpdate):
    """Plan A 简化：仅更新 .env 文件中的非空字段并提示重启。
    Plan C 完善：热加载 + 持久化。"""
    data = body.model_dump(exclude_none=True)
    # 敏感字段加密后再写
    if "feishu_app_secret" in data:
        data["feishu_app_secret"] = encrypt(data["feishu_app_secret"])
    # 写 .env.override 文件供下次启动读取
    from pathlib import Path
    override = Path(".env.override")
    with override.open("a", encoding="utf-8") as f:
        for k, v in data.items():
            f.write(f"{k.upper()}={v}\n")
    return await get_config()


@router.post("/feishu/test", response_model=FeishuTestResp)
async def test_feishu():
    """Plan B 实现：实际调用飞书 API 验证连通性"""
    return FeishuTestResp(ok=False, message="Plan B 中实现")
