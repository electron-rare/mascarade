"""Lightweight in-memory rate limiter middleware (token bucket per IP)."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("mascarade.middleware.rate_limit")

# Paths exempt from rate limiting (health checks, metrics scraping).
_EXEMPT_PATHS = frozenset({"/health", "/metrics"})


@dataclass
class _Bucket:
    tokens: float = 60.0
    last_refill: float = field(default_factory=time.monotonic)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token-bucket rate limiter per client IP.

    Parameters
    ----------
    app:
        ASGI application.
    requests_per_minute:
        Sustained request rate (bucket refill rate).  Default 60.
    burst:
        Maximum burst size (bucket capacity).  Default 120.
    """

    def __init__(self, app, *, requests_per_minute: int = 60, burst: int = 120):
        super().__init__(app)
        self._rate = requests_per_minute / 60.0  # tokens per second
        self._burst = float(burst)
        self._buckets: dict[str, _Bucket] = defaultdict(
            lambda: _Bucket(tokens=self._burst)
        )
        self._last_cleanup = time.monotonic()

    async def dispatch(self, request: Request, call_next):
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        bucket = self._buckets[client_ip]

        now = time.monotonic()
        elapsed = now - bucket.last_refill
        bucket.tokens = min(self._burst, bucket.tokens + elapsed * self._rate)
        bucket.last_refill = now

        if bucket.tokens < 1.0:
            retry_after = int((1.0 - bucket.tokens) / self._rate) + 1
            logger.warning("Rate limit exceeded for %s", client_ip)
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
                headers={"Retry-After": str(retry_after)},
            )

        bucket.tokens -= 1.0

        # Periodic cleanup of stale buckets (every 5 minutes)
        if now - self._last_cleanup > 300:
            self._last_cleanup = now
            stale = [
                ip
                for ip, b in self._buckets.items()
                if now - b.last_refill > 600
            ]
            for ip in stale:
                del self._buckets[ip]

        return await call_next(request)
