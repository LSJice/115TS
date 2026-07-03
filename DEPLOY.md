# 部署指南

> 适用版本：Plan B2（含 Telegram Bot + 飞书 Bitable 轮询 + `_resolve_cid` 真实路径解析）

---

## 目录

- [1. 环境准备](#1-环境准备)
- [2. 配置 .env](#2-配置-env)
- [3. 后端安装与启动](#3-后端安装与启动)
- [4. 前端构建](#4-前端构建)
- [5. 首次启动后操作](#5-首次启动后操作)
- [6. 生产部署](#6-生产部署)
- [7. 升级流程](#7-升级流程)
- [8. 常见问题](#8-常见问题)
- [9. 部署后验证清单](#9-部署后验证清单)

---

## 1. 环境准备

| 组件 | 版本要求 | 用途 |
|---|---|---|
| Python | ≥ 3.11 | 后端运行时 |
| Node.js | ≥ 18 | 前端构建 |
| npm / pip | 随上述带 | 包管理 |

**目录结构：**

```
115/
├── backend/         # FastAPI 后端
│   ├── app/
│   ├── .env.example
│   └── pyproject.toml
├── frontend/        # Vue 3 + Vite 前端
│   ├── src/
│   └── package.json
└── DEPLOY.md        # 本文件
```

---

## 2. 配置 .env

```bash
cd 115/backend
cp .env.example .env
```

### 必填字段

```dotenv
# 加密密钥（32 字节 base64）— 用于加密 115 cookie 和飞书 secret
# 生成命令：python -c "import secrets,base64;print(base64.b64encode(secrets.token_bytes(32)).decode())"
ENCRYPTION_KEY=<上面命令的输出>

# 外网访问必填（局域网可空）；前端通过 Authorization: Bearer 头携带
# 生成命令：python -c "import secrets;print(secrets.token_urlsafe(32))"
WEB_API_TOKEN=<随机字符串>
```

### 可选字段（按需启用）

```dotenv
# TMDB 元数据刮削（不填则跳过 metadata_scraper，分类仍可工作）
TMDB_API_KEY=
TMDB_LANGUAGE=zh-CN

# Telegram Bot（不填则 TG 适配器跳过启动）
TELEGRAM_BOT_TOKEN=                 # @BotFather 创建 bot 后获得
TELEGRAM_ALLOWED_CHAT_IDS=          # 允许的群组 chat_id，逗号分隔
TELEGRAM_ALLOWED_USER_IDS=          # 允许的个人 user_id，至少一个
TELEGRAM_ADMIN_USER_ID=0            # 0 = 默认取 ALLOWED_USER_IDS[0]

# 飞书 Bitable 轮询（不填则飞书适配器跳过启动）
FEISHU_APP_ID=                      # 自建应用凭证
FEISHU_APP_SECRET=
FEISHU_APP_TOKEN=                   # Bitable URL 中提取
FEISHU_TABLE_ID=
FEISHU_LINK_COLUMN=链接
FEISHU_CODE_COLUMN=提取码
FEISHU_REMARK_COLUMN=备注
FEISHU_POLL_INTERVAL_MINUTES=5
```

> ⚠️ **密钥不可丢失**：`ENCRYPTION_KEY` 一旦变更，已加密的 115 cookie 和飞书 secret 都将无法解密，必须重新登录 / 重配。

---

## 3. 后端安装与启动

### 3.1 创建虚拟环境

**Windows（PowerShell / Git Bash）：**
```bash
cd 115/backend
python -m venv .venv
.venv\Scripts\activate
```

**Linux / macOS：**
```bash
cd 115/backend
python3 -m venv .venv
source .venv/bin/activate
```

### 3.2 安装依赖

```bash
pip install -e .
```

依赖列表（详见 `pyproject.toml`）：

- FastAPI + uvicorn + sse-starlette
- SQLAlchemy + pydantic v2 + pydantic-settings
- httpx + p115client（115 网盘 SDK）
- cryptography（Fernet 加密）
- python-telegram-bot v21（异步 Bot）
- APScheduler（飞书表轮询）
- loguru

### 3.3 启动（开发模式）

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

启动日志应包含：

```
TaskRunner + adapters started
```

若 TG / 飞书未配置，会看到对应的 `logger.warning` 但**不阻塞启动**。

---

## 4. 前端构建

```bash
cd 115/frontend
npm install
npm run build
```

产物输出到 `frontend/dist/`。后端 `main.py` 会自动把该目录挂载到 `/`，**无需额外配置**：

- API 路由前缀：`/api/*`、`/healthz`、`/docs`、`/openapi`
- 其他路径：返回 `frontend/dist/index.html`（SPA fallback）

> 💡 单端口架构：8000 端口同时服务 API 和前端。

---

## 5. 首次启动后操作

### 5.1 访问 Web UI

打开浏览器访问 `http://<服务器IP>:8000/`。

如设置了 `WEB_API_TOKEN`，会弹出登录框，输入 `.env` 中的 token。

### 5.2 登录 115

Web UI 顶部"登录"按钮 → 扫码 → cookie 加密入库。

`/healthz` 应返回 `{"ok": true, "logged_in": true}`。

### 5.3 验证飞书（如启用）

**方式 A：Web UI 设置页** — 点击"测试飞书连通性"按钮。

**方式 B：API 调用：**

```bash
curl -X POST \
  -H "Authorization: Bearer $WEB_API_TOKEN" \
  http://localhost:8000/api/config/feishu/test
```

预期响应（成功）：

```json
{"ok": true, "message": "连通正常，首行链接列：https://115.com/s/abc..."}
```

### 5.4 验证 Telegram（如启用）

1. 在 Telegram 中搜索你的 bot，私聊 `/ping`，应收到 `pong`。
2. 发送一个 115 分享链接，应收到入队回复。
3. 若 user_id 不在白名单：bot 静默无响应（查 `TELEGRAM_ALLOWED_USER_IDS`）。

---

## 6. 生产部署

### 6.1 Windows（家用服务器 / NAS）

**方式 A：直接 uvicorn 后台跑（最简）**

```bat
cd 115\backend
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**方式 B：注册为 Windows 服务（推荐，开机自启）**

下载 [nssm](https://nssm.cc/) 后：

```bat
nssm install 115-auto-save "M:\workspace\115\backend\.venv\Scripts\python.exe" "-m uvicorn app.main:app --host 0.0.0.0 --port 8000"
nssm set 115-auto-save AppDirectory "M:\workspace\115\backend"
nssm set 115-auto-save AppEnvironmentExtra "PYTHONUNBUFFERED=1"
nssm start 115-auto-save

:: 查看状态
nssm status 115-auto-save

:: 停止 / 重启
nssm stop 115-auto-save
nssm restart 115-auto-save
```

### 6.2 Linux（VPS / 群晖 / Ubuntu Server）

**systemd unit** `/etc/systemd/system/115-auto-save.service`：

```ini
[Unit]
Description=115 Auto Save
After=network.target

[Service]
Type=simple
User=app
WorkingDirectory=/opt/115/backend
EnvironmentFile=/opt/115/backend/.env
ExecStart=/opt/115/backend/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5
StandardOutput=append:/var/log/115-auto-save.log
StandardError=append:/var/log/115-auto-save.err.log

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now 115-auto-save
sudo journalctl -u 115-auto-save -f          # 实时日志
sudo systemctl status 115-auto-save          # 状态
```

### 6.3 Docker（未来支持）

当前未提供 Dockerfile。如需容器化，参考方向：

- 多阶段构建：node 阶段编译前端，python 阶段打包后端 + 前端 dist
- 数据卷：`/app/backend/data`（SQLite + cookie 缓存）
- 环境变量：通过 `env:` 注入 `.env` 字段

### 6.4 Nginx 反向代理（HTTPS / 外网）

```nginx
server {
    server_name your.domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE 长连接（任务进度推送 /feed）
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }

    listen 443 ssl http2;
    ssl_certificate     /etc/letsencrypt/live/your.domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your.domain.com/privkey.pem;
}

server {
    listen 80;
    server_name your.domain.com;
    return 301 https://$host$request_uri;
}
```

申请证书（Let's Encrypt）：

```bash
sudo certbot certonly --nginx -d your.domain.com
```

---

## 7. 升级流程

```bash
cd 115
git pull

# 后端依赖
cd backend
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux
pip install -e .

# 前端
cd ../frontend
npm install
npm run build

# 重启服务
# Windows (nssm):  nssm restart 115-auto-save
# Linux (systemd): sudo systemctl restart 115-auto-save
```

### 数据库迁移说明

当前用 SQLAlchemy `create_all`，**幂等但不会自动改 schema**。

- 新增字段 / 表：自动生效
- 修改字段类型 / 删除字段：需手动 `rm data/config.db`（**会丢 cookie + 历史，需重新扫码**）
- 未来计划：接入 Alembic 实现平滑迁移

---

## 8. 常见问题

| 现象 | 原因 | 解决 |
|---|---|---|
| 启动后访问前端 404 | `frontend/dist` 不存在 | 先跑 `npm run build` |
| `value too long for column` | 数据库老 schema | 删 `data/config.db` 重启 |
| TG 收不到消息 | `TELEGRAM_ALLOWED_USER_IDS` 没填自己的 user_id | 私聊 @userinfobot 查 ID |
| 飞书轮询无任务 | 列名不匹配 | Web UI 设置页改列名，或 `.env` 改 `FEISHU_LINK_COLUMN` |
| `ENCRYPTION_KEY` 改了 → cookie 失效 | cookie 用旧 key 加密 | 重新扫码登录 |
| 任务卡在 running | 服务异常退出未优雅关闭 | 重启服务（启动时自动 running→pending） |
| 飞书 API 401 | `tenant_access_token` 过期 | 自动重试一次；持续失败检查 APP_SECRET |
| TG bot 不能发消息到群 | 群已开启隐私模式 | 群设置 → 关闭 Privacy Mode，或把 bot 设为管理员 |
| `_resolve_cid` 报"目录名包含非法字符" | 115 不允许的字符（如 `:`、`*`） | 检查 TMDB 返回的标题 / 年份拼接 |
| 推送重复入队 | 飞书 hash 去重失效 | 检查 `share_hash` 列 UNIQUE 索引；清理 `data/config.db` |

---

## 9. 部署后验证清单

### 基础（必做）

- [ ] `GET /healthz` → `{"ok": true, "logged_in": true}`
- [ ] Web UI 能看到任务列表（已通过 Bearer token 鉴权）
- [ ] 发一个 115 分享链接，观察转存成功（`status=done`）

### Telegram（如启用）

- [ ] 私聊 bot `/ping` → 收到 `pong`
- [ ] 发送 115 链接 → 收到"已入队"回复
- [ ] 发送非白名单 user_id 的消息 → bot 静默（无回复）
- [ ] 触发 AuthExpired（清除 cookie 重启）→ admin user 收到推送

### 飞书（如启用）

- [ ] `POST /api/config/feishu/test` → `{"ok": true, "message": "连通正常..."}`
- [ ] 飞书表新增一行（带 115 链接）→ 等待 ≤ `FEISHU_POLL_INTERVAL_MINUTES` 分钟 → 后端任务列表出现
- [ ] 同一行重复保存 → 不会重复入队（`share_hash` 去重）

### 转存链路（端到端）

- [ ] 电影类：分享根目录名能被 TMDB 识别 → `target_path` 形如 `/电影/阿凡达 (2009)`
- [ ] 学习类：`/学习/<根目录名>`（无 TMDB 元数据）
- [ ] 未分类：`/_未分类/<根目录名>`
- [ ] 缺失中间目录自动创建（如 `/电影` 不存在时 `fs_makedirs` 会建）

### 健壮性

- [ ] 服务异常 kill → 重启后 running 任务自动回退 pending
- [ ] 115 cookie 失效 → 任务 status=pending + `error_msg="需重新登录: ..."` + （TG/飞书来源）推送通知
- [ ] 飞书 API 短暂不可用 → 当前周期 log error 后跳过，下个周期恢复
