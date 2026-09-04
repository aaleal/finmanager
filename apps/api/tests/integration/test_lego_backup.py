"""Protects: *«a cópia de segurança repõe a coleção numa instalação vazia»*.

The workbook export is a report and is allowed to be lossy. This archive is not:
what goes out has to come back, on a machine whose entities, documents and rows
are all different, and re-importing the same file must not clone the collection.
"""

from __future__ import annotations

import io
import json
import zipfile
from decimal import Decimal

import pytest
from app.core.errors import ValidationError
from app.models import Entity, Household, User
from app.models.lego import LegoSetInstance, LegoSetModel, StorageLocation
from app.schemas.lego import LegoSetInstanceCreate, LegoSetModelCreate, StorageLocationCreate
from app.services import lego_backup, lego_service
from sqlalchemy import select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


@pytest.fixture
def collection(db: Session, entity: Entity, owner: User) -> LegoSetModel:
    location = lego_service.create_storage_location(
        db,
        StorageLocationCreate(area="Escritório", container="Prateleira 2"),
        actor_user_id=owner.id,
    )
    model = lego_service.create_model(
        db,
        LegoSetModelCreate(
            set_number="10307",
            name="Torre Eiffel",
            theme="Icons",
            rrp_eur=Decimal("629.99"),
            current_value_eur=Decimal("700.00"),
            piece_count=10001,
        ),
        entity_id=entity.id,
        actor_user_id=owner.id,
    )
    lego_service.create_instance(
        db,
        LegoSetInstanceCreate(
            lego_set_model_id=model.id,
            acquisition_cost_eur=Decimal("600.00"),
            acquisition_source="CONTINENTE",
            storage_location_id=location.id,
            build_state="DISASSEMBLED",
            condition="SEALED",
            has_box=True,
        ),
        entity_id=entity.id,
        actor_user_id=owner.id,
    )
    db.flush()
    return model


def test_the_archive_carries_every_table_and_a_manifest(
    db: Session, entity: Entity, collection: LegoSetModel
) -> None:
    payload = lego_backup.build_archive(db, entity_ids=[entity.id])

    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        manifest = json.loads(archive.read(lego_backup.MANIFEST_NAME))
        body = json.loads(archive.read(lego_backup.COLLECTION_NAME))

    assert manifest["format"] == lego_backup.FORMAT
    assert manifest["counts"]["models"] == 1
    assert manifest["counts"]["instances"] == 1
    assert manifest["counts"]["storage_locations"] == 1
    assert body["models"][0]["set_number"] == "10307"
    # Decimals cross as strings: JSON floats would round money.
    assert body["models"][0]["rrp_eur"] == "629.99"
    # The owning entity travels by name, not by an id meaningless elsewhere.
    assert body["models"][0]["entity"] == "Ana"
    assert body["instances"][0]["entity"] == "Ana"
    assert "entity" not in body["storage_locations"][0]


def test_a_collection_survives_a_round_trip_onto_another_entity(
    db: Session, entity: Entity, owner: User, collection: LegoSetModel
) -> None:
    """The point of the whole feature: an installation that starts empty, whose
    entities were already imported under the same names (the entities backup
    module), resolves every row back onto the matching entity by name."""
    payload = lego_backup.build_archive(db, entity_ids=[entity.id])

    # Simulates the target installation already having "Ana" — imported first,
    # by name, through the entities module — rather than the source's own row.
    original_name = entity.name
    entity.name = "Entidade original (arquivada)"
    target = Entity(household_id=entity.household_id, name=original_name)
    db.add(target)
    db.flush()
    for copy_row in db.scalars(select(LegoSetInstance)):
        db.delete(copy_row)
    for model_row in db.scalars(select(LegoSetModel)):
        db.delete(model_row)
    for location_row in db.scalars(select(StorageLocation)):
        db.delete(location_row)
    db.flush()

    report = lego_backup.restore_archive(
        db, payload, household_id=target.household_id, actor_user_id=owner.id
    )
    assert (report.models, report.instances, report.storage_locations) == (1, 1, 1)

    restored = db.scalars(select(LegoSetModel)).one()
    assert restored.entity_id == target.id
    assert restored.set_number == "10307"
    assert restored.rrp_eur == Decimal("629.99")

    copy = db.scalars(select(LegoSetInstance)).one()
    assert copy.entity_id == target.id
    assert copy.lego_set_model_id == restored.id
    assert copy.acquisition_cost_eur == Decimal("600.00")
    # Rebuilt on the target entity, and still pointing at its own storage row.
    assert copy.storage_location_id is not None


def test_archive_keeps_each_row_on_its_own_entity_not_the_caller(
    db: Session, household: Household, entity: Entity, owner: User, collection: LegoSetModel
) -> None:
    """Five sets are Ana's, five are Bruno's: restoring must not collapse them
    all onto whichever entity the caller happened to choose."""
    bruno = Entity(household_id=household.id, name="Bruno", member_ids=[owner.id])
    db.add(bruno)
    db.flush()
    bruno_model = lego_service.create_model(
        db,
        LegoSetModelCreate(set_number="75192", name="Millennium Falcon", rrp_eur="849.99"),
        entity_id=bruno.id,
        actor_user_id=owner.id,
    )
    lego_service.create_instance(
        db,
        LegoSetInstanceCreate(lego_set_model_id=bruno_model.id, acquisition_cost_eur="800.00"),
        entity_id=bruno.id,
        actor_user_id=owner.id,
    )
    db.flush()

    payload = lego_backup.build_archive(db, entity_ids=[entity.id, bruno.id])

    for copy_row in db.scalars(select(LegoSetInstance)):
        db.delete(copy_row)
    for model_row in db.scalars(select(LegoSetModel)):
        db.delete(model_row)
    db.flush()

    # Both entities' names already exist here (as if imported first): no
    # fallback entity is needed, since every row in this archive carries a name.
    lego_backup.restore_archive(db, payload, household_id=household.id, actor_user_id=owner.id)

    ana_model = db.scalar(select(LegoSetModel).where(LegoSetModel.set_number == "10307"))
    bruno_model = db.scalar(select(LegoSetModel).where(LegoSetModel.set_number == "75192"))
    assert ana_model is not None and ana_model.entity_id == entity.id
    assert bruno_model is not None and bruno_model.entity_id == bruno.id


def test_restoring_a_row_whose_entity_name_is_unknown_here_is_refused(
    db: Session, entity: Entity, owner: User, collection: LegoSetModel
) -> None:
    """Refused, not guessed (ADR-0007): import the entities archive first."""
    payload = lego_backup.build_archive(db, entity_ids=[entity.id])
    entity.name = "Já não se chama Ana"
    for copy_row in db.scalars(select(LegoSetInstance)):
        db.delete(copy_row)
    for model_row in db.scalars(select(LegoSetModel)):
        db.delete(model_row)
    db.flush()

    with pytest.raises(ValidationError):
        lego_backup.restore_archive(
            db, payload, household_id=entity.household_id, actor_user_id=owner.id
        )


def test_importing_the_same_archive_twice_clones_nothing(
    db: Session, entity: Entity, owner: User, collection: LegoSetModel
) -> None:
    """Primary keys travel, which is what makes the restore idempotent."""
    payload = lego_backup.build_archive(db, entity_ids=[entity.id])

    report = lego_backup.restore_archive(
        db, payload, household_id=entity.household_id, actor_user_id=owner.id
    )

    assert report.models == 0
    assert report.skipped_models == 1
    assert report.skipped_instances == 1
    assert len(db.scalars(select(LegoSetModel)).all()) == 1


def test_a_foreign_archive_is_refused(db: Session, entity: Entity, owner: User) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(lego_backup.MANIFEST_NAME, json.dumps({"format": "outra.coisa"}))

    with pytest.raises(ValidationError):
        lego_backup.restore_archive(
            db, buffer.getvalue(), household_id=entity.household_id, actor_user_id=owner.id
        )


def test_something_that_is_not_a_zip_is_refused(db: Session, entity: Entity, owner: User) -> None:
    with pytest.raises(ValidationError):
        lego_backup.restore_archive(
            db, b"nao sou um zip", household_id=entity.household_id, actor_user_id=owner.id
        )


def test_restoring_a_legacy_row_without_a_fallback_entity_is_refused(
    db: Session, entity: Entity, owner: User, collection: LegoSetModel
) -> None:
    """A v1/v2 archive (or one hand-edited to strip the entity name) needs a
    fallback entity from the caller — refused, not guessed, without one."""
    payload = lego_backup.build_archive(db, entity_ids=[entity.id])
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        collection_body = json.loads(archive.read(lego_backup.COLLECTION_NAME))
    for row in collection_body["models"] + collection_body["instances"]:
        row.pop("entity", None)

    buffer = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(payload)) as source,
        zipfile.ZipFile(buffer, "w") as rewritten,
    ):
        for info in source.infolist():
            if info.filename == lego_backup.COLLECTION_NAME:
                rewritten.writestr(info, json.dumps(collection_body))
            else:
                rewritten.writestr(info, source.read(info.filename))

    for copy_row in db.scalars(select(LegoSetInstance)):
        db.delete(copy_row)
    for model_row in db.scalars(select(LegoSetModel)):
        db.delete(model_row)
    db.flush()

    with pytest.raises(ValidationError):
        lego_backup.restore_archive(
            db, buffer.getvalue(), household_id=entity.household_id, actor_user_id=owner.id
        )
