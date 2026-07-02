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
