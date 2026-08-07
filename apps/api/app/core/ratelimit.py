"""Fixed-window rate limiter backed by Redis.

Applied to the two endpoints that actually matter for abuse: login and upload
(OWASP rubric). Fails open if Redis is unreachable — availability of the whole
app must not depend on the limiter.
"""

from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from app.core.redis_client import get_redis

RULES: list[tuple[str, str, int, int]] = [
    # (method, path prefix, max requests, window seconds)
    ("POST", "/api/auth/login", 10, 300),
    ("POST", "/api/auth/password", 10, 300),
    ("PUT", "/api/lego", 60, 60),
    ("POST", "/api/lego/models/lookup", 30, 60),
]


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        rule = next(
            (r for r in RULES if request.method == r[0] and request.url.path.startswith(r[1])),
            None,
        )
        if rule is None:
            return await call_next(request)

        _, prefix, limit, window = rule
        client = request.client.host if request.client else "unknown"
        key = f"ratelimit:{prefix}:{client}"
        try:
            redis = get_redis()
            count = int(redis.incr(key))  # type: ignore[arg-type]
            if count == 1:
                redis.expire(key, window)
            if count > limit:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Demasiados pedidos. Tente novamente daqui a pouco."},
                )
        except Exception:
            return await call_next(request)

        return await call_next(request)
