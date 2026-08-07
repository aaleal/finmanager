"""Cross-module home dashboard.

Modules register a summary tile here as they ship, so the landing page grows with
the product instead of being rewritten each phase. Sprint 1 registers LEGO.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import desc, select

from app.api.deps import CurrentAuth, Db, household_entity_ids
from app.models.core import AuditLog
from app.services import lego_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class ModuleTile(BaseModel):
    key: str
    label: str
    status: Literal["LIVE", "PLANNED"]
    primary_value: str | None = None
    primary_label: str | None = None
    secondary_value: str | None = None
    secondary_label: str | None = None
    href: str | None = None


class ActivityItem(BaseModel):
    id: str
    action: str
    table_name: str
    record_id: str
    created_at: dt.datetime
    actor_display_name: str | None = None


class DashboardOut(BaseModel):
    tiles: list[ModuleTile]
    pending_reviews: int
    recent_activity: list[ActivityItem]


PLANNED_MODULES = [
    ("supermarket", "Supermercado"),
    ("banking", "Banca"),
    ("health", "Saúde"),
    ("utilities", "Utilidades"),
    ("vehicles", "Veículos"),
    ("assets", "Património"),
]


def _eur(value: Decimal) -> str:
    return f"{value:.2f}"


@router.get("", response_model=DashboardOut)
def dashboard(ctx: CurrentAuth, db: Db) -> DashboardOut:
    entity_ids = household_entity_ids(db, ctx)
    lego = lego_service.overview(db, entity_ids=entity_ids, active_entity_id=ctx.active_entity_id)

    tiles = [
        ModuleTile(
            key="lego",
            label="Coleção LEGO",
            status="LIVE",
            primary_value=_eur(lego.total_value_eur),
            primary_label="Valor atual",
            secondary_value=str(lego.copies_owned),
            secondary_label="Cópias",
            href="/lego",
        )
    ]
    tiles += [ModuleTile(key=key, label=label, status="PLANNED") for key, label in PLANNED_MODULES]

    rows = (
        db.execute(
            select(AuditLog)
            .where(AuditLog.entity_id.in_(entity_ids) | AuditLog.entity_id.is_(None))
            .order_by(desc(AuditLog.created_at))
            .limit(12)
        )
        .scalars()
        .all()
    )

    return DashboardOut(
        tiles=tiles,
        pending_reviews=0,
        recent_activity=[
            ActivityItem(
                id=str(row.id),
                action=row.action,
                table_name=row.table_name,
                record_id=str(row.record_id),
                created_at=row.created_at,
            )
            for row in rows
        ],
    )
