"""Background Brickset asset fetch (ADR-0049).

Adding a set only needs Brickset for its catalogue data (name, theme, RRP, ...) —
that's a single fast lookup, already resolved before `create_model` ever runs.
The slow part is the *extra* photographs and manuals, each one its own HTTP
download; ADR-0049 moves that off the request/commit path entirely and onto the
Celery worker as two independent jobs per set (images, manuals), tracked as
`ProcessingJob` rows so the user gets visibility, cancel and retry instead of a
frozen progress bar.

`queue_brickset_assets` is the only function called from a request path — it is
DB-only (create two QUEUED rows, commit, dispatch) and therefore fast. Actual
work happens in `run_job`, invoked by the Celery tasks in `app.worker`; it is
kept free of any Celery import so it can be unit-tested by calling it directly.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.core.errors import NotFound, ValidationError
from app.models.core import ProcessingJob
from app.models.lego import LegoSetModel
from app.schemas.lego import BricksetJobOut
from app.services import lego_service

JOB_TYPE_IMAGES = "lego_brickset_images"
JOB_TYPE_MANUALS = "lego_brickset_manuals"
JOB_TYPES = (JOB_TYPE_IMAGES, JOB_TYPE_MANUALS)

_ACTIVE_STATUSES = ("QUEUED", "RUNNING")
_RETRYABLE_STATUSES = ("FAILED", "CANCELLED")


def _idempotency_key(job_type: str, model_id: uuid.UUID) -> str:
    return f"{job_type}:{model_id}"


def queue_brickset_assets(
    db: DbSession, model: LegoSetModel, *, actor_user_id: uuid.UUID
) -> list[ProcessingJob]:
    """Queues the images + manuals jobs for a genuinely new model. A MOC has
    nothing on Brickset, so it queues nothing. Re-calling this for a model that
    already has an active job for a given type reuses that job instead of
    double-queueing (e.g. the set creation flow calling it more than once)."""
    if not model.set_number:
        return []

    jobs: list[ProcessingJob] = []
    newly_queued: list[ProcessingJob] = []
    for job_type in JOB_TYPES:
        key = _idempotency_key(job_type, model.id)
        existing = db.scalar(
            select(ProcessingJob).where(
                ProcessingJob.idempotency_key == key,
                ProcessingJob.status.in_(_ACTIVE_STATUSES),
            )
        )
        if existing is not None:
            jobs.append(existing)
            continue
        job = ProcessingJob(
            idempotency_key=key,
            job_type=job_type,
            entity_id=model.entity_id,
            status="QUEUED",
            payload={
                "lego_set_model_id": str(model.id),
                "actor_user_id": str(actor_user_id),
                "set_number": model.set_number,
                "set_name": model.name,
            },
        )
        db.add(job)
        db.flush()
        jobs.append(job)
        newly_queued.append(job)

    # Committed here, not left for the caller: the worker picks this up in a
    # different process over its own DB connection, so the row must already be
    # durable by the time it's dispatched below — there is no shared
    # not-yet-committed transaction to simply wait out.
    db.commit()
    for job in newly_queued:
        _dispatch(job)
    return jobs


def _dispatch(job: ProcessingJob) -> None:
    # Imported lazily: `app.worker` importing this module back (for `run_job`)
    # would otherwise be a circular import at module load time.
    from app.worker import lego_import_images_task, lego_import_manuals_task

    task = lego_import_images_task if job.job_type == JOB_TYPE_IMAGES else lego_import_manuals_task
    task.delay(str(job.id))


def run_job(db: DbSession, job: ProcessingJob) -> None:
    """The actual work a Celery task delegates to. Kept Celery-free so tests can
    call it directly instead of going through a real worker/broker."""
    if job.status == "CANCELLED":
        return

    model = db.get(LegoSetModel, uuid.UUID(job.payload["lego_set_model_id"]))
    actor_user_id = uuid.UUID(job.payload["actor_user_id"])
    job.status = "RUNNING"
    job.started_at = dt.datetime.now(dt.UTC)
    db.commit()

    def should_continue() -> bool:
        # A fresh SELECT under READ COMMITTED sees a cancel committed by any
        # other request/process in the meantime — this is the only signal the
        # cancel endpoint has to reach an already-running job.
        db.refresh(job)
        return job.status != "CANCELLED"

    try:
        if model is None:
            raise NotFound("O conjunto já não existe.")
        if job.job_type == JOB_TYPE_IMAGES:
            lego_service.import_model_images_from_brickset(
                db, model, actor_user_id=actor_user_id, should_continue=should_continue
            )
        else:
            lego_service.import_model_instructions_from_brickset(
                db, model, actor_user_id=actor_user_id, should_continue=should_continue
            )
    except Exception as exc:
        db.rollback()
        db.refresh(job)
        if job.status == "CANCELLED":
            return
        job.status = "FAILED"
        job.last_error = str(exc)
        job.completed_at = dt.datetime.now(dt.UTC)
        db.commit()
        return

    db.refresh(job)
    if job.status == "CANCELLED":
        return
    job.status = "SUCCEEDED"
    job.completed_at = dt.datetime.now(dt.UTC)
    db.commit()


def cancel_job(db: DbSession, job: ProcessingJob) -> None:
    if job.status not in _ACTIVE_STATUSES:
        raise ValidationError("Este processo já terminou — não é possível cancelá-lo.")
    job.status = "CANCELLED"
    job.completed_at = dt.datetime.now(dt.UTC)
    db.commit()


def retry_job(db: DbSession, job: ProcessingJob) -> None:
    if job.status not in _RETRYABLE_STATUSES:
        raise ValidationError("Este processo ainda está em curso.")
    job.status = "QUEUED"
    job.attempts += 1
    job.last_error = None
    job.started_at = None
    job.completed_at = None
    db.commit()
    _dispatch(job)


def get_job(db: DbSession, job_id: uuid.UUID, *, entity_ids: list[uuid.UUID]) -> ProcessingJob:
    job = db.get(ProcessingJob, job_id)
    if job is None or job.job_type not in JOB_TYPES or job.entity_id not in entity_ids:
        raise NotFound("Processo desconhecido.")
    return job


def list_jobs(db: DbSession, *, entity_ids: list[uuid.UUID]) -> list[ProcessingJob]:
    return list(
        db.scalars(
            select(ProcessingJob)
            .where(
                ProcessingJob.job_type.in_(JOB_TYPES),
                ProcessingJob.entity_id.in_(entity_ids),
            )
            .order_by(ProcessingJob.created_at.desc())
            .limit(200)
        )
    )


def job_out(job: ProcessingJob) -> BricksetJobOut:
    return BricksetJobOut(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        last_error=job.last_error,
        lego_set_model_id=uuid.UUID(job.payload["lego_set_model_id"]),
        set_number=job.payload.get("set_number"),
        set_name=job.payload.get("set_name") or "—",
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )
