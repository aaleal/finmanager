from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

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
    prices,
    products,
    reference,
    review,
    setup,
    supermarket,
    transactions,
)
from app.api.routers import (
    settings as settings_router,
)
from app.core.config import settings
from app.core.db import engine, session_scope
from app.core.errors import AppError
from app.core.ratelimit import RateLimitMiddleware
from app.services import reference_data, settings_service

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("finmanager")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Reference data ships with the release, so every boot re-asserts it.

    The entrypoint has already run ``alembic upgrade head`` by the time this
    runs. A failure here is logged and swallowed: a missing category must not
    keep the API from serving the rest of the household's data.
    """
    try:
        if not settings.bootstrap_reference_data:
            yield
            return
        with session_scope() as db:
            created = reference_data.ensure_all(db)
            if settings_service.ensure_brickset_from_env(db):
                logger.info("bootstrap: Brickset enabled from BRICKSET_API_KEY")
        if any(created.values()):
            logger.info("bootstrap: reference data created %s", created)
    except Exception:  # pragma: no cover - defensive, boot must not depend on it
        logger.exception("bootstrap: could not ensure reference data")
    yield


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
    lifespan=lifespan,
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
    setup.router,
    auth.router,
    household.router,
    reference.router,
    lego.router,
    *supermarket.routers,
    *products.routers,
    *prices.routers,
    documents.router,
    review.router,
    transactions.router,
    settings_router.router,
    dashboard.router,
):
    app.include_router(router, prefix="/api")
