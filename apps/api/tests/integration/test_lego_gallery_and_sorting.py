"""Protects: M9.3 — sorting every column, the copies filter and the set gallery.

The sort contract is the fragile part: two of the columns are not columns at all
(`copies` is a subquery, `roi` is arithmetic) and two more are ordinal scales that
sort wrongly if anyone lets Postgres compare them alphabetically.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from app.core.errors import Conflict, ValidationError
from app.models import Entity, LegoSetInstance, User
from app.schemas.lego import (
    LegoSetInstanceCreate,
    LegoSetModelCreate,
    StorageLocationCreate,
)
from app.services import lego_service
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
    b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01"
    b"\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
)


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
    condition: str | None = None,
    storage_location_id: object = None,
) -> LegoSetInstance:
    payload = LegoSetInstanceCreate(
        acquisition_cost_eur=Decimal(cost),
        condition=condition,  # type: ignore[arg-type]
        storage_location_id=storage_location_id,  # type: ignore[arg-type]
        new_set=LegoSetModelCreate(
            set_number=set_number,
            name=name,
            current_value_eur=Decimal(value) if value else None,
            rrp_eur=Decimal(rrp) if rrp else None,
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


def test_every_grid_column_is_sortable(db: Session, entity: Entity, owner: User) -> None:
    location = lego_service.create_storage_location(
        db,
        StorageLocationCreate(area="Garagem", container="Caixa A"),
        actor_user_id=owner.id,
    )
    _copy(db, entity, owner, set_number="2000", name="Beta", storage_location_id=location.id)
    _copy(db, entity, owner, set_number="1000", name="Alfa")

    for field in lego_service.SORT_FIELDS:
        for direction in ("asc", "desc"):
            assert len(_list(db, entity, sort=field, direction=direction)) == 2, field


def test_condition_sorts_by_quality_not_alphabetically(
    db: Session, entity: Entity, owner: User
) -> None:
    """NEW then GOOD then WORN then DAMAGED. Alphabetically it would start at DAMAGED."""
    _copy(db, entity, owner, set_number="1000", name="Alfa", condition="WORN")
    _copy(db, entity, owner, set_number="2000", name="Beta", condition="NEW")
    _copy(db, entity, owner, set_number="3000", name="Gama", condition="DAMAGED")

    ordered = _list(db, entity, sort="condition", direction="asc")
    assert [i.condition for i in ordered] == ["NEW", "WORN", "DAMAGED"]


def test_roi_sort_puts_gifts_last_in_both_directions(
    db: Session, entity: Entity, owner: User
) -> None:
    """A gift has no ROI at all; absent data is never "the smallest"."""
    _copy(db, entity, owner, set_number="1000", name="Alfa", cost="100.00", value="150.00")
    _copy(db, entity, owner, set_number="2000", name="Beta", cost="100.00", value="50.00")
    _copy(db, entity, owner, set_number="3000", name="Prenda", cost="0.00", value="90.00")

    for direction in ("asc", "desc"):
        ordered = _list(db, entity, sort="roi", direction=direction)
        assert ordered[-1].set_model is not None
        assert ordered[-1].set_model.name == "Prenda", direction
        assert ordered[-1].roi_pct is None


def test_roi_sort_falls_back_to_rrp_reading_for_gifts(
    db: Session, entity: Entity, owner: User
) -> None:
    """A gift's cell shows the PVP-tagged RRP reading (ADR-0010), so the sort must
    place it by that value too — only a gift with no RRP figure has nothing to
    rank by and stays last."""
    _copy(db, entity, owner, set_number="1000", name="Alfa", cost="100.00", value="150.00")
    _copy(db, entity, owner, set_number="2000", name="Beta", cost="100.00", value="50.00")
    # PVP-only reading: no cost basis, but a strongly positive RRP ROI.
    _copy(
        db,
        entity,
        owner,
        set_number="3000",
        name="PrendaBoa",
        cost="0.00",
        value="400.00",
        rrp="100.00",
    )
    # Truly absent: no cost basis and no RRP to fall back to.
    _copy(db, entity, owner, set_number="4000", name="PrendaSemPvp", cost="0.00", value="90.00")

    desc = _list(db, entity, sort="roi", direction="desc")
    assert [i.set_model.name for i in desc] == ["PrendaBoa", "Alfa", "Beta", "PrendaSemPvp"]

    asc = _list(db, entity, sort="roi", direction="asc")
    assert [i.set_model.name for i in asc] == ["Beta", "Alfa", "PrendaBoa", "PrendaSemPvp"]


def test_roi_basis_rrp_ranks_every_row_by_the_pvp_reading(
    db: Session, entity: Entity, owner: User
) -> None:
    """`roi_basis=rrp` is the alternate view (ADR-0010): it ranks by RRP ROI even
    for paid copies, reversing the cost-ROI order when the two readings disagree."""
    # Great cost ROI (+50%), poor PVP ROI (-50%).
    _copy(
        db,
        entity,
        owner,
        set_number="1000",
        name="Alfa",
        cost="100.00",
        value="150.00",
        rrp="300.00",
    )
    # Poor cost ROI (-50%), great PVP ROI (+50%).
    _copy(
        db,
        entity,
        owner,
        set_number="2000",
        name="Beta",
        cost="300.00",
        value="150.00",
        rrp="100.00",
    )

    by_cost = _list(db, entity, sort="roi", direction="desc", roi_basis="cost")
    assert [i.set_model.name for i in by_cost] == ["Alfa", "Beta"]

    by_rrp = _list(db, entity, sort="roi", direction="desc", roi_basis="rrp")
    assert [i.set_model.name for i in by_rrp] == ["Beta", "Alfa"]


def test_copies_filter_separates_repeats_from_singles(
    db: Session, entity: Entity, owner: User
) -> None:
    first = _copy(db, entity, owner, set_number="1000", name="Repetido")
    lego_service.create_instance(
        db,
        LegoSetInstanceCreate(
            acquisition_cost_eur=Decimal("10.00"),
            lego_set_model_id=first.lego_set_model_id,
        ),
        entity_id=entity.id,
        actor_user_id=owner.id,
    )
    _copy(db, entity, owner, set_number="2000", name="Único")

    assert len(_list(db, entity)) == 3
    assert {i.set_model.name for i in _list(db, entity, copies="multiple")} == {"Repetido"}
    assert {i.set_model.name for i in _list(db, entity, copies="single")} == {"Único"}


def test_gallery_adds_promotes_and_removes(db: Session, entity: Entity, owner: User) -> None:
    copy = _copy(db, entity, owner, set_number="1000", name="Alfa")
    model = copy.model
    lego_service.set_model_image(db, model, data=PNG, filename="box.png", actor_user_id=owner.id)
    box = model.image_document_id

    image = lego_service.add_model_image(
        db,
        model,
        data=PNG[:-1] + b"\x83",
        filename="alt.png",
        caption="Traseira",
        actor_user_id=owner.id,
    )
    assert [i.id for i in lego_service.model_out(db, model).images] == [image.id]

    # Content-addressed documents make a re-upload of the same bytes a duplicate.
    with pytest.raises(Conflict):
        lego_service.add_model_image(
            db, model, data=PNG[:-1] + b"\x83", filename="alt.png", actor_user_id=owner.id
        )

    lego_service.promote_model_image(db, image, actor_user_id=owner.id)
    promoted = image.document_id
    assert model.image_document_id == promoted
    # Nothing moved: the promoted image keeps its row, and the old box shot —
    # not lost — is simply appended as a new one.
    assert [i.document_id for i in lego_service.model_out(db, model).images] == [
        promoted,
        box,
    ]

    # Deleting the (now-cover) gallery row loses nothing either: the model still
    # points at the same document, just no longer duplicated in the gallery.
    lego_service.delete_model_image(db, image, actor_user_id=owner.id)
    db.refresh(model)
    assert model.image_document_id == promoted
    assert [i.document_id for i in lego_service.model_out(db, model).images] == [box]


def test_promoting_a_second_image_does_not_duplicate_the_first(
    db: Session, entity: Entity, owner: User
) -> None:
    copy = _copy(db, entity, owner, set_number="1000", name="Alfa")
    model = copy.model
    lego_service.set_model_image(db, model, data=PNG, filename="box.png", actor_user_id=owner.id)
    box = model.image_document_id
    first = lego_service.add_model_image(
        db, model, data=PNG[:-1] + b"\x83", filename="alt.png", actor_user_id=owner.id
    )
    second = lego_service.add_model_image(
        db, model, data=PNG[:-1] + b"\x80", filename="alt2.png", actor_user_id=owner.id
    )

    lego_service.promote_model_image(db, first, actor_user_id=owner.id)
    lego_service.promote_model_image(db, second, actor_user_id=owner.id)

    assert model.image_document_id == second.document_id
    # Nothing is ever removed by a promotion, so all three documents are still
    # visible — but `first` (the cover in between) appears only once, not twice.
    docs = [i.document_id for i in lego_service.model_out(db, model).images]
    assert docs.count(first.document_id) == 1
    assert set(docs) == {box, first.document_id, second.document_id}


def test_a_copy_photograph_leads_the_carousel(db: Session, entity: Entity, owner: User) -> None:
    """The cover describes the catalog entry; a photo describes this exact box."""
    copy = _copy(db, entity, owner, set_number="1000", name="Alfa")
    lego_service.set_model_image(
        db, copy.model, data=PNG, filename="box.png", actor_user_id=owner.id
    )
    out = lego_service.instance_out(db, copy)
    assert out.photo_url is None
    assert out.set_model is not None and out.set_model.image_url is not None
    assert out.set_model.value_updated_at is None or isinstance(
        out.set_model.value_updated_at, dt.date
    )


def test_a_copy_can_pick_its_own_table_image(db: Session, entity: Entity, owner: User) -> None:
    copy = _copy(db, entity, owner, set_number="1000", name="Alfa")
    model = copy.model
    lego_service.set_model_image(db, model, data=PNG, filename="box.png", actor_user_id=owner.id)
    image = lego_service.add_model_image(
        db, model, data=PNG[:-1] + b"\x83", filename="alt.png", actor_user_id=owner.id
    )

    lego_service.set_instance_display_image(db, copy, image.document_id, actor_user_id=owner.id)
    assert lego_service.instance_out(db, copy).display_image_url is not None

    lego_service.set_instance_display_image(db, copy, None, actor_user_id=owner.id)
    assert lego_service.instance_out(db, copy).display_image_url is None


def test_a_copy_cannot_pick_an_unrelated_image(db: Session, entity: Entity, owner: User) -> None:
    copy = _copy(db, entity, owner, set_number="1000", name="Alfa")
    other = _copy(db, entity, owner, set_number="2000", name="Beta")
    lego_service.set_model_image(
        db, other.model, data=PNG, filename="box.png", actor_user_id=owner.id
    )

    with pytest.raises(ValidationError):
        lego_service.set_instance_display_image(
            db, copy, other.model.image_document_id, actor_user_id=owner.id
        )
