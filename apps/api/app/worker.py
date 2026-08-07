"""Celery application.

No M9 work is queued — the module has no background jobs by design. The worker is
provisioned in Phase 0 so ingestion-heavy modules land on a proven runtime, and it
already carries the `ProcessingJob` idempotency contract.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from celery import Celery
from sqlalchemy import select

from app.core.config import settings
from app.core.db import session_scope
from app.models.core import ProcessingJob

celery_app = Celery("finmanager", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.tz,
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
)


def claim_job(idempotency_key: str, job_type: str, payload: dict[str, Any]) -> bool:
    """Idempotency gate: returns ``False`` if this key already succeeded."""
    with session_scope() as db:
        job = db.scalar(
            select(ProcessingJob).where(ProcessingJob.idempotency_key == idempotency_key)
        )
        if job is None:
            job = ProcessingJob(
                idempotency_key=idempotency_key,
                job_type=job_type,
                payload=payload,
                status="RUNNING",
                attempts=1,
                started_at=dt.datetime.now(dt.UTC),
            )
            db.add(job)
            return True
        if job.status == "SUCCEEDED":
            return False
        job.status = "RUNNING"
        job.attempts += 1
        job.started_at = dt.datetime.now(dt.UTC)
        return True


@celery_app.task(name="finmanager.ping")
def ping() -> str:
    return "pong"
