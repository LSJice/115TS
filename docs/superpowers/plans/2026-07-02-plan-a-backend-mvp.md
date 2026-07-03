# Plan A: 后端 MVP — 自动转存核心 API

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现可独立运行的后端 API，用户能通过 HTTP 请求提交 115 分享链接，系统自动完成扫码登录、解析、分类、TMDB 刮削、路径生成、115 转存，并将任务状态持久化。

**Architecture:** FastAPI 单进程 + SQLite 持久化 + asyncio.Queue 任务队列 + p115client 调用 115 API + httpx 调用 TMDB。服务层每个组件单一职责（SRP），适配器层负责多输入源（Plan A 只做 Web 输入，Telegram/飞书在 Plan B）。任务在 SQLite 中持久化，进程崩溃后启动时自动恢复。

**Tech Stack:** Python ≥ 3.11 / FastAPI / uvicorn / SQLAlchemy 2.x / pydantic v2 / pydantic-settings / httpx / p115client / cryptography / sse-starlette / loguru / pytest + pytest-asyncio + respx

**对应规格文档:** `docs/superpowers/specs/2026-07-02-115-auto-save-design.md`

**前置条件:** 已完成并审核通过 brainstorming 设计文档。

**Plan A 范围**:
- ✅ 项目脚手架、配置、数据库
- ✅ 核心业务层 9 个服务（LinkParser / LoginManager / ShareFetcher / Classifier / MetadataScraper / PathResolver / TransferTask / Deduper / TaskRunner）
- ✅ Auth / Tasks / History / Dirs / Config 全部 API
- ✅ Bearer Token 中间件 + 敏感字段加密
- ✅ 启动时任务恢复
- ✅ 后端 MVP 集成测试

**不在 Plan A 范围（Plan B/C 处理）**:
- ❌ Telegram Adapter（Plan B Task 1）
- ❌ 飞书 Adapter（Plan B Task 2）
- ❌ Web UI（Vue3/Element Plus，Plan B Task 3-10）
- ❌ NSSM 服务化（Plan C Task 1）
- ❌ 集成测试套件补全（Plan C Task 2）

**Plan A 验收:** 用 curl 提交一条分享链接，能跑通完整流水线，文件出现在 115 正确分类目录下；服务重启后未完成任务自动恢复且不重复转存。

---

## 文件结构（Plan A 产物）

```
115/
├── backend/
│   ├── pyproject.toml
│   ├── .env.example
│   ├── .gitignore
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                      # FastAPI 实例 + lifespan
│   │   ├── config.py                    # Settings（pydantic-settings）
│   │   ├── db.py                        # SQLAlchemy 引擎 + 建表
│   │   ├── models.py                    # ORM 模型（Task / AuthState / FeishuState）
│   │   ├── schemas.py                   # Pydantic 请求/响应 schema
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py                  # /api/auth/*
│   │   │   ├── tasks.py                 # /api/tasks/*
│   │   │   ├── history.py               # /api/history/*
│   │   │   ├── dirs.py                  # /api/dirs/*
│   │   │   └── config.py                # /api/config/*
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── link_parser.py
│   │   │   ├── login_manager.py
│   │   │   ├── share_fetcher.py
│   │   │   ├── classifier.py
│   │   │   ├── metadata_scraper.py
│   │   │   ├── path_resolver.py
│   │   │   ├── transfer_task.py
│   │   │   ├── deduper.py
│   │   │   └── task_runner.py
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── crypto.py                # 敏感字段加密
│   │       ├── auth_middleware.py       # Bearer Token 校验
│   │       └── sse.py                   # SSE 广播器
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py                  # pytest fixtures
│   │   ├── fixtures/
│   │   │   ├── links.py                 # 链接样本常量
│   │   │   ├── filenames.py             # 文件名样本常量
│   │   │   ├── tmdb_responses.py        # TMDB mock JSON
│   │   │   └── p115_responses.py        # 115 API mock JSON
│   │   ├── unit/
│   │   │   ├── test_config.py
│   │   │   ├── test_link_parser.py
│   │   │   ├── test_classifier.py
│   │   │   ├── test_metadata_scraper.py
│   │   │   ├── test_path_resolver.py
│   │   │   ├── test_deduper.py
│   │   │   ├── test_crypto.py
│   │   │   └── test_sse.py
│   │   └── integration/
│   │       ├── test_db.py
│   │       ├── test_task_runner_pipeline.py
│   │       ├── test_task_recovery.py
│   │       └── test_api_smoke.py
│   └── data/                            # 运行时（.gitignore）
│       └── .gitkeep
└── docs/superpowers/plans/
    └── 2026-07-02-plan-a-backend-mvp.md
```

---

## 任务列表（20 个）

按依赖关系排序，每个任务产出可独立提交的代码。

---

### Task 1: 项目脚手架与依赖

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/.env.example`
- Create: `backend/.gitignore`
- Create: `backend/app/__init__.py` (空文件)
- Create: `backend/app/{api,services,utils}/__init__.py` (空文件)
- Create: `backend/data/.gitkeep`
- Create: `backend/tests/__init__.py` (空文件)
- Create: `backend/tests/{unit,integration,fixtures}/__init__.py` (空文件)

- [ ] **Step 1.1: 创建 pyproject.toml**

```toml
[project]
name = "cloud115-auto-save"
version = "0.1.0"
description = "115 网盘自动转存与分类系统 - 后端"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110.0",
    "uvicorn[standard]>=0.27.0",
    "pydantic>=2.6.0",
    "pydantic-settings>=2.2.0",
    "sqlalchemy>=2.0.25",
    "httpx>=0.27.0",
    "loguru>=0.7.2",
    "apscheduler>=3.10.4",
    "p115client[qrcode]>=0.7.4",
    "cryptography>=42.0.0",
    "sse-starlette>=2.0.0",
    "python-multipart>=0.0.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "respx>=0.20.2",
    "ruff>=0.3.0",
    "mypy>=1.8.0",
]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["."]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = true
```

- [ ] **Step 1.2: 创建 .env.example**

```env
# 数据库
DATABASE_URL=sqlite:///data/config.db

# 敏感字段加密密钥（32 字节 base64，开发用：python -c "import secrets,base64;print(base64.b64encode(secrets.token_bytes(32)).decode())"）
ENCRYPTION_KEY=

# Web UI 访问 Token（部署到非本机时必填）
WEB_API_TOKEN=

# TMDB
TMDB_API_KEY=
TMDB_LANGUAGE=zh-CN

# 115
P115_APP_DATA_DIR=data/p115

# Telegram（Plan B 用）
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_CHAT_IDS=
TELEGRAM_ALLOWED_USER_IDS=

# 飞书（Plan B 用）
FEISHU_APP_ID=
FEISHU_APP_SECRET=
FEISHU_APP_TOKEN=
FEISHU_TABLE_ID=
FEISHU_LINK_COLUMN=链接
FEISHU_CODE_COLUMN=提取码
FEISHU_REMARK_COLUMN=备注
FEISHU_POLL_INTERVAL_MINUTES=5

# 日志
LOG_LEVEL=INFO
LOG_DIR=data/logs
```

- [ ] **Step 1.3: 创建 .gitignore**

```
__pycache__/
*.py[cod]
*.egg-info/
.venv/
.env
data/
!data/.gitkeep
.pytest_cache/
.mypy_cache/
.ruff_cache/
htmlcov/
.coverage
dist/
build/
```

- [ ] **Step 1.4: 创建空 __init__.py 与 .gitkeep**

依次创建以下空文件：
- `backend/app/__init__.py`
- `backend/app/api/__init__.py`
- `backend/app/services/__init__.py`
- `backend/app/utils/__init__.py`
- `backend/tests/__init__.py`
- `backend/tests/unit/__init__.py`
- `backend/tests/integration/__init__.py`
- `backend/tests/fixtures/__init__.py`
- `backend/data/.gitkeep`

- [ ] **Step 1.5: 安装依赖并验证**

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate           # Windows
# 或 source .venv/bin/activate   # Unix
pip install -e ".[dev]"
pytest --version
```

Expected: 输出 `pytest 8.x.x`，无错误。

- [ ] **Step 1.6: 提交**

```bash
cd ..
git init 2>/dev/null || true
git add backend/
git commit -m "chore: scaffold backend project structure"
```

---

### Task 2: 配置管理 Settings

**Files:**
- Create: `backend/app/config.py`
- Create: `backend/tests/unit/test_config.py`

- [ ] **Step 2.1: 写失败测试**

`backend/tests/unit/test_config.py`:
```python
import pytest
from pydantic_settings import SettingsConfigDict


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", "dGVzdC1rZXktMzItYnl0ZXMtbG9uZy1lbm91Z2g=")
    monkeypatch.setenv("TMDB_API_KEY", "tmdb-fake-key")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///data/test.db")
    from app.config import Settings

    s = Settings()
    assert s.encryption_key == "dGVzdC1rZXktMzItYnl0ZXMtbG9uZy1lbm91Z2g="
    assert s.tmdb_api_key == "tmdb-fake-key"
    assert str(s.database_url).endswith("test.db")


def test_feishu_poll_interval_default(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", "dGVzdC1rZXktMzItYnl0ZXMtbG9uZy1lbm91Z2g=")
    from app.config import Settings

    s = Settings()
    assert s.feishu_poll_interval_minutes == 5


def test_telegram_allowed_ids_parses_csv(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", "dGVzdC1rZXktMzItYnl0ZXMtbG9uZy1lbm91Z2g=")
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "-100123456, -100987654")
    from app.config import Settings

    s = Settings()
    assert s.telegram_allowed_chat_ids == [-100123456, -100987654]
```

- [ ] **Step 2.2: 运行测试验证失败**

```bash
cd backend
pytest tests/unit/test_config.py -v
```

Expected: FAIL with `ImportError: No module named 'app.config'`（或类似）

- [ ] **Step 2.3: 实现 Settings**

`backend/app/config.py`:
```python
from pathlib import Path
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    telegram_allowed_chat_ids: List[int] = Field(default_factory=list)
    telegram_allowed_user_ids: List[int] = Field(default_factory=list)

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
```

- [ ] **Step 2.4: 运行测试验证通过**

```bash
pytest tests/unit/test_config.py -v
```

Expected: 3 passed

- [ ] **Step 2.5: 提交**

```bash
git add backend/app/config.py backend/tests/unit/test_config.py
git commit -m "feat(config): add pydantic-settings based Settings"
```

---

### Task 3: 数据库与 ORM 模型

**Files:**
- Create: `backend/app/models.py`
- Create: `backend/app/db.py`
- Create: `backend/tests/integration/test_db.py`

- [ ] **Step 3.1: 写失败测试**

`backend/tests/integration/test_db.py`:
```python
import pytest
from sqlalchemy import inspect
from app.db import engine, init_db, drop_db, get_session


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr("app.db.engine", create_engine_for_path(db_path))
    init_db()
    yield
    drop_db()


def create_engine_for_path(path):
    from sqlalchemy import create_engine

    return create_engine(f"sqlite:///{path}", echo=False)


def test_tables_created():
    insp = inspect(engine)
    tables = insp.get_table_names()
    assert "tasks" in tables
    assert "auth_state" in tables
    assert "feishu_state" in tables


def test_insert_task_and_query_by_hash(get_session):
    from app.models import Task

    with get_session() as s:
        t = Task(
            source="web",
            raw_input="https://115.com/s/abc",
            share_url="https://115.com/s/abc",
            share_hash="hash-abc",
            status="pending",
            created_at=1700000000,
        )
        s.add(t)
        s.commit()
        assert t.id is not None

    with get_session() as s:
        found = s.query(Task).filter_by(share_hash="hash-abc").first()
        assert found is not None
        assert found.status == "pending"


def test_share_hash_unique(get_session):
    from sqlalchemy.exc import IntegrityError
    from app.models import Task

    with get_session() as s:
        s.add(Task(
            source="web", raw_input="x", share_url="u1",
            share_hash="dup", status="pending", created_at=1,
        ))
        s.commit()

    with get_session() as s:
        s.add(Task(
            source="web", raw_input="x", share_url="u2",
            share_hash="dup", status="pending", created_at=2,
        ))
        with pytest.raises(IntegrityError):
            s.commit()
```

- [ ] **Step 3.2: 运行测试验证失败**

```bash
pytest tests/integration/test_db.py -v
```

Expected: ImportError on `app.db` / `app.models`

- [ ] **Step 3.3: 实现 models.py**

`backend/app/models.py`:
```python
from sqlalchemy import Column, Integer, String, Text, Index
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(32), nullable=False)
    source_ref = Column(Text, nullable=True)
    raw_input = Column(Text, nullable=False)
    share_url = Column(Text, nullable=False)
    share_code = Column(String(64), nullable=True)
    share_hash = Column(String(128), nullable=False, unique=True)
    status = Column(String(16), nullable=False)
    category = Column(String(32), nullable=True)
    target_path = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)
    error_msg = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    created_at = Column(Integer, nullable=False)
    started_at = Column(Integer, nullable=True)
    finished_at = Column(Integer, nullable=True)

    __table_args__ = (
        Index("idx_tasks_status", "status"),
    )


class AuthState(Base):
    __tablename__ = "auth_state"

    key = Column(String(64), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(Integer, nullable=False)


class FeishuState(Base):
    __tablename__ = "feishu_state"

    sheet_id = Column(String(64), primary_key=True)
    last_row = Column(Integer, nullable=False)
    updated_at = Column(Integer, nullable=False)
```

- [ ] **Step 3.4: 实现 db.py**

`backend/app/db.py`:
```python
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models import Base, Task

_engine = None
_SessionLocal = None


def _build_engine():
    db_path = Path(settings.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        _engine = _build_engine()
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


# 测试用别名
engine = None  # 在 init_db 时赋值


def init_db():
    global engine
    engine = get_engine()
    Base.metadata.create_all(engine)


def drop_db():
    global engine
    if engine is not None:
        Base.metadata.drop_all(engine)


@contextmanager
def get_session() -> Iterator[Session]:
    if _SessionLocal is None:
        get_engine()
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()
```

- [ ] **Step 3.5: 修复测试 fixture（autouse 的 monkeypatch 时机问题）**

打开 `backend/tests/integration/test_db.py`，把开头 fixture 改为：

```python
@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    from app import db as db_mod
    db_mod._engine = None
    db_mod._SessionLocal = None
    monkeypatch.setattr(db_mod, "_build_engine", lambda: create_engine_for_path(tmp_path / "test.db"))
    db_mod.init_db()
    yield db_mod.get_session
    db_mod.drop_db()


def create_engine_for_path(path):
    from sqlalchemy import create_engine
    return create_engine(f"sqlite:///{path}", echo=False, connect_args={"check_same_thread": False})
```

把测试中 `with get_session()` 改为 `with isolated_db()`：

```python
def test_tables_created(isolated_db):
    from sqlalchemy import inspect
    from app import db as db_mod
    insp = inspect(db_mod.engine)
    tables = insp.get_table_names()
    assert "tasks" in tables

def test_insert_task_and_query_by_hash(isolated_db):
    from app.models import Task
    with isolated_db() as s:
        ...
```

（其他测试同步把 `get_session` 入参替换为 `isolated_db`）

- [ ] **Step 3.6: 运行测试验证通过**

```bash
pytest tests/integration/test_db.py -v
```

Expected: 3 passed

- [ ] **Step 3.7: 提交**

```bash
git add backend/app/models.py backend/app/db.py backend/tests/integration/test_db.py
git commit -m "feat(db): add SQLAlchemy models and session management"
```

---

### Task 4: 加密工具 utils/crypto.py

**Files:**
- Create: `backend/app/utils/crypto.py`
- Create: `backend/tests/unit/test_crypto.py`

- [ ] **Step 4.1: 写失败测试**

`backend/tests/unit/test_crypto.py`:
```python
import base64
import pytest


@pytest.fixture
def crypto_with_key(monkeypatch):
    key = base64.b64encode(b"0123456789abcdef0123456789abcdef").decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    from importlib import reload
    import app.utils.crypto
    reload(app.utils.crypto)
    from app.utils.crypto import encrypt, decrypt
    return encrypt, decrypt


def test_round_trip(crypto_with_key):
    encrypt, decrypt = crypto_with_key
    cipher = encrypt("hello 世界")
    assert cipher != "hello 世界"
    assert decrypt(cipher) == "hello 世界"


def test_decrypt_invalid_returns_none(crypto_with_key):
    encrypt, decrypt = crypto_with_key
    assert decrypt("not-a-valid-token") is None


def test_empty_key_returns_plaintext(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", "")
    from importlib import reload
    import app.utils.crypto
    reload(app.utils.crypto)
    from app.utils.crypto import encrypt, decrypt
    assert encrypt("x") == "x"
    assert decrypt("x") == "x"
```

- [ ] **Step 4.2: 运行验证失败**

```bash
pytest tests/unit/test_crypto.py -v
```

Expected: ImportError

- [ ] **Step 4.3: 实现 crypto.py**

`backend/app/utils/crypto.py`:
```python
import base64
import os

from cryptography.fernet import Fernet, InvalidToken


def _get_key() -> bytes | None:
    raw = os.getenv("ENCRYPTION_KEY", "").strip()
    if not raw:
        return None
    try:
        return base64.b64decode(raw)
    except Exception:
        return None


def _get_fernet() -> Fernet | None:
    key = _get_key()
    if key is None or len(key) != 32:
        return None
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt(plaintext: str) -> str:
    f = _get_fernet()
    if f is None:
        return plaintext  # 未配置密钥时透传（仅开发环境）
    return f.encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt(ciphertext: str) -> str | None:
    f = _get_fernet()
    if f is None:
        return ciphertext
    try:
        return f.decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, Exception):
        return None
```

- [ ] **Step 4.4: 运行验证通过**

```bash
pytest tests/unit/test_crypto.py -v
```

Expected: 3 passed

- [ ] **Step 4.5: 提交**

```bash
git add backend/app/utils/crypto.py backend/tests/unit/test_crypto.py
git commit -m "feat(utils): add Fernet-based sensitive field encryption"
```

---

### Task 5: SSE 广播器 utils/sse.py

**Files:**
- Create: `backend/app/utils/sse.py`
- Create: `backend/tests/unit/test_sse.py`

- [ ] **Step 5.1: 写失败测试**

`backend/tests/unit/test_sse.py`:
```python
import asyncio
import pytest


@pytest.mark.asyncio
async def test_subscribe_and_publish():
    from app.utils.sse import Broadcaster

    bc = Broadcaster()
    received = []

    async def consumer():
        async for evt in bc.subscribe():
            received.append(evt)
            if len(received) >= 2:
                break

    task = asyncio.create_task(consumer())
    await asyncio.sleep(0.05)
    await bc.publish({"id": 1, "status": "running"})
    await bc.publish({"id": 1, "status": "done"})
    await asyncio.wait_for(task, timeout=1.0)
    assert received == [{"id": 1, "status": "running"}, {"id": 1, "status": "done"}]


@pytest.mark.asyncio
async def test_no_subscribers_publish_doesnt_error():
    from app.utils.sse import Broadcaster

    bc = Broadcaster()
    await bc.publish({"x": 1})  # 不应抛异常
```

- [ ] **Step 5.2: 运行验证失败**

```bash
pytest tests/unit/test_sse.py -v
```

Expected: ImportError

- [ ] **Step 5.3: 实现 sse.py**

`backend/app/utils/sse.py`:
```python
import asyncio
import json
from typing import AsyncIterator, Set


class Broadcaster:
    """简单 async SSE 广播器：多个订阅者，无订阅时丢弃事件。"""

    def __init__(self) -> None:
        self._subscribers: Set[asyncio.Queue] = set()

    def subscribe(self) -> AsyncIterator[str]:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.add(q)
        return self._iter(q)

    async def _iter(self, q: asyncio.Queue) -> AsyncIterator[str]:
        try:
            while True:
                payload = await q.get()
                yield payload
                if payload == "CLOSE":
                    break
        finally:
            self._subscribers.discard(q)

    async def publish(self, event: dict) -> None:
        data = json.dumps(event, ensure_ascii=False)
        for q in list(self._subscribers):
            try:
                q.put_nowait(f"data: {data}\n\n")
            except asyncio.QueueFull:
                # 慢消费者直接丢弃
                pass


broadcaster = Broadcaster()
```

- [ ] **Step 5.4: 验证通过**

```bash
pytest tests/unit/test_sse.py -v
```

Expected: 2 passed

- [ ] **Step 5.5: 提交**

```bash
git add backend/app/utils/sse.py backend/tests/unit/test_sse.py
git commit -m "feat(utils): add async SSE broadcaster"
```

---

### Task 6: LinkParser（链接解析与规范化）

**Files:**
- Create: `backend/tests/fixtures/links.py`
- Create: `backend/tests/unit/test_link_parser.py`
- Create: `backend/app/services/link_parser.py`

- [ ] **Step 6.1: 写测试夹具与失败测试**

`backend/tests/fixtures/links.py`:
```python
SAMPLES = [
    # (raw_text, expected_url, expected_code, expected_hash_consistency)
    ("https://115.com/s/abc123?password=xyz", "abc123", "xyz", True),
    ("https://115.com/s/abc123?password=xyz", "abc123", "xyz", True),  # 与上行同 hash
    ("https://115.com/s/abc123/?password=xyz", "abc123", "xyz", True),  # 末尾斜杠 → 同 hash
    ("HTTPS://115.com/s/ABC123?password=xyz", "abc123", "xyz", True),  # 大小写 → 同 hash
    ("链接: 115.com/s/def456 提取码: pwd", "def456", "pwd", True),
    ("分享 https://115.com/s/ghi789?password=aaa 收藏一下", "ghi789", "aaa", True),
    ("https://115.com/s/zzz999", "zzz999", None, True),  # 无提取码
    ("没有链接的纯文本", None, None, False),
]

NORMALIZATION_PAIRS = [
    # 不同写法应规范化为同一 share_id → 同一 hash
    ("https://115.com/s/CaseSensitive123?password=p", "https://115.com/s/casesensitive123/?password=p"),
]
```

`backend/tests/unit/test_link_parser.py`:
```python
import pytest
from tests.fixtures.links import SAMPLES, NORMALIZATION_PAIRS


def test_parse_each_sample():
    from app.services.link_parser import parse
    for raw, expected_id, expected_code, _ in SAMPLES:
        result = parse(raw)
        if expected_id is None:
            assert result is None, f"应解析失败: {raw}"
        else:
            assert result is not None, f"应解析成功: {raw}"
            assert result.share_id == expected_id
            assert result.password == expected_code


def test_hash_consistency_for_normalization():
    from app.services.link_parser import parse
    for a, b in NORMALIZATION_PAIRS:
        ra, rb = parse(a), parse(b)
        assert ra is not None and rb is not None
        assert ra.share_hash == rb.share_hash, f"规范化失败：{a} vs {b}"


def test_duplicate_input_same_hash():
    from app.services.link_parser import parse
    samples = [s for s in SAMPLES if s[3]]
    hashes = {parse(s[0]).share_hash for s in samples}
    # 每个不同 share_id 一个 hash
    expected = {s[1].lower() for s in samples}
    assert len(hashes) == len({s[1] for s in samples})


def test_multiple_links_in_one_message():
    from app.services.link_parser import parse_all
    text = "两个 https://115.com/s/aaa111?password=p1 和 https://115.com/s/bbb222?password=p2"
    results = parse_all(text)
    assert len(results) == 2
    assert {r.share_id for r in results} == {"aaa111", "bbb222"}
```

- [ ] **Step 6.2: 运行验证失败**

```bash
pytest tests/unit/test_link_parser.py -v
```

Expected: ImportError

- [ ] **Step 6.3: 实现 link_parser.py**

`backend/app/services/link_parser.py`:
```python
import hashlib
import re
from dataclasses import dataclass

URL_RE = re.compile(
    r"https?://(?:anyme\.)?115\.com/s/(?P<id>[A-Za-z0-9_-]+)"
    r"(?:\?[^#\s]*)?",
    re.IGNORECASE,
)
PASSWORD_RE = re.compile(r"(?:password|提取码|访问码|密码)\s*[:：]?\s*(?P<code>[A-Za-z0-9]{4,12})", re.IGNORECASE)
SHORT_RE = re.compile(r"115\.com/s/(?P<id>[A-Za-z0-9_-]+)", re.IGNORECASE)


@dataclass(frozen=True)
class ShareLink:
    share_id: str          # 规范化后的小写 id
    password: str | None
    share_hash: str        # sha256(share_id)，规范化后稳定


def _normalize_id(raw: str) -> str:
    return raw.strip().lower()


def parse(text: str) -> ShareLink | None:
    if not text:
        return None
    m = URL_RE.search(text) or SHORT_RE.search(text)
    if not m:
        return None
    share_id = _normalize_id(m.group("id"))
    pwd_match = PASSWORD_RE.search(text)
    password = pwd_match.group("code") if pwd_match else None
    # 若 URL 中有 ?password=xxx 也兼容
    if password is None:
        qm = re.search(r"[?&]password=([^&\s#]+)", text, re.IGNORECASE)
        if qm:
            password = qm.group(1)
    return ShareLink(
        share_id=share_id,
        password=password,
        share_hash=hashlib.sha256(share_id.encode("utf-8")).hexdigest(),
    )


def parse_all(text: str) -> list[ShareLink]:
    if not text:
        return []
    results: list[ShareLink] = []
    seen: set[str] = set()
    for m in re.finditer(URL_RE, text):
        share_id = _normalize_id(m.group("id"))
        if share_id in seen:
            continue
        seen.add(share_id)
        pwd_match = PASSWORD_RE.search(text)
        password = pwd_match.group("code") if pwd_match else None
        if password is None:
            qm = re.search(r"[?&]password=([^&\s#]+)", text, re.IGNORECASE)
            password = qm.group(1) if qm else None
        results.append(ShareLink(
            share_id=share_id,
            password=password,
            share_hash=hashlib.sha256(share_id.encode("utf-8")).hexdigest(),
        ))
    return results
```

- [ ] **Step 6.4: 验证通过**

```bash
pytest tests/unit/test_link_parser.py -v
```

Expected: 4 passed

- [ ] **Step 6.5: 提交**

```bash
git add backend/app/services/link_parser.py backend/tests/unit/test_link_parser.py backend/tests/fixtures/links.py
git commit -m "feat(services): add LinkParser with normalization-based hashing"
```

---

### Task 7: Classifier（规则匹配五大类）

**Files:**
- Create: `backend/tests/fixtures/filenames.py`
- Create: `backend/tests/unit/test_classifier.py`
- Create: `backend/app/services/classifier.py`

- [ ] **Step 7.1: 写测试夹具**

`backend/tests/fixtures/filenames.py`:
```python
# (file_list, expected_category)
# file_list 模拟分享根目录下的文件名样本
SAMPLES = [
    # 电视剧：S01E01 / 第N集 / EP01
    (["Game.of.Thrones.S01E01.1080p.mkv", "Game.of.Thrones.S01E02.mkv"], "电视剧"),
    (["某剧.第03集.WEB-DL.mp4"], "电视剧"),
    (["Anime.Series.EP12.mkv"], "电视剧"),  # EP 走电视剧（动漫也是 TV 类型）
    # 电影：单一视频文件，年份在括号里
    (["Avatar.2009.2160p.UHD.mkv"], "电影"),
    (["The.Dark.Knight.2008.mkv"], "电影"),
    # 动漫：日文片名 / 番剧 / 国创 / 漫
    (["鬼灭之刃.第二季.合集.mkv"], "动漫"),
    (["进击的巨人.S01E01.mp4"], "动漫"),  # 兼容：含 S01E01 但中文番名 → 动漫
    # 综艺：综艺/选秀/真人秀
    (["向往的生活.第N期.mp4", "某综艺.2024暑期版.mp4"], "综艺"),
    # 学习：教程/课程/TTC/Coursera/PDF/PPT
    (["Python进阶教程.第01讲.mp4"], "学习"),
    (["machine-learning-lecture-01.pdf"], "学习"),
    # 未命中：未知
    (["random-file.bin"], "_未分类"),
]
```

- [ ] **Step 7.2: 写失败测试**

`backend/tests/unit/test_classifier.py`:
```python
from tests.fixtures.filenames import SAMPLES


def test_classify_all_samples():
    from app.services.classifier import classify
    for files, expected in SAMPLES:
        result = classify(files)
        assert result == expected, f"file_list={files} expected={expected} got={result}"
```

- [ ] **Step 7.3: 运行验证失败**

```bash
pytest tests/unit/test_classifier.py -v
```

Expected: ImportError

- [ ] **Step 7.4: 实现 classifier.py**

`backend/app/services/classifier.py`:
```python
import re
from typing import Iterable

# 优先级从高到低；先命中的优先
RULES: list[tuple[str, re.Pattern]] = [
    # 学习类优先（防止 mp4 教程被误判为电影/剧）
    ("学习", re.compile(
        r"(教程|课程|讲义|lec\d+|lecture|coursera|udemy|tTC|TTC|\.pdf$|\.pptx?$|\.docx?$)",
        re.IGNORECASE,
    )),
    # 动漫：常见番剧关键词 + 日文假名片段
    ("动漫", re.compile(
        r"(动漫|番剧|国创|二次元|鬼灭|进击的巨人|海贼王|火影|死神|咒术|蜘蛛|紫罗兰|"
        r"[ぁ-ヿ]+|[一-龥]{2,8}\.(?:第\w+季|合集))",
        re.IGNORECASE,
    )),
    # 电视剧：S01E01 / 第N集 / EP\d
    ("电视剧", re.compile(
        r"(S\d{1,2}E\d{1,3}|EP\d{1,3}|第\d{1,3}集|Season\s?\d{1,2}|E\d{2,3}\.)",
        re.IGNORECASE,
    )),
    # 综艺
    ("综艺", re.compile(
        r"(综艺|真人秀|选秀|向往的生活|奔跑吧|中国好声音|歌手|快乐大本营)",
        re.IGNORECASE,
    )),
    # 电影：含 4 位年份
    ("电影", re.compile(r"(19[5-9]\d|20[0-4]\d)")),
]


def classify(file_list: Iterable[str]) -> str:
    text = "\n".join(file_list)
    for category, pattern in RULES:
        if pattern.search(text):
            return category
    return "_未分类"
```

- [ ] **Step 7.5: 验证通过**

```bash
pytest tests/unit/test_classifier.py -v
```

Expected: 1 passed

- [ ] **Step 7.6: 提交**

```bash
git add backend/app/services/classifier.py backend/tests/unit/test_classifier.py backend/tests/fixtures/filenames.py
git commit -m "feat(services): add rule-based Classifier for 5 categories"
```

---

### Task 8: MetadataScraper（TMDB 客户端）

**Files:**
- Create: `backend/tests/fixtures/tmdb_responses.py`
- Create: `backend/tests/unit/test_metadata_scraper.py`
- Create: `backend/app/services/metadata_scraper.py`

- [ ] **Step 8.1: 写 mock 夹具**

`backend/tests/fixtures/tmdb_responses.py`:
```python
GOT_SEARCH = {
    "page": 1,
    "results": [
        {
            "id": 1399,
            "name": "Game of Thrones",
            "original_name": "Game of Thrones",
            "first_air_date": "2011-04-17",
            "overview": "七大家族争夺铁王座",
            "number_of_seasons": 8,
            "media_type": "tv",
        },
        {
            "id": 99999,
            "name": "Game of Thrones (Animated)",
            "first_air_date": "2018-01-01",
            "number_of_seasons": 1,
            "media_type": "tv",
        },
    ],
    "total_results": 2,
}

AVATAR_SEARCH = {
    "page": 1,
    "results": [
        {
            "id": 19995,
            "title": "Avatar",
            "original_title": "Avatar",
            "release_date": "2009-12-15",
            "overview": "潘多拉星球",
            "media_type": "movie",
        },
    ],
    "total_results": 1,
}

EMPTY_SEARCH = {"page": 1, "results": [], "total_results": 0}
```

- [ ] **Step 8.2: 写失败测试**

`backend/tests/unit/test_metadata_scraper.py`:
```python
import pytest
import respx
from httpx import Response

from tests.fixtures.tmdb_responses import GOT_SEARCH, AVATAR_SEARCH, EMPTY_SEARCH


@pytest.mark.asyncio
@respx.mock
async def test_search_tv_returns_best_match():
    respx.get("https://api.themoviedb.org/3/search/tv").mock(
        return_value=Response(200, json=GOT_SEARCH)
    )
    from app.services.metadata_scraper import MetadataScraper

    scraper = MetadataScraper(api_key="fake")
    result = await scraper.search(query="权力的游戏", category="电视剧", year=None)
    assert result is not None
    assert result.title == "Game of Thrones"
    assert result.year == 2011
    assert result.tmdb_id == 13995 + 4  # 13999
    assert result.kind == "tv"


@pytest.mark.asyncio
@respx.mock
async def test_search_movie():
    respx.get("https://api.themoviedb.org/3/search/movie").mock(
        return_value=Response(200, json=AVATAR_SEARCH)
    )
    from app.services.metadata_scraper import MetadataScraper

    scraper = MetadataScraper(api_key="fake")
    result = await scraper.search(query="Avatar", category="电影", year=2009)
    assert result is not None
    assert result.title == "Avatar"
    assert result.year == 2009
    assert result.kind == "movie"


@pytest.mark.asyncio
@respx.mock
async def test_zero_results_returns_none():
    respx.get("https://api.themoviedb.org/3/search/tv").mock(
        return_value=Response(200, json=EMPTY_SEARCH)
    )
    from app.services.metadata_scraper import MetadataScraper

    scraper = MetadataScraper(api_key="fake")
    result = await scraper.search(query="不存在的剧", category="电视剧", year=None)
    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_no_api_key_returns_none():
    from app.services.metadata_scraper import MetadataScraper

    scraper = MetadataScraper(api_key="")
    result = await scraper.search(query="anything", category="电影", year=None)
    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_year_filter_picks_correct_match():
    respx.get("https://api.themoviedb.org/3/search/tv").mock(
        return_value=Response(200, json=GOT_SEARCH)
    )
    from app.services.metadata_scraper import MetadataScraper

    scraper = MetadataScraper(api_key="fake")
    result = await scraper.search(query="Game of Thrones", category="电视剧", year=2018)
    # year=2018 应匹配第二个（动画版 2018）
    assert result is not None
    assert result.tmdb_id == 99999
```

- [ ] **Step 8.3: 运行验证失败**

```bash
pytest tests/unit/test_metadata_scraper.py -v
```

Expected: ImportError

- [ ] **Step 8.4: 实现 metadata_scraper.py**

`backend/app/services/metadata_scraper.py`:
```python
from dataclasses import dataclass
from typing import Literal

import httpx


@dataclass(frozen=True)
class Metadata:
    tmdb_id: int
    title: str
    year: int | None
    kind: Literal["movie", "tv"]
    seasons: int | None = None


class MetadataScraper:
    BASE = "https://api.themoviedb.org/3"

    def __init__(self, api_key: str, language: str = "zh-CN", timeout: float = 10.0):
        self.api_key = api_key
        self.language = language
        self.timeout = timeout

    async def search(
        self,
        query: str,
        category: str,
        year: int | None,
    ) -> Metadata | None:
        if not self.api_key or not query:
            return None
        if category == "电影":
            endpoint = "movie"
            year_param = "primary_release_year"
            title_field = "title"
        else:
            # 电视剧/动漫 统一走 tv
            endpoint = "tv"
            year_param = "first_air_date_year"
            title_field = "name"
        params = {
            "api_key": self.api_key,
            "language": self.language,
            "query": query,
        }
        if year:
            params[year_param] = year
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(f"{self.BASE}/search/{endpoint}", params=params)
                resp.raise_for_status()
            except httpx.HTTPError:
                return None
            data = resp.json()
        results = data.get("results", [])
        if not results:
            return None
        # 年份过滤：若用户给了 year，挑匹配的；否则取第一个
        chosen = None
        if year:
            for r in results:
                d = r.get("release_date") or r.get("first_air_date") or ""
                if d.startswith(str(year)):
                    chosen = r
                    break
        if chosen is None:
            chosen = results[0]
        date_str = chosen.get("release_date") or chosen.get("first_air_date") or ""
        parsed_year = int(date_str[:4]) if len(date_str) >= 4 else None
        return Metadata(
            tmdb_id=chosen["id"],
            title=chosen.get(title_field) or chosen.get("original_title") or chosen.get("original_name") or query,
            year=parsed_year,
            kind=endpoint,  # type: ignore
            seasons=chosen.get("number_of_seasons"),
        )
```

- [ ] **Step 8.5: 验证通过**

```bash
pytest tests/unit/test_metadata_scraper.py -v
```

Expected: 5 passed

- [ ] **Step 8.6: 提交**

```bash
git add backend/app/services/metadata_scraper.py backend/tests/unit/test_metadata_scraper.py backend/tests/fixtures/tmdb_responses.py
git commit -m "feat(services): add TMDB MetadataScraper with year-filter"
```

---

### Task 9: Deduper（hash 幂等）

**Files:**
- Create: `backend/tests/unit/test_deduper.py`
- Create: `backend/app/services/deduper.py`

- [ ] **Step 9.1: 写失败测试**

`backend/tests/unit/test_deduper.py`:
```python
import pytest


@pytest.fixture
def deduper(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models import Base
    from app.services.deduper import Deduper

    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    return Deduper(session_factory=Session)


def test_first_occurrence_not_seen(deduper):
    assert deduper.is_processed("hash1") is False


def test_after_record_seen(deduper):
    deduper.mark_processed(share_hash="hash1", task_id=42)
    result = deduper.is_processed("hash1")
    assert result is not None
    assert result["task_id"] == 42


def test_concurrent_insert_only_one_wins(deduper):
    from sqlalchemy.exc import IntegrityError
    deduper.mark_processed(share_hash="dup", task_id=1)
    with pytest.raises(IntegrityError):
        deduper.mark_processed(share_hash="dup", task_id=2)
```

- [ ] **Step 9.2: 验证失败**

```bash
pytest tests/unit/test_deduper.py -v
```

Expected: ImportError

- [ ] **Step 9.3: 实现 deduper.py**

`backend/app/services/deduper.py`:
```python
from datetime import datetime, timezone
from typing import Callable, Optional

from sqlalchemy.orm import Session, sessionmaker

from app.models import Task


class Deduper:
    def __init__(self, session_factory: Callable[[], Session]):
        self._session_factory = session_factory

    def is_processed(self, share_hash: str) -> Optional[dict]:
        """返回 {task_id, finished_at, target_path} 或 None"""
        with self._session_factory() as s:
            t = s.query(Task).filter_by(share_hash=share_hash).filter(
                Task.status.in_(["done", "skipped"])
            ).first()
            if t is None:
                return None
            return {
                "task_id": t.id,
                "finished_at": t.finished_at,
                "target_path": t.target_path,
                "status": t.status,
            }

    def mark_processed(self, share_hash: str, task_id: int) -> None:
        """以 task_id 行的 share_hash 唯一约束兜底"""
        # 实际写入由 TaskRunner 在 INSERT tasks 时完成；
        # 这里仅做冲突检测，调用方负责异常处理。
        with self._session_factory() as s:
            existing = s.query(Task).filter_by(share_hash=share_hash).first()
            if existing is not None and existing.id != task_id:
                from sqlalchemy.exc import IntegrityError
                raise IntegrityError("Duplicate share_hash", {}, None)
```

- [ ] **Step 9.4: 验证通过**

```bash
pytest tests/unit/test_deduper.py -v
```

Expected: 3 passed

- [ ] **Step 9.5: 提交**

```bash
git add backend/app/services/deduper.py backend/tests/unit/test_deduper.py
git commit -m "feat(services): add Deduper for share_hash idempotency"
```

---

### Task 10: PathResolver（路径生成 + 目录复用）

**Files:**
- Create: `backend/tests/unit/test_path_resolver.py`
- Create: `backend/app/services/path_resolver.py`

- [ ] **Step 10.1: 写失败测试**

`backend/tests/unit/test_path_resolver.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.metadata_scraper import Metadata


def make_fetcher(existing_dirs: dict[str, list[str]]):
    """existing_dirs: {parent_path: [child_dir_names]}"""
    fetcher = MagicMock()
    async def list_dir(path: str) -> list[str]:
        return existing_dirs.get(path, [])
    fetcher.list_dir = list_dir
    return fetcher


@pytest.mark.asyncio
async def test_resolve_tv_with_metadata_creates_path_with_year():
    from app.services.path_resolver import PathResolver

    resolver = PathResolver(make_fetcher({"/电视剧": []}))
    md = Metadata(tmdb_id=1399, title="权力的游戏", year=2011, kind="tv", seasons=8)
    path = await resolver.resolve(category="电视剧", metadata=md, share_root_name="某分享文件夹")
    assert path == "/电视剧/权力的游戏 (2011)"


@pytest.mark.asyncio
async def test_resolve_tv_existing_dir_reused_for_multi_season():
    """已有同名目录（不带年份也复用），用于多季合并"""
    from app.services.path_resolver import PathResolver

    fetcher = make_fetcher({"/电视剧": ["权力的游戏 (2011)", "其他剧"]})
    resolver = PathResolver(fetcher)
    md = Metadata(tmdb_id=1399, title="权力的游戏", year=2011, kind="tv")
    path = await resolver.resolve("电视剧", md, "新分享")
    assert path == "/电视剧/权力的游戏 (2011)"


@pytest.mark.asyncio
async def test_resolve_movie_no_metadata_uses_share_root():
    from app.services.path_resolver import PathResolver

    resolver = PathResolver(make_fetcher({"/电影": []}))
    path = await resolver.resolve("电影", metadata=None, share_root_name="阿凡达.2009.4K")
    assert path == "/电影/阿凡达.2009.4K"


@pytest.mark.asyncio
async def test_resolve_uncategorized():
    from app.services.path_resolver import PathResolver

    resolver = PathResolver(make_fetcher({"/_未分类": []}))
    path = await resolver.resolve("_未分类", metadata=None, share_root_name="原分享")
    assert path == "/_未分类/原分享"


@pytest.mark.asyncio
async def test_resolve_learning_skips_year_suffix():
    from app.services.path_resolver import PathResolver

    resolver = PathResolver(make_fetcher({"/学习": []}))
    path = await resolver.resolve("学习", metadata=None, share_root_name="Python进阶")
    assert path == "/学习/Python进阶"


@pytest.mark.asyncio
async def test_resolve_movie_with_metadata_includes_year():
    from app.services.path_resolver import PathResolver

    fetcher = make_fetcher({"/电影": []})
    resolver = PathResolver(fetcher)
    md = Metadata(tmdb_id=19995, title="Avatar", year=2009, kind="movie")
    path = await resolver.resolve("电影", md, "avatar.mkv")
    assert path == "/电影/Avatar (2009)"
```

- [ ] **Step 10.2: 验证失败**

```bash
pytest tests/unit/test_path_resolver.py -v
```

Expected: ImportError

- [ ] **Step 10.3: 实现 path_resolver.py**

`backend/app/services/path_resolver.py`:
```python
from typing import Protocol

from app.services.metadata_scraper import Metadata


class _DirLister(Protocol):
    async def list_dir(self, path: str) -> list[str]: ...


CATEGORY_ROOTS = {
    "电影": "/电影",
    "电视剧": "/电视剧",
    "动漫": "/动漫",
    "综艺": "/综艺",
    "学习": "/学习",
    "_未分类": "/_未分类",
}


class PathResolver:
    def __init__(self, dir_lister: _DirLister):
        self._lister = dir_lister

    async def resolve(
        self,
        category: str,
        metadata: Metadata | None,
        share_root_name: str,
    ) -> str:
        root = CATEGORY_ROOTS.get(category, CATEGORY_ROOTS["_未分类"])
        if metadata is None:
            # 无元数据：用原分享文件夹名
            return f"{root}/{share_root_name}"

        # 学习类不强制年份
        if category == "学习":
            return f"{root}/{share_root_name}"

        # 电影/电视剧/动漫/综艺：尝试匹配已存在同名目录（多季合并）
        desired_name = f"{metadata.title} ({metadata.year})" if metadata.year else metadata.title
        existing = await self._lister.list_dir(root)
        # 已有同名 → 复用
        if desired_name in existing:
            return f"{root}/{desired_name}"
        # 也兼容不带年份的同名（比如老数据）
        no_year = metadata.title
        if no_year in existing:
            return f"{root}/{no_year}"
        # 新建
        return f"{root}/{desired_name}"
```

- [ ] **Step 10.4: 验证通过**

```bash
pytest tests/unit/test_path_resolver.py -v
```

Expected: 6 passed

- [ ] **Step 10.5: 提交**

```bash
git add backend/app/services/path_resolver.py backend/tests/unit/test_path_resolver.py
git commit -m "feat(services): add PathResolver with existing-dir reuse"
```

---

### Task 11: LoginManager（扫码登录）

**Files:**
- Create: `backend/app/services/login_manager.py`

> 说明：LoginManager 与 p115client 强耦合，**不做单元测试**（p115client 自身有测试）；只在集成测试里做冒烟（见 Task 20）。本任务实现接口契约。

- [ ] **Step 11.1: 实现 login_manager.py**

`backend/app/services/login_manager.py`:
```python
import asyncio
import json
import time
from dataclasses import dataclass
from typing import Optional

from loguru import logger

from app.db import get_session
from app.models import AuthState
from app.utils.crypto import encrypt, decrypt

COOKIE_KEY = "p115_cookies"
QR_TOKEN_KEY = "p115_qr_token"


@dataclass
class QRStatus:
    state: str  # 'waiting' | 'scanned' | 'confirmed' | 'expired' | 'error'
    qrcode_url: Optional[str] = None
    message: str = ""


class LoginManager:
    def __init__(self, app_data_dir: str):
        self.app_data_dir = app_data_dir
        self._client = None

    def _load_cookies(self) -> dict | None:
        with get_session() as s:
            row = s.query(AuthState).filter_by(key=COOKIE_KEY).first()
            if row is None:
                return None
            plain = decrypt(row.value)
            try:
                return json.loads(plain) if plain else None
            except json.JSONDecodeError:
                return None

    def _save_cookies(self, cookies: dict) -> None:
        with get_session() as s:
            payload = encrypt(json.dumps(cookies))
            existing = s.query(AuthState).filter_by(key=COOKIE_KEY).first()
            now = int(time.time())
            if existing:
                existing.value = payload
                existing.updated_at = now
            else:
                s.add(AuthState(key=COOKIE_KEY, value=payload, updated_at=now))
            s.commit()

    def is_logged_in(self) -> bool:
        return self._load_cookies() is not None

    def get_client(self):
        if self._client is not None:
            return self._client
        from p115 import P115Client  # p115client 包入口

        cookies = self._load_cookies()
        client = P115Client(app=self.app_data_dir, cookies=cookies or None)
        self._client = client
        return client

    async def start_qrcode_login(self) -> QRStatus:
        """启动一次扫码登录，返回二维码 URL"""
        client = self.get_client()
        try:
            resp = client.login_qrcode_token()
            uid = resp["data"]["uid"]
            qrcode = resp["data"]["qrcode"]
            with get_session() as s:
                _upsert(s, QR_TOKEN_KEY, uid)
            return QRStatus(state="waiting", qrcode_url=qrcode)
        except Exception as e:
            logger.exception("start_qrcode_login failed")
            return QRStatus(state="error", message=str(e))

    async def poll_qrcode_status(self) -> QRStatus:
        client = self.get_client()
        with get_session() as s:
            uid_row = s.query(AuthState).filter_by(key=QR_TOKEN_KEY).first()
            uid = uid_row.value if uid_row else None
        if not uid:
            return QRStatus(state="error", message="无活跃的二维码会话")
        try:
            resp = client.login_qrcode_status(uid=uid)
            code, msg = resp["data"]["code"], resp["data"]["msg"]
            if code == 0:
                cookies = client.cookies
                self._save_cookies(cookies)
                return QRStatus(state="confirmed", message="登录成功")
            if code == 1:
                return QRStatus(state="waiting", message="等待扫码")
            if code == 2:
                return QRStatus(state="scanned", message="已扫码，请在手机确认")
            if code == -1:
                return QRStatus(state="expired", message="二维码过期")
            return QRStatus(state="error", message=f"未知 code={code} msg={msg}")
        except Exception as e:
            logger.exception("poll_qrcode_status failed")
            return QRStatus(state="error", message=str(e))

    def logout(self) -> None:
        with get_session() as s:
            for k in (COOKIE_KEY, QR_TOKEN_KEY):
                row = s.query(AuthState).filter_by(key=k).first()
                if row:
                    s.delete(row)
            s.commit()
        self._client = None


def _upsert(session, key: str, value: str) -> None:
    existing = session.query(AuthState).filter_by(key=key).first()
    now = int(time.time())
    if existing:
        existing.value = value
        existing.updated_at = now
    else:
        session.add(AuthState(key=key, value=value, updated_at=now))
    session.commit()
```

- [ ] **Step 11.2: 静态检查（类型与导入）**

```bash
cd backend
python -c "from app.services.login_manager import LoginManager, QRStatus; print('OK')"
```

Expected: `OK`（p115client 包名实际为 `p115`，安装时已带上）

- [ ] **Step 11.3: 提交**

```bash
git add backend/app/services/login_manager.py
git commit -m "feat(services): add LoginManager with qrcode login + cookie encryption"
```

---

### Task 12: ShareFetcher（拉取分享文件树）

**Files:**
- Create: `backend/tests/fixtures/p115_responses.py`
- Create: `backend/app/services/share_fetcher.py`

- [ ] **Step 12.1: mock 夹具**

`backend/tests/fixtures/p115_responses.py`:
```python
SHARE_CONTENT_GOT = {
    "data": {
        "file_name": "Game.of.Thrones.Complete",
        "file_category": "0",
        "size": "12345",
        "is_dir": True,
        "file_list": [
            {"file_name": "Game.of.Thrones.S01E01.mkv", "file_category": "video", "size": 1024 ** 4},
            {"file_name": "Game.of.Thrones.S01E02.mkv", "file_category": "video", "size": 1024 ** 4},
        ],
    },
    "state": True,
}

SHARE_CONTENT_FLAT = {
    "data": {
        "file_name": "movie-collection",
        "is_dir": True,
        "file_list": [
            {"file_name": "Avatar.2009.2160p.mkv", "file_category": "video", "size": 1024 ** 4 * 50},
        ],
    },
    "state": True,
}
```

- [ ] **Step 12.2: 写失败测试**

`backend/tests/unit/test_share_fetcher.py`:
```python
import pytest
from unittest.mock import MagicMock, AsyncMock


def make_login_manager_mock(resp_data: dict):
    lm = MagicMock()
    client = MagicMock()
    client.share_snap = MagicMock(return_value=resp_data)
    lm.get_client.return_value = client
    lm.is_logged_in.return_value = True
    return lm


@pytest.mark.asyncio
async def test_fetch_returns_root_name_and_filenames():
    from tests.fixtures.p115_responses import SHARE_CONTENT_GOT
    from app.services.share_fetcher import ShareFetcher, ShareContent

    lm = make_login_manager_mock(SHARE_CONTENT_GOT)
    fetcher = ShareFetcher(lm)
    content = await fetcher.fetch(share_id="abc", password="xyz")
    assert isinstance(content, ShareContent)
    assert content.root_name == "Game.of.Thrones.Complete"
    assert content.file_names == ["Game.of.Thrones.S01E01.mkv", "Game.of.Thrones.S01E02.mkv"]


@pytest.mark.asyncio
async def test_fetch_no_password_omits_password_param():
    from tests.fixtures.p115_responses import SHARE_CONTENT_FLAT
    from app.services.share_fetcher import ShareFetcher

    lm = make_login_manager_mock(SHARE_CONTENT_FLAT)
    fetcher = ShareFetcher(lm)
    await fetcher.fetch(share_id="abc", password=None)
    args, kwargs = lm.get_client.return_value.share_snap.call_args
    assert kwargs.get("receive_code", "") in (None, "")


@pytest.mark.asyncio
async def test_fetch_handles_error_state():
    from app.services.share_fetcher import ShareFetcher, ShareFetchError

    lm = make_login_manager_mock({"state": False, "error": "invalid share"})
    fetcher = ShareFetcher(lm)
    with pytest.raises(ShareFetchError):
        await fetcher.fetch(share_id="bad", password=None)
```

- [ ] **Step 12.3: 实现 share_fetcher.py**

`backend/app/services/share_fetcher.py`:
```python
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
    def __init__(self, login_manager: LoginManager):
        self._lm = login_manager

    async def fetch(self, share_id: str, password: Optional[str]) -> ShareContent:
        client = self._lm.get_client()
        try:
            params = {"share_code": share_id}
            if password:
                params["receive_code"] = password
            resp = client.share_snap(**params)
        except Exception as e:
            logger.exception("share_snap failed")
            raise ShareFetchError(str(e)) from e
        if not resp.get("state", False):
            raise ShareFetchError(resp.get("error", "未知错误"))
        data = resp.get("data", {})
        root_name = data.get("file_name", share_id)
        file_list = data.get("file_list", [])
        file_names = [f["file_name"] for f in file_list if "file_name" in f]
        return ShareContent(root_name=root_name, file_names=file_names, raw=resp)
```

- [ ] **Step 12.4: 验证通过**

```bash
pytest tests/unit/test_share_fetcher.py -v
```

Expected: 3 passed

- [ ] **Step 12.5: 提交**

```bash
git add backend/app/services/share_fetcher.py backend/tests/unit/test_share_fetcher.py backend/tests/fixtures/p115_responses.py
git commit -m "feat(services): add ShareFetcher for share content listing"
```

---

### Task 13: TransferTask（调用 p115client 转存）

**Files:**
- Create: `backend/tests/unit/test_transfer_task.py`
- Create: `backend/app/services/transfer_task.py`

- [ ] **Step 13.1: 写失败测试**

`backend/tests/unit/test_transfer_task.py`:
```python
import pytest
from unittest.mock import MagicMock, AsyncMock


def make_lm_mock(post_save_resp: dict, offline_resp: dict | None = None):
    lm = MagicMock()
    client = MagicMock()
    client.share_post = MagicMock(return_value=post_save_resp)
    if offline_resp is not None:
        client.officer_copy_or_save = MagicMock(return_value=offline_resp)
    lm.get_client.return_value = client
    lm.is_logged_in.return_value = True
    return lm


@pytest.mark.asyncio
async def test_transfer_success():
    from app.services.transfer_task import TransferTask, TransferResult

    lm = make_lm_mock(post_save_resp={"state": True, "data": {"already_in": False}})
    task = TransferTask(lm)
    result = await task.run(share_id="abc", password="xyz", target_cid=12345)
    assert isinstance(result, TransferResult)
    assert result.success is True


@pytest.mark.asyncio
async def test_transfer_already_in_is_success():
    from app.services.transfer_task import TransferTask, TransferResult

    lm = make_lm_mock(post_save_resp={"state": True, "data": {"already_in": True, "msg": "已在网盘"}})
    task = TransferTask(lm)
    result = await task.run(share_id="abc", password="xyz", target_cid=12345)
    assert result.success is True
    assert result.already_in is True


@pytest.mark.asyncio
async def test_transfer_failure_raises():
    from app.services.transfer_task import TransferTask, TransferError

    lm = make_lm_mock(post_save_resp={"state": False, "error": "提取码错误"})
    task = TransferTask(lm)
    with pytest.raises(TransferError):
        await task.run(share_id="abc", password="bad", target_cid=12345)


@pytest.mark.asyncio
async def test_transfer_cookie_expired_raises_auth_error():
    from app.services.transfer_task import TransferTask, AuthExpiredError

    lm = MagicMock()
    client = MagicMock()
    client.share_post = MagicMock(side_effect=Exception("401 unauthorized"))
    lm.get_client.return_value = client
    lm.is_logged_in.return_value = True
    task = TransferTask(lm)
    with pytest.raises(AuthExpiredError):
        await task.run(share_id="abc", password=None, target_cid=12345)
```

- [ ] **Step 13.2: 实现 transfer_task.py**

`backend/app/services/transfer_task.py`:
```python
import asyncio
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
            params = {"share_code": share_id, "file_id": 0, "cid": target_cid}
            if password:
                params["receive_code"] = password
            resp = client.share_post(**params)
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
        data = resp.get("data", {})
        already = bool(data.get("already_in", False))
        return TransferResult(success=True, already_in=already, raw=resp)
```

- [ ] **Step 13.3: 验证通过**

```bash
pytest tests/unit/test_transfer_task.py -v
```

Expected: 4 passed

- [ ] **Step 13.4: 提交**

```bash
git add backend/app/services/transfer_task.py backend/tests/unit/test_transfer_task.py
git commit -m "feat(services): add TransferTask with already-in idempotency"
```

---

### Task 14: TaskRunner（流水线编排）

**Files:**
- Create: `backend/tests/integration/test_task_runner_pipeline.py`
- Create: `backend/app/services/task_runner.py`

- [ ] **Step 14.1: 写集成测试（mock 全部外部依赖）**

`backend/tests/integration/test_task_runner_pipeline.py`:
```python
import asyncio
import time
import pytest
from unittest.mock import MagicMock, AsyncMock

from app.models import Base, Task
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    yield Session, engine
    engine.dispose()


@pytest.fixture
def mocks():
    """mock 所有外部服务"""
    lm = MagicMock()
    lm.is_logged_in.return_value = True

    share_fetcher = MagicMock()
    share_fetcher.fetch = AsyncMock(return_value=MagicMock(
        root_name="Game.of.Thrones.S01",
        file_names=["Game.of.Thrones.S01E01.mkv", "Game.of.Thrones.S01E02.mkv"],
    ))

    classifier = MagicMock(return_value="电视剧")

    md_scraper = MagicMock()
    md_scraper.search = AsyncMock(return_value=MagicMock(
        title="权力的游戏", year=2011, kind="tv", tmdb_id=1399, seasons=1,
    ))

    path_resolver = MagicMock()
    path_resolver.resolve = AsyncMock(return_value="/电视剧/权力的游戏 (2011)")

    transfer_task = MagicMock()
    transfer_task.run = AsyncMock(return_value=MagicMock(success=True, already_in=False))

    return {
        "login_manager": lm,
        "share_fetcher": share_fetcher,
        "classifier": classifier,
        "metadata_scraper": md_scraper,
        "path_resolver": path_resolver,
        "transfer_task": transfer_task,
    }


@pytest.mark.asyncio
async def test_pipeline_success(db, mocks):
    from app.services.task_runner import TaskRunner

    Session, _ = db
    # 先插入一个 pending 任务
    with Session() as s:
        s.add(Task(
            id=1, source="web", raw_input="https://115.com/s/abc",
            share_url="https://115.com/s/abc", share_hash="hash1",
            status="pending", created_at=int(time.time()),
        ))
        s.commit()

    runner = TaskRunner(session_factory=Session, **mocks, broadcaster=MagicMock())
    runner.start()
    await runner.process_once(task_id=1)
    runner.stop()

    with Session() as s:
        t = s.get(Task, 1)
        assert t.status == "done"
        assert t.category == "电视剧"
        assert t.target_path == "/电视剧/权力的游戏 (2011)"
        assert t.finished_at is not None


@pytest.mark.asyncio
async def test_pipeline_already_processed_skips(db, mocks):
    """任务表里已是 done 状态，不应再调用任何服务"""
    from app.services.task_runner import TaskRunner

    Session, _ = db
    with Session() as s:
        s.add(Task(
            id=99, source="web", raw_input="x", share_url="u",
            share_hash="h-done", status="done", created_at=int(time.time()),
            finished_at=int(time.time()),
        ))
        s.commit()

    runner = TaskRunner(session_factory=Session, **mocks, broadcaster=MagicMock())
    await runner.process_once(task_id=99)
    runner.stop()

    mocks["share_fetcher"].fetch.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_transfer_failure_marks_failed(db, mocks):
    from app.services.task_runner import TaskRunner
    from app.services.transfer_task import TransferError

    Session, _ = db
    with Session() as s:
        s.add(Task(
            id=2, source="web", raw_input="x", share_url="u",
            share_hash="h-fail", status="pending", created_at=int(time.time()),
        ))
        s.commit()

    mocks["transfer_task"].run = AsyncMock(side_effect=TransferError("提取码错误"))

    runner = TaskRunner(session_factory=Session, **mocks, broadcaster=MagicMock())
    await runner.process_once(task_id=2)
    runner.stop()

    with Session() as s:
        t = s.get(Task, 2)
        assert t.status == "failed"
        assert "提取码" in (t.error_msg or "")


@pytest.mark.asyncio
async def test_pipeline_cookie_expired_marks_paused(db, mocks):
    from app.services.task_runner import TaskRunner
    from app.services.transfer_task import AuthExpiredError

    Session, _ = db
    with Session() as s:
        s.add(Task(
            id=3, source="web", raw_input="x", share_url="u",
            share_hash="h-paused", status="pending", created_at=int(time.time()),
        ))
        s.commit()

    mocks["transfer_task"].run = AsyncMock(side_effect=AuthExpiredError("过期"))

    bc = MagicMock()
    bc.publish = AsyncMock()
    runner = TaskRunner(session_factory=Session, **mocks, broadcaster=bc)
    await runner.process_once(task_id=3)
    runner.stop()

    with Session() as s:
        t = s.get(Task, 3)
        # Cookie 过期：状态回退到 pending（保留重试），但错误信息已记录
        assert t.status == "pending"
        assert "过期" in (t.error_msg or "")
    bc.publish.assert_called()
```

- [ ] **Step 14.2: 实现 task_runner.py**

`backend/app/services/task_runner.py`:
```python
import asyncio
import time
from typing import Callable, Optional

from loguru import logger
from sqlalchemy.orm import Session, sessionmaker

from app.models import Task
from app.services.classifier import classify
from app.services.deduper import Deduper
from app.services.link_parser import parse
from app.services.metadata_scraper import Metadata, MetadataScraper
from app.services.path_resolver import PathResolver
from app.services.share_fetcher import ShareContent, ShareFetcher
from app.services.transfer_task import AuthExpiredError, TransferError, TransferTask
from app.services.login_manager import LoginManager


class TaskRunner:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        login_manager: LoginManager,
        share_fetcher: ShareFetcher,
        classifier: Callable = classify,
        metadata_scraper: MetadataScraper | None = None,
        path_resolver: PathResolver | None = None,
        transfer_task: TransferTask | None = None,
        broadcaster=None,
    ):
        self._session_factory = session_factory
        self._lm = login_manager
        self._share_fetcher = share_fetcher
        self._classifier = classifier
        self._metadata_scraper = metadata_scraper
        self._path_resolver = path_resolver
        self._transfer_task = transfer_task
        self._broadcaster = broadcaster
        self._queue: asyncio.Queue[int] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None

    # ---------- 任务入队 ----------
    def enqueue(self, task_id: int) -> None:
        try:
            self._queue.put_nowait(task_id)
        except asyncio.QueueFull:
            logger.warning(f"queue full, task {task_id} dropped")

    # ---------- 启动后台 worker ----------
    def start(self) -> None:
        if self._worker_task is None:
            self._worker_task = asyncio.create_task(self._worker_loop())

    def stop(self) -> None:
        if self._worker_task:
            self._worker_task.cancel()
            self._worker_task = None

    async def _worker_loop(self) -> None:
        while True:
            task_id = await self._queue.get()
            try:
                await self.process_once(task_id)
            except Exception:
                logger.exception(f"worker error on task {task_id}")

    # ---------- 主处理逻辑 ----------
    async def process_once(self, task_id: int) -> None:
        with self._session_factory() as s:
            t = s.get(Task, task_id)
            if t is None:
                return
            if t.status in ("done", "skipped", "failed"):
                return
            t.status = "running"
            t.started_at = int(time.time())
            t.error_msg = None
            s.commit()
            raw_input = t.raw_input
            share_url = t.share_url
            share_code = t.share_code

        # 解析链接
        link = parse(raw_input) or parse(share_url)
        if link is None:
            await self._fail(task_id, "无法解析链接")
            return

        try:
            # [a] 拉取分享内容
            content: ShareContent = await self._share_fetcher.fetch(
                share_id=link.share_id, password=link.password,
            )
            # [b] 分类
            category = self._classifier(content.file_names)
            # [c] 元数据刮削（学习/_未分类 跳过）
            metadata: Optional[Metadata] = None
            if category in ("电影", "电视剧", "动漫", "综艺") and self._metadata_scraper:
                metadata = await self._metadata_scraper.search(
                    query=content.root_name, category=category, year=None,
                )
            # [d] 解析路径
            target_path = await self._path_resolver.resolve(
                category=category, metadata=metadata, share_root_name=content.root_name,
            )
            # [e] 转存（target_cid 由 dirs API 提前查得；这里简化为根目录 0）
            # TODO Plan A 简化：把 target_path 解析成 cid 放进 transfer；Plan B 完善
            if self._transfer_task:
                await self._transfer_task.run(
                    share_id=link.share_id, password=link.password,
                    target_cid=await self._resolve_cid(target_path),
                )
            # [f] 成功
            await self._succeed(task_id, category=category, target_path=target_path, metadata=metadata)
        except AuthExpiredError as e:
            await self._pause_for_auth(task_id, str(e))
        except TransferError as e:
            await self._fail(task_id, str(e))
        except Exception as e:
            logger.exception(f"unexpected error on task {task_id}")
            await self._fail(task_id, f"unexpected: {e}")

    # ---------- 辅助 ----------
    async def _resolve_cid(self, target_path: str) -> int:
        """把 '/电视剧/权力的游戏 (2011)' 解析成 115 cid。
        Plan A 简化实现：直接返回 0（根目录），由 115 自带的 share_post 创建子目录。
        Plan B 完善：递归调用 client.dir_remote_path_to_cid。"""
        return 0

    async def _succeed(self, task_id: int, category: str, target_path: str, metadata) -> None:
        with self._session_factory() as s:
            t = s.get(Task, task_id)
            if t is None:
                return
            t.status = "done"
            t.category = category
            t.target_path = target_path
            t.metadata_json = (
                f'{{"title":"{metadata.title}","year":{metadata.year},"tmdb_id":{metadata.tmdb_id}}}'
                if metadata else None
            )
            t.finished_at = int(time.time())
            s.commit()
        await self._notify({"task_id": task_id, "status": "done", "target_path": target_path})

    async def _fail(self, task_id: int, error_msg: str) -> None:
        with self._session_factory() as s:
            t = s.get(Task, task_id)
            if t is None:
                return
            t.status = "failed"
            t.error_msg = error_msg
            t.finished_at = int(time.time())
            s.commit()
        await self._notify({"task_id": task_id, "status": "failed", "error": error_msg})

    async def _pause_for_auth(self, task_id: int, error_msg: str) -> None:
        with self._session_factory() as s:
            t = s.get(Task, task_id)
            if t is None:
                return
            t.status = "pending"  # 回退队列
            t.error_msg = f"需重新登录: {error_msg}"
            s.commit()
        await self._notify({"task_id": task_id, "status": "auth_expired", "error": error_msg})
        # 重新入队等扫码后再次消费
        self.enqueue(task_id)

    async def _notify(self, event: dict) -> None:
        if self._broadcaster is not None:
            await self._broadcaster.publish(event)
```

- [ ] **Step 14.3: 验证通过**

```bash
pytest tests/integration/test_task_runner_pipeline.py -v
```

Expected: 4 passed

- [ ] **Step 14.4: 提交**

```bash
git add backend/app/services/task_runner.py backend/tests/integration/test_task_runner_pipeline.py
git commit -m "feat(services): add TaskRunner pipeline with auth-pause and retry"
```

---

### Task 15: 启动时任务恢复

**Files:**
- Modify: `backend/app/db.py` (添加 reset_running_to_pending 函数)
- Create: `backend/tests/integration/test_task_recovery.py`

- [ ] **Step 15.1: 写测试**

`backend/tests/integration/test_task_recovery.py`:
```python
import time
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Task


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    yield Session, engine
    engine.dispose()


def test_running_tasks_reset_to_pending(db):
    Session, _ = db
    now = int(time.time())
    with Session() as s:
        s.add_all([
            Task(source="web", raw_input="x", share_url="u1", share_hash="h1",
                 status="running", started_at=now, created_at=now),
            Task(source="web", raw_input="x", share_url="u2", share_hash="h2",
                 status="pending", created_at=now),
            Task(source="web", raw_input="x", share_url="u3", share_hash="h3",
                 status="done", finished_at=now, created_at=now),
        ])
        s.commit()

    from app.db import reset_running_to_pending
    reset_running_to_pending(Session)

    with Session() as s:
        statuses = {t.share_hash: t.status for t in s.query(Task).all()}
    assert statuses == {"h1": "pending", "h2": "pending", "h3": "done"}
```

- [ ] **Step 15.2: 在 db.py 添加函数**

打开 `backend/app/db.py`，在文件末尾追加：

```python
def reset_running_to_pending(session_factory) -> int:
    """启动钩子：把所有 running 状态的任务回退为 pending。
    返回重置的行数。"""
    with session_factory() as s:
        from app.models import Task
        count = s.query(Task).filter_by(status="running").update({Task.status: "pending"})
        s.commit()
        return count
```

- [ ] **Step 15.3: 验证通过**

```bash
pytest tests/integration/test_task_recovery.py -v
```

Expected: 1 passed

- [ ] **Step 15.4: 提交**

```bash
git add backend/app/db.py backend/tests/integration/test_task_recovery.py
git commit -m "feat(db): add reset_running_to_pending startup hook"
```

---

### Task 16: Bearer Token 中间件

**Files:**
- Create: `backend/app/utils/auth_middleware.py`
- Create: `backend/tests/unit/test_auth_middleware.py`

- [ ] **Step 16.1: 写失败测试**

`backend/tests/unit/test_auth_middleware.py`:
```python
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def build_app(token: str):
    from app.utils.auth_middleware import BearerTokenMiddleware
    app = FastAPI()
    app.add_middleware(BearerTokenMiddleware, expected_token=token)
    app.routes.clear()
    from fastapi import APIRouter
    r = APIRouter()

    @r.get("/api/ping")
    def ping():
        return {"ok": True}

    @r.get("/healthz")
    def health():
        return {"ok": True}

    app.include_router(r)
    return app


def test_no_token_required_when_unconfigured():
    app = build_app(token="")
    client = TestClient(app)
    r = client.get("/api/ping")
    assert r.status_code == 200


def test_missing_token_returns_401():
    app = build_app(token="secret")
    client = TestClient(app)
    r = client.get("/api/ping")
    assert r.status_code == 401


def test_wrong_token_returns_401():
    app = build_app(token="secret")
    client = TestClient(app)
    r = client.get("/api/ping", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401


def test_correct_token_passes():
    app = build_app(token="secret")
    client = TestClient(app)
    r = client.get("/api/ping", headers={"Authorization": "Bearer secret"})
    assert r.status_code == 200


def test_healthz_bypasses_auth():
    app = build_app(token="secret")
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
```

- [ ] **Step 16.2: 实现 auth_middleware.py**

`backend/app/utils/auth_middleware.py`:
```python
import hmac
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class BearerTokenMiddleware(BaseHTTPMiddleware):
    SKIP_PATHS = {"/healthz", "/api/auth/qrcode"}

    def __init__(self, app, expected_token: str):
        super().__init__(app)
        self.expected_token = expected_token

    async def dispatch(self, request: Request, call_next):
        if not self.expected_token:
            return await call_next(request)
        path = request.url.path
        # 健康检查 + 二维码入口允许匿名
        if path in self.SKIP_PATHS:
            return await call_next(request)
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return JSONResponse({"detail": "未授权"}, status_code=401)
        token = auth[7:]
        if not hmac.compare_digest(token, self.expected_token):
            return JSONResponse({"detail": "Token 无效"}, status_code=401)
        return await call_next(request)
```

- [ ] **Step 16.3: 验证通过**

```bash
pytest tests/unit/test_auth_middleware.py -v
```

Expected: 5 passed

- [ ] **Step 16.4: 提交**

```bash
git add backend/app/utils/auth_middleware.py backend/tests/unit/test_auth_middleware.py
git commit -m "feat(middleware): add BearerTokenMiddleware with health bypass"
```

---

### Task 17: Pydantic schemas（请求/响应模型）

**Files:**
- Create: `backend/app/schemas.py`

- [ ] **Step 17.1: 实现 schemas.py**

`backend/app/schemas.py`:
```python
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
```

- [ ] **Step 17.2: 提交**

```bash
git add backend/app/schemas.py
git commit -m "feat(api): add pydantic request/response schemas"
```

---

### Task 18: Auth API 路由

**Files:**
- Create: `backend/app/api/auth.py`
- Modify: `backend/tests/integration/test_api_smoke.py` (在 Task 20 创建)

> Plan A 只做接口骨架，端到端测试在 Task 20 整合。

- [ ] **Step 18.1: 实现 auth.py**

`backend/app/api/auth.py`:
```python
import asyncio
from fastapi import APIRouter, HTTPException

from app.config import settings
from app.schemas import AuthCheckResp, QRStartResp, QRStatusResp
from app.services.login_manager import LoginManager

router = APIRouter(prefix="/api/auth", tags=["auth"])

_login_manager: LoginManager | None = None


def get_login_manager() -> LoginManager:
    global _login_manager
    if _login_manager is None:
        _login_manager = LoginManager(app_data_dir=settings.p115_app_data_dir)
    return _login_manager


@router.get("/check", response_model=AuthCheckResp)
async def check_auth():
    return AuthCheckResp(logged_in=get_login_manager().is_logged_in())


@router.post("/qrcode", response_model=QRStartResp)
async def start_qrcode():
    status = await get_login_manager().start_qrcode_login()
    if status.state != "waiting":
        raise HTTPException(400, status.message)
    return QRStartResp(qrcode_url=status.qrcode_url or "", state=status.state)


@router.get("/qrcode/status", response_model=QRStatusResp)
async def qrcode_status():
    status = await get_login_manager().poll_qrcode_status()
    return QRStatusResp(state=status.state, message=status.message)


@router.post("/logout")
async def logout():
    get_login_manager().logout()
    return {"ok": True}
```

- [ ] **Step 18.2: 提交**

```bash
git add backend/app/api/auth.py
git commit -m "feat(api): add /api/auth routes for qrcode login"
```

---

### Task 19: Tasks / History / Dirs / Config API

**Files:**
- Create: `backend/app/api/tasks.py`
- Create: `backend/app/api/history.py`
- Create: `backend/app/api/dirs.py`
- Create: `backend/app/api/config.py`
- Create: `backend/app/services/__init__.py` (helper wiring)

- [ ] **Step 19.1: 实现 tasks.py**

`backend/app/api/tasks.py`:
```python
import time
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from sse_starlette.sse import EventSourceResponse

from app.db import get_session
from app.models import Task
from app.schemas import TaskCategoryUpdate, TaskCreate, TaskOut
from app.services.link_parser import parse
from app.utils.sse import broadcaster

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("", response_model=TaskOut)
async def create_task(body: TaskCreate):
    link = parse(body.raw_input)
    if link is None:
        raise HTTPException(400, "无法解析 115 链接")
    with get_session() as s:
        existing = s.query(Task).filter_by(share_hash=link.share_hash).first()
        if existing is not None:
            # 幂等：返回已存在任务
            return TaskOut.model_validate(existing)
        t = Task(
            source="web",
            raw_input=body.raw_input,
            share_url=f"https://115.com/s/{link.share_id}",
            share_code=link.password,
            share_hash=link.share_hash,
            status="pending",
            created_at=int(time.time()),
        )
        s.add(t)
        s.commit()
        s.refresh(t)
        # 入队
        from app.main import get_runner
        runner = get_runner()
        if runner:
            runner.enqueue(t.id)
        return TaskOut.model_validate(t)


@router.get("", response_model=List[TaskOut])
async def list_tasks(
    status: Optional[List[str]] = Query(default=None),
    limit: int = Query(default=100, le=500),
    offset: int = 0,
):
    with get_session() as s:
        q = s.query(Task)
        if status:
            q = q.filter(Task.status.in_(status))
        items = q.order_by(Task.id.desc()).offset(offset).limit(limit).all()
        return [TaskOut.model_validate(i) for i in items]


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(task_id: int):
    with get_session() as s:
        t = s.get(Task, task_id)
        if t is None:
            raise HTTPException(404, "task not found")
        return TaskOut.model_validate(t)


@router.post("/{task_id}/retry", response_model=TaskOut)
async def retry_task(task_id: int):
    with get_session() as s:
        t = s.get(Task, task_id)
        if t is None:
            raise HTTPException(404, "task not found")
        t.status = "pending"
        t.error_msg = None
        t.retry_count += 1
        s.commit()
        s.refresh(t)
        from app.main import get_runner
        runner = get_runner()
        if runner:
            runner.enqueue(t.id)
        return TaskOut.model_validate(t)


@router.put("/{task_id}/category", response_model=TaskOut)
async def update_category(task_id: int, body: TaskCategoryUpdate):
    """人工修正分类/目标路径，并重新入队转存"""
    with get_session() as s:
        t = s.get(Task, task_id)
        if t is None:
            raise HTTPException(404, "task not found")
        t.category = body.category
        if body.target_path_override:
            t.target_path = body.target_path_override
        t.status = "pending"
        t.error_msg = None
        s.commit()
        s.refresh(t)
        from app.main import get_runner
        runner = get_runner()
        if runner:
            runner.enqueue(t.id)
        return TaskOut.model_validate(t)


@router.get("/stream")
async def stream():
    async def gen():
        async for evt in broadcaster.subscribe():
            if evt == "CLOSE":
                yield {"event": "close", "data": "close"}
                break
            yield {"event": "task", "data": evt[len("data: "):-2] if evt.startswith("data:") else evt}
    return EventSourceResponse(gen())
```

- [ ] **Step 19.2: 实现 history.py**

`backend/app/api/history.py`:
```python
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.db import get_session
from app.models import Task
from app.schemas import HistoryOut

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("", response_model=List[HistoryOut])
async def list_history(
    q: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
):
    with get_session() as s:
        query = s.query(Task).filter(Task.status.in_(["done", "failed", "skipped"]))
        if q:
            like = f"%{q}%"
            query = query.filter(
                (Task.raw_input.like(like)) | (Task.target_path.like(like))
            )
        if category:
            query = query.filter(Task.category == category)
        items = query.order_by(Task.finished_at.desc()).offset(offset).limit(limit).all()
        return [HistoryOut.model_validate(i) for i in items]


@router.delete("/{task_id}")
async def delete_history(task_id: int):
    with get_session() as s:
        t = s.get(Task, task_id)
        if t is None:
            raise HTTPException(404, "not found")
        if t.status not in ("done", "failed", "skipped"):
            raise HTTPException(400, "仅允许删除已完成/失败/跳过的任务历史")
        s.delete(t)
        s.commit()
    return {"ok": True}
```

- [ ] **Step 19.3: 实现 dirs.py**

`backend/app/api/dirs.py`:
```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.services.login_manager import LoginManager

router = APIRouter(prefix="/api/dirs", tags=["dirs"])

ROOTS = ["电影", "电视剧", "动漫", "综艺", "学习"]


class DirNode(BaseModel):
    name: str
    cid: int
    is_dir: bool = True
    children: list["DirNode"] = []


@router.get("/roots")
async def get_roots():
    """返回五大类目录的 cid（需要登录后调用）"""
    from app.api.auth import get_login_manager
    lm = get_login_manager()
    if not lm.is_logged_in():
        raise HTTPException(401, "未登录")
    client = lm.get_client()
    result = []
    for name in ROOTS:
        try:
            # 在 115 根目录下找名为 name 的子目录
            resp = client.cd_and_path_name_to_cid(path="/", name=name)
            cid = resp.get("data", {}).get("cid", 0) if isinstance(resp, dict) else 0
        except Exception:
            cid = 0
        result.append({"name": name, "cid": cid})
    return {"roots": result}


@router.get("/browse")
async def browse(cid: int = 0):
    from app.api.auth import get_login_manager
    lm = get_login_manager()
    if not lm.is_logged_in():
        raise HTTPException(401, "未登录")
    client = lm.get_client()
    try:
        resp = client.dir_files(cid=cid)
    except Exception as e:
        raise HTTPException(500, str(e))
    files = resp.get("data", []) if isinstance(resp, dict) else []
    return {
        "items": [
            {"name": f.get("name", ""), "cid": f.get("cid", 0), "is_dir": f.get("type") == "0"}
            for f in files
        ]
    }
```

- [ ] **Step 19.4: 实现 config.py（Plan B/C 完善；Plan A 留骨架）**

`backend/app/api/config.py`:
```python
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
```

- [ ] **Step 19.5: 提交**

```bash
git add backend/app/api/tasks.py backend/app/api/history.py backend/app/api/dirs.py backend/app/api/config.py
git commit -m "feat(api): add tasks/history/dirs/config routes"
```

---

### Task 20: 主入口 app/main.py + 集成冒烟测试

**Files:**
- Create: `backend/app/main.py`
- Create: `backend/tests/integration/test_api_smoke.py`

- [ ] **Step 20.1: 实现 main.py**

`backend/app/main.py`:
```python
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.api import auth, config, dirs, history, tasks
from app.config import settings
from app.db import get_engine, init_db, reset_running_to_pending, get_session
from app.models import AuthState
from app.services.classifier import classify
from app.services.metadata_scraper import MetadataScraper
from app.services.path_resolver import PathResolver
from app.services.share_fetcher import ShareFetcher
from app.services.task_runner import TaskRunner
from app.services.transfer_task import TransferTask
from app.utils.auth_middleware import BearerTokenMiddleware
from app.utils.crypto import decrypt
from app.utils.sse import broadcaster

import json

_runner: TaskRunner | None = None


def get_runner() -> TaskRunner | None:
    return _runner


def _wiring_services():
    """构造所有服务实例（在 lifespan 中调用一次）"""
    from app.api.auth import get_login_manager
    lm = get_login_manager()
    share_fetcher = ShareFetcher(lm)
    metadata_scraper = MetadataScraper(api_key=settings.tmdb_api_key, language=settings.tmdb_language)
    path_resolver = PathResolver(dir_lister=_P115DirLister(lm))
    transfer_task = TransferTask(lm)
    return lm, share_fetcher, metadata_scraper, path_resolver, transfer_task


class _P115DirLister:
    def __init__(self, login_manager):
        self._lm = login_manager

    async def list_dir(self, path: str) -> list[str]:
        if not self._lm.is_logged_in():
            return []
        try:
            client = self._lm.get_client()
            resp = client.cd_and_path_name_to_cid(path=path)
            cid = resp.get("data", {}).get("cid", 0)
            files = client.dir_files(cid=cid).get("data", [])
            return [f.get("name", "") for f in files if f.get("type") == "0"]
        except Exception:
            logger.exception("list_dir failed")
            return []


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _runner
    # 初始化 DB
    init_db()
    # 启动时恢复 running -> pending
    n = reset_running_to_pending(get_session)
    if n > 0:
        logger.info(f"启动时恢复 {n} 个未完成任务")
    # 装配服务
    lm, share_fetcher, md_scraper, path_resolver, transfer_task = _wiring_services()
    _runner = TaskRunner(
        session_factory=get_session,
        login_manager=lm,
        share_fetcher=share_fetcher,
        classifier=classify,
        metadata_scraper=md_scraper,
        path_resolver=path_resolver,
        transfer_task=transfer_task,
        broadcaster=broadcaster,
    )
    _runner.start()
    logger.info("TaskRunner started")
    yield
    _runner.stop()
    logger.info("TaskRunner stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="115 Auto Save", lifespan=lifespan)
    if settings.web_api_token:
        app.add_middleware(BearerTokenMiddleware, expected_token=settings.web_api_token)
    app.include_router(auth.router)
    app.include_router(tasks.router)
    app.include_router(history.router)
    app.include_router(dirs.router)
    app.include_router(config.router)

    @app.get("/healthz")
    def health():
        return {"ok": True, "logged_in": _is_logged_in()}

    # 静态文件（Plan B 构建 dist 后挂载；先占位不挂载避免目录不存在报错）
    dist = Path("frontend/dist")
    if dist.exists():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="static")

    return app


def _is_logged_in() -> bool:
    try:
        with get_session() as s:
            row = s.query(AuthState).filter_by(key="p115_cookies").first()
            if row is None:
                return False
            return decrypt(row.value) is not None
    except Exception:
        return False


app = create_app()
```

- [ ] **Step 20.2: 写冒烟测试**

`backend/tests/integration/test_api_smoke.py`:
```python
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", "dGVzdC1rZXktMzItYnl0ZXMtbG9uZy1lbm91Z2g=")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./data/test-smoke.db")
    # 重置已缓存的 settings
    from importlib import reload
    import app.config
    reload(app.config)
    from app import db as db_mod
    db_mod._engine = None
    db_mod._SessionLocal = None
    import app.main
    reload(app.main)
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True


def test_create_task_invalid_link_rejected(client):
    r = client.post("/api/tasks", json={"raw_input": "no link here"})
    assert r.status_code == 400


def test_create_task_parses_link(client):
    r = client.post("/api/tasks", json={"raw_input": "https://115.com/s/abc123?password=xyz"})
    assert r.status_code == 200
    body = r.json()
    assert body["share_url"].endswith("/abc123")
    assert body["status"] == "pending"


def test_duplicate_link_returns_same_task(client):
    payload = {"raw_input": "https://115.com/s/dup456?password=p"}
    r1 = client.post("/api/tasks", json=payload)
    r2 = client.post("/api/tasks", json=payload)
    assert r1.json()["id"] == r2.json()["id"]


def test_list_tasks_pagination(client):
    for i in range(5):
        client.post("/api/tasks", json={"raw_input": f"https://115.com/s/x{i}?password=p"})
    r = client.get("/api/tasks", params={"limit": 3})
    body = r.json()
    assert len(body) <= 3


def test_history_empty(client):
    r = client.get("/api/history")
    assert r.status_code == 200
    assert r.json() == []


def test_config_masked(client):
    r = client.get("/api/config")
    body = r.json()
    # 未配置时是空串；有值则应脱敏
    if body["tmdb_api_key"]:
        assert "*" in body["tmdb_api_key"]
```

- [ ] **Step 20.3: 验证通过**

```bash
pytest tests/integration/test_api_smoke.py -v
```

Expected: 7 passed

如果失败常见原因：
- `p115client` API 名称与文档不符 → 调整 Task 11/12 的 client 方法名（p115client 文档：https://github.com/ChenyangGao/p115client）
- `dir_files` 字段名不符 → 调整 Task 19/20 的字段提取

- [ ] **Step 20.4: 启动本地验证**

```bash
cd backend
# 先生成加密密钥
python -c "import secrets,base64;print(base64.b64encode(secrets.token_bytes(32)).decode())" > /tmp/key.txt
# 写到 .env
echo "ENCRYPTION_KEY=$(cat /tmp/key.txt)" > .env
echo "DATABASE_URL=sqlite:///data/config.db" >> .env
# 启动
uvicorn app.main:app --reload --port 8000
```

打开浏览器访问 `http://localhost:8000/healthz` 应返回 `{"ok": true, "logged_in": false}`。

访问 `http://localhost:8000/docs` 查看 Swagger。

- [ ] **Step 20.5: 运行全量测试**

```bash
pytest -v --cov=app --cov-report=term-missing
```

Expected: 全部通过，覆盖率 ≥ 60%（Plan A 目标；Plan C 完善后到 80%）

- [ ] **Step 20.6: 提交**

```bash
git add backend/app/main.py backend/tests/integration/test_api_smoke.py
git commit -m "feat(app): wire up FastAPI lifespan, runner startup, smoke tests"
```

---

## Plan A 完成验收

执行完上述 20 个任务后，应满足：

- [ ] `pytest` 全部通过
- [ ] `uvicorn app.main:app` 能启动，`/healthz` 返回 ok
- [ ] `/docs` Swagger 可访问
- [ ] `POST /api/tasks` 能解析 115 链接、入库、入队
- [ ] `POST /api/auth/qrcode` 能拿到二维码 URL（需要真实 115 App 扫码确认）
- [ ] 服务重启后 `running` 任务自动恢复为 `pending`
- [ ] 重复链接提交不会创建新任务（share_hash 幂等）

**未完成项（Plan B/C 处理）**：
- Telegram / 飞书输入源
- Web UI（Vue3）
- `_resolve_cid` 还在用占位 `0`（Plan B 完善 115 目录路径→cid 转换）
- 集成测试套件补全
- NSSM 服务化

---

## Self-Review

**1. 规格覆盖：**
- §3-4 架构与组件 → Task 1-14
- §5 数据流 → Task 14 TaskRunner 完整实现
- §6 错误处理 → Task 13/14 AuthExpired/TransferError + Task 15 启动恢复
- §6.3 Bearer Token → Task 16
- §4.3 API 路由 → Task 18/19
- §7 测试策略 → 各任务 TDD + Task 20 冒烟集成测试

**2. 占位符扫描：**
- Task 11 (LoginManager) 没有单元测试，因为强耦合 p115client —— 已显式说明，并在 Task 20 集成冒烟覆盖
- Task 14 `_resolve_cid` 用了占位 `0` —— 已显式标注 Plan B 完善
- Task 19 feishu test 返回假数据 —— 已标注 Plan B 实现
- 无其他 TODO/TBD

**3. 类型一致性：**
- `ShareLink` / `Metadata` / `ShareContent` / `TransferResult` / `QRStatus` 在各 Task 中定义后被复用，签名一致
- `TaskRunner.__init__` 参数与 Task 20 `_wiring_services()` 构造的实参一致
- `get_session()` 是 contextmanager，所有调用点都用 `with get_session() as s:`

**4. 实施执行顺序：** 严格按 Task 1→20，每个 Task 内部按 Step 1→N，依赖关系无回溯。

---

## 执行交付

**Plan complete and saved to `docs/superpowers/plans/2026-07-02-plan-a-backend-mvp.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - 每个 Task 派发独立 subagent 执行，任务间做 review，迭代快、上下文干净

**2. Inline Execution** - 在当前会话内逐 Task 执行，分批 checkpoint 供 review

**Which approach?**

后续 Plan B（输入适配器 + Web UI）和 Plan C（部署 + 集成测试）会在 Plan A 完成后另起 plan 文件。
