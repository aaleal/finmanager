"""Typed access to the ``Setting`` table."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.models.core import Setting

# --- Known keys --------------------------------------------------------------
CONFIDENCE_AUTO_ACCEPT = "confidence.auto_accept"
CONFIDENCE_REVIEW = "confidence.review"
BRICKSET_ENABLED = "lego.brickset.enabled"
BRICKSET_API_KEY = "lego.brickset.api_key"
LEGO_STALE_VALUE_DAYS = "lego.stale_value_days"

DEFAULTS: dict[str, Any] = {
    CONFIDENCE_AUTO_ACCEPT: 0.90,
    CONFIDENCE_REVIEW: 0.60,
    BRICKSET_ENABLED: False,  # every external provider is off by default
    BRICKSET_API_KEY: "",
    LEGO_STALE_VALUE_DAYS: 180,
}


def get(
    db: DbSession,
    key: str,
    *,
    scope: str = "GLOBAL",
    scope_id: uuid.UUID | None = None,
    default: Any = None,
) -> Any:
    row = db.scalar(
        select(Setting).where(
            Setting.key == key, Setting.scope == scope, Setting.scope_id.is_(scope_id)
        )
    )
    if row is None:
        return DEFAULTS.get(key, default)
    return row.value.get("value", DEFAULTS.get(key, default))


def set_value(
    db: DbSession,
    key: str,
    value: Any,
    *,
    scope: str = "GLOBAL",
    scope_id: uuid.UUID | None = None,
    updated_by: uuid.UUID | None = None,
) -> Setting:
    row = db.scalar(
        select(Setting).where(
            Setting.key == key, Setting.scope == scope, Setting.scope_id.is_(scope_id)
        )
    )
    if row is None:
        row = Setting(scope=scope, scope_id=scope_id, key=key, value={"value": value})
        db.add(row)
    else:
        row.value = {"value": value}
    row.updated_by = updated_by
    row.updated_at = dt.datetime.now(dt.UTC)
    db.flush()
    return row


def stale_value_days(db: DbSession) -> int:
    return int(get(db, LEGO_STALE_VALUE_DAYS, default=180))
