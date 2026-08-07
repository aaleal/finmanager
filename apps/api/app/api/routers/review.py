"""The shared Review Queue.

One generic surface consumed by every module: it serves `ReviewTask` rows as
`{subject_type, subject_id, module, confidence, suggested_payload,
decision_reasons}` and accepts Confirm / Fix / Dismiss. M9 produces no tasks —
this is the shell every ingestion-heavy module will plug into.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import CurrentAuth, Db, Writer, household_entity_ids
from app.core.errors import NotFound
from app.models.core import ReviewTask
from app.schemas.common import ApiModel, Page

router = APIRouter(prefix="/review", tags=["review"])


class ReviewTaskOut(ApiModel):
    id: uuid.UUID
    entity_id: uuid.UUID
    module: str
    subject_type: str
    subject_id: uuid.UUID
    confidence: float | None
    suggested_payload: dict[str, Any]
    decision_reasons: list[Any]
    status: str
    title: str | None
    created_at: dt.datetime
    resolved_at: dt.datetime | None


class ReviewResolution(BaseModel):
    action: Literal["CONFIRMED", "FIXED", "DISMISSED"]
    payload: dict[str, Any] | None = None


class ReviewSummary(BaseModel):
    pending: int
    by_module: dict[str, int]


@router.get("/summary", response_model=ReviewSummary)
def summary(ctx: CurrentAuth, db: Db) -> ReviewSummary:
    scope = [ctx.active_entity_id] if ctx.active_entity_id else household_entity_ids(db, ctx)
    rows = db.execute(
        select(ReviewTask.module, func.count())
        .where(ReviewTask.entity_id.in_(scope), ReviewTask.status == "PENDING")
        .group_by(ReviewTask.module)
    ).all()
    by_module = {row[0]: row[1] for row in rows}
    return ReviewSummary(pending=sum(by_module.values()), by_module=by_module)


@router.get("/tasks", response_model=Page[ReviewTaskOut])
def list_tasks(
    ctx: CurrentAuth,
    db: Db,
    status: str = "PENDING",
    module: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> Page[ReviewTaskOut]:
    scope = [ctx.active_entity_id] if ctx.active_entity_id else household_entity_ids(db, ctx)
    stmt = select(ReviewTask).where(ReviewTask.entity_id.in_(scope), ReviewTask.status == status)
    if module:
        stmt = stmt.where(ReviewTask.module == module)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(ReviewTask.confidence.asc().nullsfirst(), ReviewTask.created_at)
        .limit(page_size)
        .offset((page - 1) * page_size)
    ).all()
    return Page(
        items=[ReviewTaskOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/tasks/{task_id}/resolve", response_model=ReviewTaskOut)
def resolve(task_id: uuid.UUID, body: ReviewResolution, ctx: Writer, db: Db) -> ReviewTaskOut:
    task = db.get(ReviewTask, task_id)
    if task is None:
        raise NotFound("Tarefa não encontrada.")
    task.status = body.action
    task.resolved_at = dt.datetime.now(dt.UTC)
    task.resolved_by = ctx.user.id
    if body.payload:
        task.suggested_payload = {**task.suggested_payload, **body.payload}
    db.flush()
    return ReviewTaskOut.model_validate(task)
