"""Protects: the generic backup registry routes a module archive correctly, and
the global export/import round-trips through the container it wraps every
module's own archive in (ADR-0037). The per-module restore *rules* (primary
keys travel, only `entity_id`/`document_id` remapped, existing rows skipped)
stay LEGO's own and are protected by `test_lego_backup.py`; this file only
protects the routing layer above it.
"""

from __future__ import annotations

import io
import json
import zipfile
from decimal import Decimal

import pytest
from app.core.errors import ValidationError
from app.models import Entity, User
from app.models.lego import LegoSetInstance, LegoSetModel
from app.schemas.lego import LegoSetModelCreate
from app.services import backup_service, lego_backup, lego_service
from sqlalchemy import select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


def test_entities_is_registered_and_restored_before_lego_in_a_global_archive() -> None:
    """A row LEGO's own archive names by entity must find that entity already
    created — the global restore walks the registry in this order."""
    assert list(backup_service.modules().keys()) == ["entities", "lego"]


@pytest.fixture
def one_set(db: Session, entity: Entity, owner: User) -> LegoSetModel:
    model = lego_service.create_model(
        db,
        LegoSetModelCreate(set_number="21318", name="Casa da Árvore", rrp_eur=Decimal("219.99")),
        entity_id=entity.id,
        actor_user_id=owner.id,
    )
    db.flush()
    return model


def test_a_single_module_export_matches_the_modules_own_archive(
    db: Session, entity: Entity, one_set: LegoSetModel
) -> None:
    """Same rows, same shape — only the manifest's own export timestamp differs."""
    module = backup_service.get_module("lego")
    via_registry = module.build_archive(db, [entity.id])
    direct = lego_backup.build_archive(db, entity_ids=[entity.id])

    with zipfile.ZipFile(io.BytesIO(via_registry)) as archive:
        registry_body = json.loads(archive.read(lego_backup.COLLECTION_NAME))
    with zipfile.ZipFile(io.BytesIO(direct)) as archive:
        direct_body = json.loads(archive.read(lego_backup.COLLECTION_NAME))

    assert registry_body == direct_body


def test_the_global_export_wraps_every_module_under_its_own_manifest(
    db: Session, entity: Entity, one_set: LegoSetModel
) -> None:
    payload = backup_service.build_global_archive(db, entity_ids=[entity.id])

    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = archive.namelist()
        assert "manifest.json" in names
        assert f"{backup_service.MODULES_DIR}/lego.zip" in names
        inner = archive.read(f"{backup_service.MODULES_DIR}/lego.zip")

    with zipfile.ZipFile(io.BytesIO(inner)) as nested:
        assert lego_backup.MANIFEST_NAME in nested.namelist()


def test_restore_any_detects_a_lone_module_archive_without_a_hint(
    db: Session, entity: Entity, one_set: LegoSetModel
) -> None:
    payload = lego_backup.build_archive(db, entity_ids=[entity.id])

    # Same test database as the fixture: the primary key already exists unless
    # the original row is cleared first (mirrors test_lego_backup.py's own
    # round-trip fixture — a real installation would simply start empty).
    for instance_row in db.scalars(select(LegoSetInstance)):
        db.delete(instance_row)
    for model_row in db.scalars(select(LegoSetModel)):
        db.delete(model_row)
    db.flush()

    report = backup_service.restore_any(db, payload, household_id=entity.household_id)

    assert len(report.modules) == 1
    assert report.modules[0].module == "lego"
    assert report.modules[0].counts["models"] == 1


def test_restore_any_unwraps_the_global_container_module_by_module(
    db: Session, entity: Entity, one_set: LegoSetModel
) -> None:
    payload = backup_service.build_global_archive(db, entity_ids=[entity.id])

    for instance_row in db.scalars(select(LegoSetInstance)):
        db.delete(instance_row)
    for model_row in db.scalars(select(LegoSetModel)):
        db.delete(model_row)
    db.flush()

    report = backup_service.restore_any(db, payload, household_id=entity.household_id)

    assert [entry.module for entry in report.modules] == ["entities", "lego"]
    lego_report = next(entry for entry in report.modules if entry.module == "lego")
    assert lego_report.counts["models"] == 1


def test_restore_any_refuses_an_archive_it_does_not_recognise(db: Session, entity: Entity) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("manifest.json", '{"format": "algo.desconhecido"}')

    with pytest.raises(ValidationError):
        backup_service.restore_any(db, buffer.getvalue(), household_id=entity.household_id)
