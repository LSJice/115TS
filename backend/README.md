# 115 网盘自动转存 — 后端

## 快速启动

1. 复制 `.env.example` 为 `.env`，填写必要字段
2. 安装依赖：`pip install -e ".[dev]"`
3. 启动：`uvicorn app.main:app --reload`

## Plan B2 新增配置

| 字段 | 说明 |
|---|---|
| `TELEGRAM_BOT_TOKEN` | 从 @BotFather 获取 |
| `TELEGRAM_ALLOWED_USER_IDS` | 逗号分隔；至少一个 |
| `TELEGRAM_ADMIN_USER_ID` | 0 = 取 ALLOWED_USER_IDS[0] |
| `FEISHU_APP_ID` / `FEISHU_APP_SECRET` | 飞书自建应用凭证 |
| `FEISHU_APP_TOKEN` / `FEISHU_TABLE_ID` | Bitable URL 中提取 |
| `FEISHU_POLL_INTERVAL_MINUTES` | 默认 5 |

## 验证连通性

启动后访问：

- `GET /healthz` — 服务健康
- `POST /api/config/feishu/test` — 飞书连通性 + 拉一行验证

## 测试

```bash
.venv/Scripts/python.exe -m pytest -v
```
