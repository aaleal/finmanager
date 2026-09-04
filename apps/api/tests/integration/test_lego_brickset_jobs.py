"""Protects: ADR-0049 «images and manuals are fetched in the background».

`queue_brickset_assets` must be fast and DB-only (no Brickset call, that's the
whole point) and idempotent — calling it twice for the same model must not
double-queue a job that's still active. `run_job` is the Celery task's actual
work, factored out so it's testable without a broker: it must move a job
QUEUED → RUNNING → SUCCEEDED/FAILED, record `last_error` on failure, and stop
early (cooperative cancel) if the job is flipped to CANCELLED mid-fetch.
`cancel_job`/`retry_job` must only accept the statuses that make sense.
"""

from __future__ import annotations

from typing import Any

import pytest
from app.core.errors import ValidationError
from app.models import Entity, User
from app.models.core import ProcessingJob
from app.models.lego import LegoSetModel
from app.schemas.lego import LegoSetModelCreate
from app.services import documents, lego_brickset_jobs, lego_provider, lego_service
from sqlalchemy import select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

# A real (tiny, 1x1) PNG signature — `documents.store_bytes` sniffs the magic
# bytes, so a fake image body needs to actually start with one.
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
    b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01"
    b"\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
)

IMAGES = ["https://brickset.test/alt1.jpg", "https://brickset.test/alt2.jpg"]


class _StubProvider:
    name = "brickset"
    enabled = True

    def lookup(self, set_number: str) -> Any:  # pragma: no cover - unused here
        raise NotImplementedError

    def additional_images(self, set_number: str) -> list[lego_provider.RemoteImage]:
        return [lego_provider.RemoteImage(url=url) for url in IMAGES]

    def instructions(self, set_number: str) -> list[lego_provider.RemoteInstruction]:
        return []


class _DisabledProvider:
    name = "brickset"
    enabled = False

    def lookup(self, set_number: str) -> Any:  # pragma: no cover - unused here
        raise NotImplementedError

    def additional_images(self, set_number: str) -> list[lego_provider.RemoteImage]:
        return []

    def instructions(self, set_number: str) -> list[lego_provider.RemoteInstruction]:
        return []


@pytest.fixture
def brickset(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_download(
        db: Session,
        url: str,
        *,
        max_bytes: int | None = None,
        original_filename: str | None = None,
    ) -> Any:
        # Distinct bytes per URL, or the content-addressed store would fold both
        # images into one document.
        return documents.store_bytes(db, PNG + url.encode(), source="URL", url=url)

    monkeypatch.setattr(lego_provider, "get_provider", lambda db: _StubProvider())
    monkeypatch.setattr(documents, "store_from_url", fake_download)


@pytest.fixture
def no_dispatch(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every test here calls `run_job` directly — dispatching to Celery would
    otherwise push a real message onto the same Redis the dev worker listens
    on. Records job ids `_dispatch` would have sent, for assertions."""
    dispatched: list[str] = []
    monkeypatch.setattr(lego_brickset_jobs, "_dispatch", lambda job: dispatched.append(str(job.id)))
    return dispatched


@pytest.fixture
def model(db: Session, entity: Entity, owner: User) -> LegoSetModel:
    return lego_service.create_model(
        db,
        LegoSetModelCreate(set_number="10280", name="Ramo de flores", theme="Icons"),
        entity_id=entity.id,
        actor_user_id=owner.id,
    )


def test_queue_creates_one_queued_job_per_asset_type(
    db: Session, owner: User, model: LegoSetModel, no_dispatch: list[str]
) -> None:
    jobs = lego_brickset_jobs.queue_brickset_assets(db, model, actor_user_id=owner.id)

    assert {job.job_type for job in jobs} == {
        lego_brickset_jobs.JOB_TYPE_IMAGES,
        lego_brickset_jobs.JOB_TYPE_MANUALS,
    }
    assert all(job.status == "QUEUED" for job in jobs)
    assert len(no_dispatch) == 2


def test_queue_reuses_an_already_active_job_instead_of_doubling_it(
    db: Session, owner: User, model: LegoSetModel, no_dispatch: list[str]
) -> None:
    first = lego_brickset_jobs.queue_brickset_assets(db, model, actor_user_id=owner.id)
    again = lego_brickset_jobs.queue_brickset_assets(db, model, actor_user_id=owner.id)

    assert {job.id for job in first} == {job.id for job in again}
    assert len(no_dispatch) == 2  # the second call dispatched nothing new
    remaining = db.scalars(
        select(ProcessingJob).where(ProcessingJob.job_type.in_(lego_brickset_jobs.JOB_TYPES))
    ).all()
    assert len(remaining) == 2


def test_a_moc_queues_nothing(db: Session, entity: Entity, owner: User) -> None:
    moc = lego_service.create_model(
        db,
        LegoSetModelCreate(is_custom=True, name="Construção própria"),
        entity_id=entity.id,
        actor_user_id=owner.id,
    )

    assert lego_brickset_jobs.queue_brickset_assets(db, moc, actor_user_id=owner.id) == []


def test_run_job_succeeds_and_actually_imports_the_images(
    db: Session, owner: User, model: LegoSetModel, brickset: None, no_dispatch: list[str]
) -> None:
    job = lego_brickset_jobs.queue_brickset_assets(db, model, actor_user_id=owner.id)[0]
    assert job.job_type == lego_brickset_jobs.JOB_TYPE_IMAGES

    lego_brickset_jobs.run_job(db, job)

    assert job.status == "SUCCEEDED"
    assert job.started_at is not None
    assert job.completed_at is not None
    assert len(model.images) == 2


def test_run_job_records_the_error_on_failure(
    db: Session,
    owner: User,
    model: LegoSetModel,
    no_dispatch: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(lego_provider, "get_provider", lambda db: _DisabledProvider())
    job = lego_brickset_jobs.queue_brickset_assets(db, model, actor_user_id=owner.id)[0]

    lego_brickset_jobs.run_job(db, job)

    assert job.status == "FAILED"
    assert job.last_error
    assert job.completed_at is not None


def test_cancelling_mid_fetch_stops_before_the_next_image(
    db: Session,
    owner: User,
    model: LegoSetModel,
    no_dispatch: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The job is flipped to CANCELLED (as the cancel endpoint would, from a
    different request) right after the first image is stored — the loop must
    notice before starting the second one."""
    calls = 0

    def fake_download(
        db: Session,
        url: str,
        *,
        max_bytes: int | None = None,
        original_filename: str | None = None,
    ) -> Any:
        nonlocal calls
        calls += 1
        if calls == 1:
            job.status = "CANCELLED"
            db.commit()
        return documents.store_bytes(db, PNG + url.encode(), source="URL", url=url)

    monkeypatch.setattr(lego_provider, "get_provider", lambda db: _StubProvider())
    monkeypatch.setattr(documents, "store_from_url", fake_download)

    job = lego_brickset_jobs.queue_brickset_assets(db, model, actor_user_id=owner.id)[0]
    lego_brickset_jobs.run_job(db, job)

    assert calls == 1
    assert job.status == "CANCELLED"
    assert len(model.images) == 1


def test_cancel_only_accepts_an_active_job(
    db: Session, owner: User, model: LegoSetModel, no_dispatch: list[str]
) -> None:
    job = lego_brickset_jobs.queue_brickset_assets(db, model, actor_user_id=owner.id)[0]
    lego_brickset_jobs.cancel_job(db, job)
    assert job.status == "CANCELLED"

    with pytest.raises(ValidationError):
        lego_brickset_jobs.cancel_job(db, job)


def test_retry_only_accepts_a_finished_job_and_redispatches(
    db: Session, owner: User, model: LegoSetModel, no_dispatch: list[str]
) -> None:
    job = lego_brickset_jobs.queue_brickset_assets(db, model, actor_user_id=owner.id)[0]

    with pytest.raises(ValidationError):
        lego_brickset_jobs.retry_job(db, job)  # still QUEUED, nothing to retry

    lego_brickset_jobs.cancel_job(db, job)
    lego_brickset_jobs.retry_job(db, job)

    assert job.status == "QUEUED"
    assert job.attempts == 1
    assert job.last_error is None
    assert len(no_dispatch) == 3  # 2 from queueing both jobs, +1 from this retry
