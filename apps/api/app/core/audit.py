"""AuditLog writer — the single mechanism for reconstructing historical state."""

from __future__ import annotations

import datetime as dt
import decimal
import uuid
from typing import Any

from sqlalchemy.orm import Session as DbSession

from app.models.core import AuditLog


def _jsonable(value: Any) -> Any:
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dt.datetime | dt.date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    return value


def snapshot(obj: Any, fields: list[str] | None = None) -> dict[str, Any]:
    """Serialize an ORM row into a JSON-safe dict for ``before`` / ``after``."""
    if obj is None:
        return {}
    columns = fields or [c.name for c in obj.__table__.columns]
    return {name: _jsonable(getattr(obj, name, None)) for name in columns}


def record(
    db: DbSession,
    *,
    action: str,
    table_name: str,
    record_id: uuid.UUID,
    entity_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        entity_id=entity_id,
        actor_user_id=actor_user_id,
        action=action,
        table_name=table_name,
        record_id=record_id,
        before=before,
        after=after,
        reason=reason,
    )
    db.add(entry)
    return entry
