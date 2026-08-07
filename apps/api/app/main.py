from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.api.routers import (
    auth,
    dashboard,
    documents,
    household,
    lego,
    reference,
    review,
    transactions,
)
from app.api.routers import (
    settings as settings_router,
)
from app.core.config import settings
from app.core.db import engine
from app.core.errors import AppError
from app.core.ratelimit import RateLimitMiddleware

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("finmanager")

app = FastAPI(
    title="FinManager API",
    version="0.1.0",
    description=(
        "Self-hosted household finance platform. Portuguese-first (pt-PT), "
        "EUR-only, privacy-first."
    ),
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        return response


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)

if settings.is_dev:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code, **getattr(exc, "extra", {})},
    )


@app.get("/api/health", tags=["system"])
def health() -> dict[str, str]:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok", "env": settings.app_env}


for router in (
    auth.router,
    household.router,
    reference.router,
    lego.router,
    documents.router,
    review.router,
    transactions.router,
    settings_router.router,
    dashboard.router,
):
    app.include_router(router, prefix="/api")
