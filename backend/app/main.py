from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.api import auth, config, dirs, history, tasks
from app.config import settings
from app.db import init_db, reset_running_to_pending, get_session
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

_runner: TaskRunner | None = None


def get_runner() -> TaskRunner | None:
    """供 API 路由获取全局 TaskRunner 实例（用于入队）。"""
    return _runner


class _P115DirLister:
    """PathResolver 的 115 实现：通过 p115client 列出指定路径下的子目录名。"""

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
            # 仅记录异常类型，避免泄露 cookie 等敏感信息
            logger.exception("list_dir failed")
            return []


def _wiring_services():
    """构造所有服务实例（在 lifespan 中调用一次）"""
    lm = auth.get_login_manager()
    share_fetcher = ShareFetcher(lm)
    metadata_scraper = MetadataScraper(
        api_key=settings.tmdb_api_key, language=settings.tmdb_language
    )
    path_resolver = PathResolver(dir_lister=_P115DirLister(lm))
    transfer_task = TransferTask(lm)
    return lm, share_fetcher, metadata_scraper, path_resolver, transfer_task


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _runner
    # 初始化 DB（幂等：表已存在则跳过）
    init_db()
    # 启动时恢复 running -> pending（防止重启后任务卡死）
    n = reset_running_to_pending(get_session)
    if n > 0:
        logger.info("启动时恢复 {} 个未完成任务", n)
    # 装配核心服务
    lm, share_fetcher, md_scraper, path_resolver, transfer_task = _wiring_services()

    # 装配 Telegram 适配器（start() 内部 token 缺失自动跳过）
    from app.adapters.telegram_bot import TelegramAdapter
    tg_adapter = TelegramAdapter(
        bot_token=settings.telegram_bot_token,
        allowed_chat_ids=settings.telegram_allowed_chat_ids,
        allowed_user_ids=settings.telegram_allowed_user_ids,
        admin_user_id=settings.telegram_admin_user_id,
    )

    _runner = TaskRunner(
        session_factory=get_session,
        login_manager=lm,
        share_fetcher=share_fetcher,
        classifier=classify,
        metadata_scraper=md_scraper,
        path_resolver=path_resolver,
        transfer_task=transfer_task,
        broadcaster=broadcaster,
        tg_adapter=tg_adapter,
    )
    _runner.start()

    # 装配飞书适配器（配置缺失时跳过）
    feishu_adapter = None
    if settings.feishu_app_id and settings.feishu_app_token:
        from app.adapters.feishu_client import FeishuClient
        from app.adapters.feishu_sheet import FeishuAdapter
        feishu_client = FeishuClient(
            app_id=settings.feishu_app_id,
            app_secret=settings.feishu_app_secret,
            app_token=settings.feishu_app_token,
            table_id=settings.feishu_table_id,
            link_column=settings.feishu_link_column,
            code_column=settings.feishu_code_column,
            remark_column=settings.feishu_remark_column,
        )
        feishu_adapter = FeishuAdapter(
            client=feishu_client,
            interval_minutes=settings.feishu_poll_interval_minutes,
            tg_adapter=tg_adapter,
        )
        try:
            feishu_adapter.start_scheduler()
        except Exception as e:
            logger.error("feishu scheduler start failed: {}", type(e).__name__)

    # 启动 TG 适配器（最后启动，避免漏消息）
    try:
        await tg_adapter.start()
    except Exception as e:
        logger.error("telegram adapter start failed: {}", type(e).__name__)

    logger.info("TaskRunner + adapters started")
    try:
        yield
    finally:
        if feishu_adapter:
            try:
                feishu_adapter.stop_scheduler()
            except Exception as e:
                logger.error("feishu scheduler stop failed: {}", type(e).__name__)
        try:
            await tg_adapter.stop()
        except Exception as e:
            logger.error("telegram adapter stop failed: {}", type(e).__name__)
        _runner.stop()
        logger.info("TaskRunner + adapters stopped")


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

    # 静态文件：从 backend/app/main.py 解析到项目根目录的 frontend/dist
    # 这样无论从 backend/ 还是项目根启动都能正确挂载
    dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="static")

        # SPA fallback：对非 API/docs 的 GET 请求返回 index.html
        # 解决 createWebHistory 模式下直接访问 /tasks 等子路由 404 的问题
        @app.exception_handler(404)
        async def spa_fallback(request: Request, exc):
            path = request.url.path
            if (request.method != "GET"
                    or path.startswith("/api")
                    or path.startswith("/docs")
                    or path.startswith("/openapi")
                    or path.startswith("/healthz")
                    or path.startswith("/redoc")):
                return JSONResponse({"detail": "Not Found"}, status_code=404)
            index = dist / "index.html"
            if index.exists():
                return FileResponse(str(index))
            return JSONResponse({"detail": "Not Found"}, status_code=404)

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
