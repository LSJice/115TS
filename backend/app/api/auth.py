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
