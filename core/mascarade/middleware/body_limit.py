"""Middleware to reject request bodies exceeding a size limit."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

MAX_BODY_BYTES = 10 * 1024 * 1024  # 10 MB default


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests whose Content-Length exceeds *max_bytes*.

    Parameters
    ----------
    app:
        ASGI application.
    max_bytes:
        Maximum allowed request body size in bytes.  Default 10 MB.
    """

    def __init__(self, app, *, max_bytes: int = MAX_BODY_BYTES):
        super().__init__(app)
        self._max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self._max_bytes:
            return JSONResponse(
                status_code=413,
                content={
                    "detail": f"Request body too large (max {self._max_bytes // 1024 // 1024} MB)"
                },
            )
        return await call_next(request)
