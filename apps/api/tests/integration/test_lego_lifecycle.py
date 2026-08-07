"""Protects: M9 Definition of Done — «ownership-transition guards», «non-in-collection
copies excluded from every KPI», «returning to IN_COLLECTION clears sale fields»,
delete guards, and the rubric bullet «audit log records every mutation».
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from app.core.errors import Conflict
from app.models import AuditLog, Entity, LegoSetInstance, User
from app.models.lego import LegoSetModel, StorageLocation
from app.schemas.lego import (
    LegoSetInstanceCreate,
    LegoSetInstanceUpdate,
    LegoSetModelCreate,
    StorageLocationCreate,
)
from app.services import lego_service
from sqlalchemy import func, select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


def _make_copy(
    db: Session,
    entity: Entity,
    owner: User,
    *,
    set_number: str = "10307",
    name: str = "Torre Eiffel",
    cost: str = "599.99",
    value: str | None = "689.00",
) -> LegoSetInstance:
    payload = LegoSetInstanceCreate(
        acquisition_cost_eur=Decimal(cost),
        new_set=LegoSetModelCreate(
            set_number=set_number,
            name=name,
            current_value_eur=Decimal(value) if value else None,
        ),
    )
    return lego_service.create_instance(db, payload, entity_id=entity.id, actor_user_id=owner.id)


def test_sold_copy_leaves_every_kpi_but_stays_browsable(
    db: Session, entity: Entity, owner: User
) -> None:
    copy = _make_copy(db, entity, owner)
    before = lego_service.overview(db, entity_ids=[entity.id], active_entity_id=entity.id)
    assert before.copies_owned == 1
    assert before.total_value_eur == Decimal("689.00")

    lego_service.update_instance(
        db,
        copy,
        LegoSetInstanceUpdate(
            ownership_status="SOLD",
            sale_price_eur=Decimal("750.00"),
            sale_date=dt.date(2025, 1, 5),
        ),
        actor_user_id=owner.id,
    )

    after = lego_service.overview(db, entity_ids=[entity.id], active_entity_id=entity.id)
    assert after.copies_owned == 0
    assert after.total_cost_eur == Decimal("0.00")
    assert after.total_value_eur == Decimal("0.00")
    assert after.roi_pct is None
    # Reported separately, never mixed into ROI.
    assert after.departed_copies == 1
    assert after.departed_sale_total_eur == Decimal("750.00")

    # Still visible in history.
    items, total = lego_service.list_instances(
        db, entity_ids=[entity.id], active_entity_id=entity.id, ownership_status="SOLD"
    )
    assert total == 1 and items[0].sale_price_eur == Decimal("750.00")


def test_returning_to_collection_clears_the_sale_record(
    db: Session, entity: Entity, owner: User
) -> None:
    copy = _make_copy(db, entity, owner)
    lego_service.update_instance(
        db,
        copy,
        LegoSetInstanceUpdate(
            ownership_status="GIFTED", sale_price_eur=Decimal("0.00"), sale_date=dt.date(2025, 2, 2)
        ),
        actor_user_id=owner.id,
    )
    lego_service.update_instance(
        db, copy, LegoSetInstanceUpdate(ownership_status="IN_COLLECTION"), actor_user_id=owner.id
    )

    assert copy.ownership_status == "IN_COLLECTION"
    assert copy.sale_price_eur is None
    assert copy.sale_date is None


def test_every_transition_is_allowed_and_audited_as_a_status_change(
    db: Session, entity: Entity, owner: User
) -> None:
    copy = _make_copy(db, entity, owner)
    for status in ("SOLD", "GIFTED", "IN_COLLECTION", "SOLD"):
        lego_service.update_instance(
            db, copy, LegoSetInstanceUpdate(ownership_status=status), actor_user_id=owner.id
        )

    status_changes = db.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.record_id == copy.id, AuditLog.action == "STATUS_CHANGE")
    )
    assert status_changes == 4


def test_create_and_delete_write_audit_rows(db: Session, entity: Entity, owner: User) -> None:
    copy = _make_copy(db, entity, owner)
    lego_service.delete_instance(db, copy, hard=False, actor_user_id=owner.id)

    actions = set(db.scalars(select(AuditLog.action).where(AuditLog.record_id == copy.id)).all())
    assert actions == {"CREATE", "DELETE"}
    assert copy.is_deleted is True


def test_model_delete_is_blocked_while_a_live_copy_references_it(
    db: Session, entity: Entity, owner: User
) -> None:
    copy = _make_copy(db, entity, owner)
    model = db.get(LegoSetModel, copy.lego_set_model_id)
    assert model is not None

    with pytest.raises(Conflict):
        lego_service.delete_model(db, model, hard=False, actor_user_id=owner.id)

    lego_service.delete_instance(db, copy, hard=False, actor_user_id=owner.id)
    lego_service.delete_model(db, model, hard=False, actor_user_id=owner.id)
    assert model.is_deleted is True


def test_second_copy_reuses_the_same_model(db: Session, entity: Entity, owner: User) -> None:
    first = _make_copy(db, entity, owner)
    second = lego_service.create_instance(
        db,
        LegoSetInstanceCreate(
            acquisition_cost_eur=Decimal("529.00"),
            new_set=LegoSetModelCreate(set_number="10307", name="Torre Eiffel"),
        ),
        entity_id=entity.id,
        actor_user_id=owner.id,
    )
    assert second.lego_set_model_id == first.lego_set_model_id

    models, total = lego_service.list_models(db, entity_ids=[entity.id], active_entity_id=entity.id)
    assert total == 1 and models[0].owned_copies_count == 2


def test_storage_delete_is_blocked_while_copies_are_assigned(
    db: Session, entity: Entity, owner: User
) -> None:
    location = lego_service.create_storage_location(
        db,
        StorageLocationCreate(area="Garagem", container="Caixa TV", capacity_pct=75),
        entity_id=entity.id,
        actor_user_id=owner.id,
    )
    copy = _make_copy(db, entity, owner)
    lego_service.update_instance(
        db,
        copy,
        LegoSetInstanceUpdate(storage_location_id=location.id),
        actor_user_id=owner.id,
    )

    with pytest.raises(Conflict):
        lego_service.delete_storage_location(db, location, actor_user_id=owner.id)

    lego_service.update_instance(
        db, copy, LegoSetInstanceUpdate(clear_storage_location=True), actor_user_id=owner.id
    )
    lego_service.delete_storage_location(db, location, actor_user_id=owner.id)
    assert db.get(StorageLocation, location.id).is_deleted is True  # type: ignore[union-attr]


def test_setting_a_value_stamps_its_freshness_date(
    db: Session, entity: Entity, owner: User
) -> None:
    from app.schemas.lego import LegoSetModelUpdate

    copy = _make_copy(db, entity, owner, value=None)
    model = db.get(LegoSetModel, copy.lego_set_model_id)
    assert model is not None and model.value_updated_at is None

    lego_service.update_model(
        db, model, LegoSetModelUpdate(current_value_eur=Decimal("689.00")), actor_user_id=owner.id
    )
    assert model.value_updated_at == dt.date.today()

    # Clearing the value clears the stamp too — no phantom freshness.
    lego_service.update_model(
        db, model, LegoSetModelUpdate(current_value_eur=None), actor_user_id=owner.id
    )
    assert model.value_updated_at is None
