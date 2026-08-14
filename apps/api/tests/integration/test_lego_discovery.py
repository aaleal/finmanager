"""Protects: M9.1 — the discovery and analytics refinements.

Three things here are genuinely load-bearing and easy to break silently: the
sort contract (a short field list plus a direction, with the old combined values
still honoured), the hierarchical storage filter (a filter, never a tree), and the
acquisition timeline (cumulative, and explicitly *not* a market-value history).
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from app.core.errors import ValidationError
from app.models import Entity, LegoSetInstance, User
from app.models.lego import LegoSetModel
from app.schemas.lego import (
    LegoSetInstanceCreate,
    LegoSetInstanceUpdate,
    LegoSetModelCreate,
    LegoSetModelUpdate,
    StorageLocationCreate,
)
from app.services import lego_service
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


def _copy(
    db: Session,
    entity: Entity,
    owner: User,
    *,
    set_number: str,
    name: str,
    cost: str = "100.00",
    value: str | None = "150.00",
    rrp: str | None = None,
    pieces: int | None = None,
    acquired: dt.date | None = None,
    retirement_date: dt.date | None = None,
    storage_location_id: object = None,
    missing_parts: str | None = None,
) -> LegoSetInstance:
    payload = LegoSetInstanceCreate(
        acquisition_cost_eur=Decimal(cost),
        acquisition_date=acquired,
        missing_parts=missing_parts,
        storage_location_id=storage_location_id,  # type: ignore[arg-type]
        new_set=LegoSetModelCreate(
            set_number=set_number,
            name=name,
            piece_count=pieces,
            retirement_date=retirement_date,
            rrp_eur=Decimal(rrp) if rrp else None,
            current_value_eur=Decimal(value) if value else None,
        ),
    )
    return lego_service.create_instance(db, payload, entity_id=entity.id, actor_user_id=owner.id)


def _list(db: Session, entity: Entity, **kwargs: object) -> list:
    items, _, _ = lego_service.list_instances(
        db,
        entity_ids=[entity.id],
        active_entity_id=entity.id,
        **kwargs,  # type: ignore[arg-type]
    )
    return items


def test_sort_field_and_direction_are_independent(db: Session, entity: Entity, owner: User) -> None:
    _copy(db, entity, owner, set_number="1000", name="Alfa", pieces=100)
    _copy(db, entity, owner, set_number="2000", name="Beta", pieces=900)

    ascending = _list(db, entity, sort="pieces", direction="asc")
    assert [i.set_model.piece_count for i in ascending] == [100, 900]

    descending = _list(db, entity, sort="pieces", direction="desc")
    assert [i.set_model.piece_count for i in descending] == [900, 100]


def test_legacy_combined_sort_values_still_work(db: Session, entity: Entity, owner: User) -> None:
    """Bookmarked `?sort=name_desc` URLs must not start ordering by insertion date."""
    _copy(db, entity, owner, set_number="1000", name="Alfa")
    _copy(db, entity, owner, set_number="2000", name="Beta")

    items = _list(db, entity, sort="name_desc", direction="asc")
    assert [i.set_model.name for i in items] == ["Beta", "Alfa"]


def test_storage_filter_by_area_spans_every_container(
    db: Session, entity: Entity, owner: User
) -> None:
    garage_a = lego_service.create_storage_location(
        db,
        StorageLocationCreate(area="Garagem", container="Caixa A"),
        entity_id=entity.id,
        actor_user_id=owner.id,
    )
    garage_b = lego_service.create_storage_location(
        db,
        StorageLocationCreate(area="Garagem", container="Caixa B"),
        entity_id=entity.id,
        actor_user_id=owner.id,
    )
    house = lego_service.create_storage_location(
        db,
        StorageLocationCreate(area="Casa", container="Armário"),
        entity_id=entity.id,
        actor_user_id=owner.id,
    )
    _copy(db, entity, owner, set_number="1000", name="Alfa", storage_location_id=garage_a.id)
    _copy(db, entity, owner, set_number="2000", name="Beta", storage_location_id=garage_b.id)
    _copy(db, entity, owner, set_number="3000", name="Gama", storage_location_id=house.id)

    assert len(_list(db, entity, storage_area="Garagem")) == 2
    assert len(_list(db, entity, storage_location_id=garage_a.id)) == 1
    assert len(_list(db, entity, storage_area="Casa")) == 1


def test_completeness_and_retirement_are_tri_state(
    db: Session, entity: Entity, owner: User
) -> None:
    _copy(
        db,
        entity,
        owner,
        set_number="1000",
        name="Alfa",
        retirement_date=dt.date(2015, 12, 31),
    )
    _copy(db, entity, owner, set_number="2000", name="Beta", missing_parts="2x 3001 vermelho")

    assert len(_list(db, entity)) == 2
    assert len(_list(db, entity, retirement="retired")) == 1
    assert len(_list(db, entity, retirement="available")) == 1
    assert len(_list(db, entity, completeness="complete")) == 1
    assert len(_list(db, entity, completeness="incomplete")) == 1


def test_a_future_retirement_date_is_still_on_sale(
    db: Session, entity: Entity, owner: User
) -> None:
    """M9.2: a set retiring on 31 December is buyable for the whole of that year."""
    end_of_year = dt.date(dt.date.today().year, 12, 31)
    copy = _copy(db, entity, owner, set_number="1000", name="Alfa", retirement_date=end_of_year)

    still_selling = end_of_year > dt.date.today()
    assert copy.model.is_retired is not still_selling
    assert len(_list(db, entity, retirement="available")) == (1 if still_selling else 0)
    assert len(_list(db, entity, retirement="retired")) == (0 if still_selling else 1)

    out = lego_service.model_out(db, copy.model)
    # The grid still reads a plain year, whatever the exact date is (M9.1 UX-9.10).
    assert out.retired_year == end_of_year.year


def test_every_catalog_field_is_editable_and_dates_must_stay_ordered(
    db: Session, entity: Entity, owner: User
) -> None:
    """M9.2 FR-9.23: the detail sheet edits the set, not just the copy."""
    copy = _copy(db, entity, owner, set_number="1000", name="Alfa", value=None)

    lego_service.update_model(
        db,
        copy.model,
        LegoSetModelUpdate(
            name="Alfa editado",
            theme="Icons",
            subtheme="Landmarks",
            release_date=dt.date(2020, 1, 1),
            retirement_date=dt.date(2099, 12, 31),
            piece_count=500,
            minifig_count=2,
            rrp_eur=Decimal("99.99"),
            current_value_eur=Decimal("120.00"),
            short_description="editado",
            notes="nota",
        ),
        actor_user_id=owner.id,
    )
    out = lego_service.model_out(db, copy.model)
    assert (out.name, out.subtheme, out.piece_count) == ("Alfa editado", "Landmarks", 500)
    assert out.release_year == 2020
    # Setting a value by hand re-stamps its freshness date, from here too (FR-9.6).
    assert out.value_updated_at == dt.date.today()

    # A partial update supplying only one date is still checked against the row.
    with pytest.raises(ValidationError):
        lego_service.update_model(
            db,
            copy.model,
            LegoSetModelUpdate(retirement_date=dt.date(2019, 1, 1)),
            actor_user_id=owner.id,
        )


def test_summary_covers_every_match_not_just_the_page(
    db: Session, entity: Entity, owner: User
) -> None:
    _copy(db, entity, owner, set_number="1000", name="Alfa", cost="10.00", value="30.00", pieces=5)
    _copy(db, entity, owner, set_number="2000", name="Beta", cost="20.00", value="40.00", pieces=7)

    _, total, summary = lego_service.list_instances(
        db, entity_ids=[entity.id], active_entity_id=entity.id, limit=1
    )
    assert total == 2
    assert summary.copies == 2
    assert summary.unique_sets == 2
    assert summary.total_cost_eur == Decimal("30.00")
    assert summary.total_value_eur == Decimal("70.00")
    assert summary.total_pieces == 12


def test_rrp_roi_is_derived_and_kept_apart_from_cost_roi(
    db: Session, entity: Entity, owner: User
) -> None:
    """A gift has no cost ROI, but its value against the original RRP is still readable."""
    copy = _copy(
        db, entity, owner, set_number="1000", name="Alfa", cost="0.00", value="150.00", rrp="100.00"
    )
    out = lego_service.instance_out(db, copy)

    assert out.roi_pct is None  # no cost basis — unchanged M9 rule
    assert out.set_model is not None
    assert out.set_model.rrp_appreciation_eur == Decimal("50.00")
    assert out.set_model.rrp_roi_pct == Decimal("50.00")


def test_timeline_is_cumulative_and_ignores_undated_copies(
    db: Session, entity: Entity, owner: User
) -> None:
    _copy(
        db,
        entity,
        owner,
        set_number="1000",
        name="Alfa",
        cost="10.00",
        value="30.00",
        acquired=dt.date(2024, 3, 12),
    )
    _copy(
        db,
        entity,
        owner,
        set_number="2000",
        name="Beta",
        cost="20.00",
        value="40.00",
        acquired=dt.date(2024, 5, 1),
    )
    _copy(db, entity, owner, set_number="3000", name="Gama", cost="99.00", value="99.00")

    result = lego_service.overview(db, entity_ids=[entity.id], active_entity_id=entity.id)

    assert [point.month for point in result.timeline] == ["2024-03", "2024-05"]
    assert [point.copies for point in result.timeline] == [1, 2]
    assert [point.cost_eur for point in result.timeline] == [Decimal("10.00"), Decimal("30.00")]
    assert [point.value_eur for point in result.timeline] == [Decimal("30.00"), Decimal("70.00")]
    assert result.copies_without_date == 1


def test_departed_copies_never_reach_the_timeline(db: Session, entity: Entity, owner: User) -> None:
    copy = _copy(
        db,
        entity,
        owner,
        set_number="1000",
        name="Alfa",
        acquired=dt.date(2024, 3, 12),
    )
    lego_service.update_instance(
        db, copy, LegoSetInstanceUpdate(ownership_status="SOLD"), actor_user_id=owner.id
    )

    result = lego_service.overview(db, entity_ids=[entity.id], active_entity_id=entity.id)
    assert result.timeline == []
    assert db.query(LegoSetModel).count() >= 1
