from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import CurrentAuth, Db, Owner
from app.services import settings_service

router = APIRouter(prefix="/settings", tags=["settings"])

# Only these keys are readable/writable over the API; anything else stays internal.
EXPOSED_KEYS = {
    settings_service.CONFIDENCE_AUTO_ACCEPT,
    settings_service.CONFIDENCE_REVIEW,
    settings_service.BRICKSET_ENABLED,
    settings_service.BRICKSET_API_KEY,
    settings_service.LEGO_STALE_VALUE_DAYS,
}

SECRET_KEYS = {settings_service.BRICKSET_API_KEY}


class SettingsOut(BaseModel):
    values: dict[str, Any]


class SettingsUpdate(BaseModel):
    values: dict[str, Any]


def _read(db: Db) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in sorted(EXPOSED_KEYS):
        value = settings_service.get(db, key)
        # Never echo a provider credential back to the browser.
        result[key] = bool(value) if key in SECRET_KEYS else value
    return result


@router.get("", response_model=SettingsOut)
def read_settings(ctx: CurrentAuth, db: Db) -> SettingsOut:
    return SettingsOut(values=_read(db))


@router.patch("", response_model=SettingsOut)
def update_settings(payload: SettingsUpdate, ctx: Owner, db: Db) -> SettingsOut:
    for key, value in payload.values.items():
        if key not in EXPOSED_KEYS:
            continue
        settings_service.set_value(db, key, value, updated_by=ctx.user.id)
    db.flush()
    return SettingsOut(values=_read(db))
