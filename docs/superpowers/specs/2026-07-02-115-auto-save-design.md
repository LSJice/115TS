# 115 网盘自动转存与分类系统 — 设计文档

- **创建日期**：2026-07-02
- **作者**：用户 + Claude（brainstorming）
- **状态**：已通过 brainstorming，待编写实施计划

---

## 1. 背景与目标

### 1.1 问题陈述

用户从多个来源（Web 粘贴、Telegram 群、飞书共享 Excel）收集到大量 115 网盘分享链接。当前需要逐个手动：
1. 打开 115 网盘
2. 输入链接 + 提取码
3. 选择转存目标文件夹
4. 等待完成

而下游消费者（Infuse、网易波密）已与 115 关联，只要文件出现在 115 中即可被自动刮削识别。瓶颈在"分享链接 → 我的 115 对应分类目录"这一步。

### 1.2 目标

构建一个后台服务，**自动**完成：

- 从多种输入源接收分享链接
- 解析并提取分享内容元信息
- 基于文件名规则 + TMDB 元数据刮削判定类型与命名
- 转存到 115 网盘对应的标准化目录结构
- 处理重复、错误、Cookie 过期等边界情况
- 通过 Web UI 实时查看进度与历史

### 1.3 非目标（YAGNI）

- ❌ 不实现微信消息监听（逆向方案不稳定，暂缓）
- ❌ 不做用户多租户、权限管理（个人工具）
- ❌ 不做云部署（本地 Windows 服务）
- ❌ 不做 CDN/分发加速（QPS 极低）

---

## 2. 需求摘要

| 维度 | 决策 |
|---|---|
| 输入源 | ① Web UI 手动粘贴 ② Telegram Bot（仅响应白名单 chat_id/user_id） ③ 飞书共享 Excel 定时轮询（默认每 5 分钟一次，可配置） |
| 分类策略 | 规则匹配五大类（电影/电视剧/动漫/综艺/学习）+ TMDB 元数据刮削生成 Infuse 标准子目录 |
| 部署形态 | Python 后台服务 + Vue3/Element Plus Web UI（前后端分离） |
| 115 登录 | 二维码扫码，Cookie 持久化 |
| 115 顶级目录 | 沿用已有的「电影/电视剧/动漫/综艺/学习」 |
| 冲突处理 | 同链接 hash 命中 → 跳过 + 提示已转存时间 |
| 任务持久化 | SQLite，服务重启自动恢复 pending/running 任务 |

---

## 3. 系统架构

### 3.1 总体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        输入层（多来源）                          │
│  ① Web UI 提交框    ② Telegram Bot    ③ 飞书 Excel 定时轮询     │
└────────┬──────────────────┬────────────────────┬───────────────┘
         │                  │                    │
         ▼                  ▼                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  FastAPI 后端（uvicorn 单进程，APScheduler 内嵌）                │
│ ┌────────────────────────────────────────────────────────────┐ │
│ │  API 路由层 (REST + SSE)                                    │ │
│ │  /api/auth /api/tasks /api/history /api/config /api/dirs    │ │
│ └────────────────────────────────────────────────────────────┘ │
│ ┌────────────────────────────────────────────────────────────┐ │
│ │  业务服务层（每个组件单一职责）                             │ │
│ │  LinkParser / LoginManager / ShareFetcher                   │ │
│ │  Classifier / MetadataScraper / PathResolver                │ │
│ │  TransferTask / Deduper / TaskRunner                        │ │
│ └────────────────────────────────────────────────────────────┘ │
│ ┌────────────────────────────────────────────────────────────┐ │
│ │  调度与适配层                                               │ │
│ │  APScheduler（飞书轮询）+ TelegramAdapter + WebAdapter      │ │
│ │  asyncio.Queue（内存队列，SQLite 持久化源）                  │ │
│ └────────────────────────────────────────────────────────────┘ │
│ ┌────────────────────────────────────────────────────────────┐ │
│ │  持久层  SQLite（tasks / auth_state / feishu_state）         │ │
│ │  * history 视图 = tasks 表中 status IN ('done','failed','skipped') │ │
│ └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │  115 网盘 (云)   │
                    └──────────────────┘
                              ▲
                              │
┌────────────────────────────────────────────┐
│  Vue3 + Element Plus + Vite Web UI         │
│  Login / Tasks / History / Config / Browser│
└────────────────────────────────────────────┘
```

### 3.2 关键设计决策

| 决策 | 理由 |
|---|---|
| **FastAPI 单进程** | QPS 极低，单进程足够；避免 Celery+Redis 的部署复杂度 |
| **任务持久化用 SQLite** | 单文件、零运维；崩溃可恢复；与业务表同库 |
| **asyncio.Queue 仅做内存中转** | 持久化由 SQLite tasks 表承担，重启时扫描重入队 |
| **APScheduler 内嵌** | 减少部署单元 |
| **前端构建产物由 FastAPI 静态托管** | 同源、单端口、省 nginx |
| **服务层组件单一职责** | 便于单测；后续替换某层（如换 TMDB→Douban）影响面小 |
| **后端是业务规则唯一持有者** | 前端纯展示，避免业务逻辑散落 |
| **TelegramAdapter 用 long-polling，非阻塞方式挂进同一 event loop** | 个人工具无公网域名，webhook 不现实；用 `Application.initialize()` + `updater.start_polling()` 接入 FastAPI `lifespan`，而非调用会阻塞的 `run_polling()`，避免与 uvicorn 抢 event loop |
| **Web UI 默认仅信任本机/内网访问，暴露到内网外时加固定 Bearer Token** | 个人工具不做账号体系，但避免"谁都能操作我的网盘"这种极端情况 |

---

## 4. 核心组件

### 4.1 后端服务层

| 组件 | 文件 | 职责 | 主要依赖 |
|---|---|---|---|
| **LinkParser** | `services/link_parser.py` | 从原始文本中解析多种格式的链接，提取 URL 与提取码；**规范化**（统一大小写、去掉末尾斜杠与无关 query 参数，仅保留 share_id）后再计算 `share_hash` | 无（标准库 re） |
| **LoginManager** | `services/login_manager.py` | 扫码登录、Cookie 持久化、过期检测与刷新 | `p115client` |
| **ShareFetcher** | `services/share_fetcher.py` | 调 p115client 拉取分享内文件树（文件夹名/文件名/大小） | `LoginManager` |
| **Classifier** | `services/classifier.py` | 基于文件名规则判定大类（电影/电视剧/动漫/综艺/学习）；命中"学习"时标记跳过元数据刮削 | 无 |
| **MetadataScraper** | `services/metadata_scraper.py` | 调 TMDB API 识别真实片名、年份、Season 信息；电影走 `/search/movie`，电视剧/动漫统一走 `/search/tv`（动漫也是 TMDB 的 tv 类型，不额外区分 endpoint）；分类为"学习"时不调用 | `httpx` |
| **PathResolver** | `services/path_resolver.py` | 根据分类 + 元数据 + 115 根目录树生成目标路径；**若目标剧集目录已存在（同名匹配）则复用**，用于多季合并，而非每次新建 | `ShareFetcher`（读取 115 现有目录树做同名匹配） |
| **TransferTask** | `services/transfer_task.py` | 调用 p115client 转存 API；处理"已在网盘"提示（**该机制天然覆盖服务崩溃重启后的重放场景**——重放时若 115 端已存在该内容会返回"已在网盘"而非重复创建，无需额外的幂等检查）；轮询转存结果 | `LoginManager` |
| **Deduper** | `services/deduper.py` | 维护 `share_hash` 唯一索引；查询历史是否已处理（**仅按分享链接去重，与目标路径无关**；目标目录是否已存在由 `PathResolver` 自行判断，见上） | SQLite |
| **TaskRunner** | `services/task_runner.py` | 协调流水线；通过 asyncio.Queue 消费任务；处理重试与回退（重试通过延时重新入队实现，不在 worker 内 `sleep` 阻塞，避免拖慢其他 pending 任务） | 全部 |

### 4.2 输入适配层

| 组件 | 文件 | 触发方式 |
|---|---|---|
| **WebAdapter** | `adapters/web_api.py`（FastAPI 路由） | 用户 UI 提交 |
| **TelegramAdapter** | `adapters/telegram_bot.py` | Bot 收到含 115 链接的消息；**仅响应白名单 `chat_id`/`user_id`（配置于 `.env`）**，非白名单消息直接忽略，不建任务 |
| **FeishuAdapter** | `adapters/feishu_sheet.py` | APScheduler 每 N 分钟拉取飞书表格新行 |

### 4.3 API 路由

```
POST /api/auth/qrcode          # 获取登录二维码
GET  /api/auth/qrcode/status   # 轮询扫码状态
POST /api/auth/logout
GET  /api/auth/check           # Cookie 有效性

POST /api/tasks                # 提交链接
GET  /api/tasks                # 任务列表
GET  /api/tasks/{id}           # 任务详情
POST /api/tasks/{id}/retry     # 重试
PUT  /api/tasks/{id}/category  # 人工修正分类/目标路径后重新转存（用于"未分类"场景）
GET  /api/tasks/stream         # SSE 实时推送

GET  /api/history              # 转存历史（搜索）
DELETE /api/history/{id}       # 删除记录

GET  /api/dirs/browse          # 浏览 115 目录树
GET  /api/dirs/roots           # 五大顶级目录 cid

GET  /api/config               # 读取配置（脱敏）
PUT  /api/config               # 更新 TMDB Key / 飞书凭证 / 规则
POST /api/config/feishu/test   # 测试飞书连通性
```

### 4.4 数据模型（SQLite）

```sql
CREATE TABLE tasks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source        TEXT NOT NULL,        -- 'web' | 'telegram' | 'feishu'
    source_ref    TEXT,
    raw_input     TEXT NOT NULL,
    share_url     TEXT NOT NULL,
    share_code    TEXT,
    share_hash    TEXT NOT NULL UNIQUE,
    status        TEXT NOT NULL,        -- pending/running/done/failed/skipped
    category      TEXT,
    target_path   TEXT,
    metadata_json TEXT,
    error_msg     TEXT,
    retry_count   INTEGER NOT NULL DEFAULT 0,
    created_at    INTEGER NOT NULL,
    started_at    INTEGER,
    finished_at   INTEGER
);

CREATE INDEX idx_tasks_status ON tasks(status);
-- share_hash 已是 UNIQUE，SQLite 会自动建索引，无需再建 idx_tasks_hash

CREATE TABLE auth_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE TABLE feishu_state (
    sheet_id   TEXT PRIMARY KEY,
    last_row   INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
```

### 4.5 前端模块

```
src/
├── views/
│   ├── Login.vue
│   ├── Tasks.vue
│   ├── History.vue
│   ├── Config.vue
│   └── Browser.vue
├── stores/        # Pinia（auth/tasks/config）
├── api/           # axios 封装
└── router/
```

---

## 5. 数据流

### 5.1 典型流程（Telegram 入站 → 转存完成）

```
[1] TG 群消息入站
[2] TelegramAdapter 提取链接 + 提取码，计算 share_hash
[3] Deduper.check(share_hash) 未命中 → INSERT tasks (status=pending)
[4] asyncio.Queue.put(task_id) → TaskRunner 消费
[5] TaskRunner 流水线：
    [a] ShareFetcher.fetch     → 拉文件树
    [b] Classifier.classify    → 命中"电视剧"
    [c] MetadataScraper.search → TMDB 返回年份与季信息
    [d] PathResolver.resolve   → /电视剧/<剧名> (<年份>)/Season XX/（若目录已存在则复用，用于多季合并）
    [e] TransferTask.run       → p115client 转存（"已在网盘"响应天然吸收重启重放场景）→ 115 异步任务 ID 轮询
[6] status=done → SSE 推送 → 前端刷新
[7] Infuse/网易波密（外部）扫描 115 识别新文件
```

### 5.2 分支

- **A 已转存**：Deduper 命中 → status=skipped + 提示已转存时间
- **B 分类未命中**：自动降级到 `/_未分类/<原分享文件夹名>/`，前端标红；用户可通过 `PUT /api/tasks/{id}/category` 手动修正分类后重新转存
- **C TMDB 失败/未配置**：降级用原分享文件夹名，path 形如 `/电视剧/<原名>/`
- **D 转存 API 失败**：status=failed，前端可重试
- **E Cookie 过期**：暂停任务；来源是 Web 时 SSE 通知前端弹扫码页；来源是 Telegram/飞书时无人值守，Bot 额外主动推送一条"需要重新登录"提醒，避免任务无声卡住；扫码后自动恢复
- **F 分类为"学习"**：跳过 MetadataScraper（无 TMDB 元数据可言），PathResolver 直接用原分享文件夹名生成路径

---

## 6. 错误处理与边界

### 6.1 错误分级

| 等级 | 类型 | 策略 |
|---|---|---|
| 🟢 可重试 | 网络抖动 / 115 限流 | 指数退避（1s→4s→16s，最多 3 次） |
| 🟡 需人工 | Cookie 过期 / 提取码错误 | 暂停 + 通知前端 + 修复后自动恢复 |
| 🔴 不可恢复 | 分享已删 / 重复 hash | 标记 failed/skipped，写入历史 |

### 6.2 边界情况

1. **链接格式变种**：纯 URL / 带 password 参数 / 中文说明文本 / 多链接一条消息
2. **分享内嵌套目录**：以分享根目录为整体单元，**原样保留**分享内子目录结构，仅决定"挂在 115 哪个父目录下"。例如分享内已是 `<剧名>/Season 01/...` 结构，转存到 `/电视剧/<剧名> (<年份>)/`；若分享内是平铺视频文件，PathResolver 会创建 `Season 01/` 包装层（避免 Infuse 把多季识别成 1 季）
3. **同名剧集**：TMDB 多结果按年份匹配；歧义时选第一个 + 前端标记"待确认"
4. **TMDB 故障/未配置**：降级用原文件名，不阻塞转存
5. **飞书表格结构变化**：按列名匹配（非位置）。默认列约定：`链接`、`提取码`、`备注`；用户可在配置中改列名。找不到列名则跳过本次拉取 + 告警
6. **大文件转存超时**：轮询 115 任务状态，最长等待 30 分钟
7. **服务重启**：启动钩子 `UPDATE tasks SET status='pending' WHERE status='running'`，重新入队；重放时若该内容已转存成功，115 会返回"已在网盘"（见 §4.1 TransferTask），不会产生重复文件
8. **多设备登录冲突**：检测到下线 → 清 Cookie → 强提示重新扫码
9. **Telegram 非白名单消息**：直接忽略，不建任务，不占用 115 空间

### 6.3 日志与可观测

- **结构化日志**：`loguru`，按天滚动，保留 30 天
- **实时进度**：FastAPI SSE 推送（比 WebSocket 简单，原生支持）
- **配置安全**：敏感字段（TMDB Key / 飞书 Secret / 115 Cookie）加密存 SQLite，密钥来自 `.env`
- **访问控制**：默认假设仅本机/内网访问；若监听地址暴露到内网以外，需通过 `.env` 配置固定 Bearer Token，由中间件校验 `/api/*`（简单单用户机制，非账号体系）

---

## 7. 测试策略

### 7.1 单元测试（pytest，目标覆盖率 > 80%）

| 模块 | 关键用例 |
|---|---|
| LinkParser | 多种链接格式变种 |
| Classifier | 各类样本 → 期望分类 |
| MetadataScraper | mock TMDB；多结果匹配；零结果降级 |
| PathResolver | 嵌套 vs 平铺；同名歧义；中文/特殊字符 |
| Deduper | 重复 hash 命中；并发插入安全 |

### 7.2 集成测试

| 场景 | 做法 |
|---|---|
| 任务流水线 | mock p115client，验证状态流转 + 重启恢复 |
| 飞书轮询 | mock 飞书 API，验证位点推进 |
| Telegram | mock Update 对象，验证消息解析 |

### 7.3 不测的部分

- ❌ 115/TMDB 实际响应（用 mock）
- ❌ 前端组件（初期手动验证；后续如复杂度上升再加 Vitest）

### 7.4 测试夹具

```
tests/
├── fixtures/
│   ├── links/
│   ├── filenames/
│   ├── tmdb_responses/
│   └── p115_responses/
├── unit/
└── integration/
```

---

## 8. 部署与运行

| 项 | 方案 |
|---|---|
| 后端启动 | `uvicorn app.main:app --host 0.0.0.0 --port 8000` |
| 前端构建 | `npm run build` → `dist/` 由 FastAPI 静态托管 |
| 开发模式 | Vite 5173 + FastAPI 8000 + vite-proxy 转发 /api |
| Windows 常驻 | NSSM 注册服务，开机自启 |
| 配置 | `.env`（环境变量）+ `data/config.db`（加密敏感字段） |
| 目录 | 单一可执行目录，data/ 存 SQLite 与日志 |

---

## 9. 依赖清单

### 后端（Python ≥ 3.11）

```
fastapi
uvicorn[standard]
pydantic
pydantic-settings
httpx
loguru
apscheduler
python-telegram-bot
p115client[qrcode]    # 支持扫码登录
cryptography           # 敏感字段加密
sse-starlette          # SSE 推送
```

### 前端

```
vue@3
element-plus
vite
@vitejs/plugin-vue
vue-router
pinia
axios
```

### 开发

```
pytest
pytest-asyncio
respx           # httpx mock
ruff
mypy
```

---

## 10. 项目结构

```
115/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── api/
│   │   │   ├── auth.py
│   │   │   ├── tasks.py
│   │   │   ├── history.py
│   │   │   ├── config.py
│   │   │   └── dirs.py
│   │   ├── services/
│   │   │   ├── link_parser.py
│   │   │   ├── login_manager.py
│   │   │   ├── share_fetcher.py
│   │   │   ├── classifier.py
│   │   │   ├── metadata_scraper.py
│   │   │   ├── path_resolver.py
│   │   │   ├── transfer_task.py
│   │   │   ├── deduper.py
│   │   │   └── task_runner.py
│   │   ├── adapters/
│   │   │   ├── telegram_bot.py
│   │   │   ├── feishu_sheet.py
│   │   │   └── web_api.py
│   │   ├── models/
│   │   └── utils/
│   ├── tests/
│   ├── data/                 # SQLite + 日志（gitignore）
│   ├── pyproject.toml
│   └── .env.example
├── frontend/
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
├── docs/
│   └── superpowers/specs/
│       └── 2026-07-02-115-auto-save-design.md
└── README.md
```

---

## 11. 开放事项

实施阶段需要解决的细节（不影响规格定稿）：

1. **TMDB API Key**：用户需自行申请（https://www.themoviedb.org/settings/api）
2. **飞书应用**：用户需在飞书开放平台创建自建应用，授予 Bitable/Sheets 读取权限
3. **Telegram Bot Token**：用户需通过 @BotFather 创建 Bot
4. **NSSM 服务包装**：实施阶段给出具体脚本
5. **Telegram 白名单 chat_id/user_id**：用户需提供允许触发转存的群/用户 ID 清单
6. **Web UI 访问 Token**（若部署到本机以外可访问的地址时）：用户按需生成并配置

这些是"运行时配置"，不阻塞代码实现。

---

## 12. 验收标准

- [ ] 扫码登录一次，Cookie 持久化 ≥ 7 天
- [ ] Web UI 粘贴一条分享链接 → 自动转存到正确分类目录
- [ ] Telegram Bot 接收一条消息 → 自动转存
- [ ] 飞书 Excel 新增一行 → 5 分钟内被消费
- [ ] 重复链接提交 → 显示"已转存于 YYYY-MM-DD"，不再请求 115
- [ ] 服务重启 → 自动恢复未完成任务，且不产生重复转存
- [ ] Telegram 非白名单用户发送链接 → 被忽略，不生成任务
- [ ] 单元测试覆盖率 ≥ 80%，关键路径集成测试通过
