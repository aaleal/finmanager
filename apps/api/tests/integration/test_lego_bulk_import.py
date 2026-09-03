"""Protects: ADR-0048 «bulk import mirrors the export».

Three guarantees are worth a test. Preview must resolve entity/storage/enum
columns from the household's own data and flag exactly what it can't, without
ever touching Brickset. Commit must reuse an existing model by set number
(no Brickset call) but do a real find-or-create lookup for a genuinely new
one — and one row failing that lookup must not sink the rest of the batch.
Storage import must upsert on (area, container), not duplicate.
"""

from __future__ import annotations

import io
from decimal import Decimal
from typing import Any

import openpyxl
import pytest
from app.core.errors import ValidationError
from app.models import Entity, User
from app.models.lego import LegoSetInstance, LegoSetModel, StorageLocation
from app.schemas.lego import BulkImportRow, LegoSetModelCreate, LookupResult
from app.services import lego_bulk_import, lego_provider, lego_service
from sqlalchemy import select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


def _workbook(sheet_name: str, headers: list[str], rows: list[list[Any]]) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = sheet_name
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


class _StubProvider:
    """Answers one known set number, refuses every other (M9's manual-form parity)."""

    name = "brickset"
    enabled = True

    def lookup(self, set_number: str) -> LookupResult:
        if set_number == "10281":
            return LookupResult(found=True, set_number="10281", name="Bonsai", theme="Icons")
        return LookupResult(found=False, message=f"{set_number} não encontrado.")

    def additional_images(self, set_number: str) -> list[Any]:
        return []

    def instructions(self, set_number: str) -> list[Any]:
        return []


@pytest.fixture
def brickset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lego_provider, "get_provider", lambda db: _StubProvider())


@pytest.fixture
def existing_model(db: Session, entity: Entity, owner: User) -> LegoSetModel:
    return lego_service.create_model(
        db,
        LegoSetModelCreate(set_number="10280", name="Ramo de flores", theme="Icons"),
        entity_id=entity.id,
        actor_user_id=owner.id,
    )


@pytest.fixture
def storage(db: Session) -> StorageLocation:
    row = StorageLocation(area="Garagem", container="Caixa A")
    db.add(row)
    db.flush()
    return row


def test_preview_resolves_local_data_and_never_calls_brickset(
    db: Session,
    entity: Entity,
    storage: StorageLocation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*args: Any, **kwargs: Any) -> Any:  # pragma: no cover - must never run
        raise AssertionError("preview must not contact Brickset")

    monkeypatch.setattr(lego_provider, "get_provider", _boom)

    data = _workbook(
        "Cópias",
        ["Número", "Entidade", "Área", "Contentor", "Origem", "Custo (€)"],
        [
            ["10280", entity.name, "Garagem", "Caixa A", "Loja", "89.99"],
            ["10281", "Alguém que não existe", "Sótão", "", "Marciano", "abc"],
        ],
    )

    rows = lego_bulk_import.preview_instances(
        db, data=data, household_id=entity.household_id, active_entity_id=None
    )

    assert len(rows) == 2
    ok, bad = rows
    assert ok.errors == {}
    assert ok.entity_id == entity.id
    assert ok.storage_location_id == storage.id
    assert ok.acquisition_source == "RETAIL"

    assert bad.entity_id is None
    assert "entity_id" in bad.errors
    assert "storage_location_id" in bad.errors
    assert "acquisition_source" in bad.errors
    assert "acquisition_cost_eur" in bad.errors


def test_commit_reuses_existing_model_without_a_lookup(
    db: Session,
    entity: Entity,
    owner: User,
    existing_model: LegoSetModel,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*args: Any, **kwargs: Any) -> Any:  # pragma: no cover - must never run
        raise AssertionError("a known set number must not trigger a Brickset lookup")

    monkeypatch.setattr(lego_provider, "get_provider", _boom)

    row = BulkImportRow(
        row_number=2,
        set_number="10280",
        entity_id=entity.id,
        acquisition_cost_eur=Decimal("49.99"),
    )

    results = lego_bulk_import.commit_instances(
        db, [row], household_id=entity.household_id, actor_user_id=owner.id
    )

    assert results[0].ok is True
    instance = db.get(LegoSetInstance, results[0].lego_set_instance_id)
    assert instance is not None
    assert instance.lego_set_model_id == existing_model.id


def test_commit_looks_up_a_new_set_and_one_bad_row_does_not_sink_the_batch(
    db: Session, entity: Entity, owner: User, brickset: None
) -> None:
    rows = [
        BulkImportRow(row_number=2, set_number="10281", entity_id=entity.id),
        BulkImportRow(row_number=3, set_number="99999", entity_id=entity.id),
    ]

    results = lego_bulk_import.commit_instances(
        db, rows, household_id=entity.household_id, actor_user_id=owner.id
    )

    found, not_found = results
    assert found.ok is True
    model = db.scalar(select(LegoSetModel).where(LegoSetModel.set_number == "10281"))
    assert model is not None and model.name == "Bonsai"

    assert not_found.ok is False
    assert "99999" in not_found.message


def test_commit_rejects_a_row_still_carrying_errors(
    db: Session, entity: Entity, owner: User
) -> None:
    row = BulkImportRow(
        row_number=2, set_number="10280", entity_id=entity.id, errors={"entity_id": "por corrigir"}
    )

    results = lego_bulk_import.commit_instances(
        db, [row], household_id=entity.household_id, actor_user_id=owner.id
    )

    assert results[0].ok is False


def test_storage_import_upserts_on_area_and_container(
    db: Session, owner: User, storage: StorageLocation
) -> None:
    data = _workbook(
        "Arrumação",
        ["Área", "Contentor", "Descrição", "Ocupação (%)"],
        [
            ["Garagem", "Caixa A", "Sets grandes", "60"],
            ["Sótão", "", "", ""],
        ],
    )

    result = lego_bulk_import.import_storage_locations(db, data=data, actor_user_id=owner.id)

    assert result.created == 1
    assert result.updated == 1
    assert result.errors == []
    db.refresh(storage)
    assert storage.description == "Sets grandes"
    assert storage.capacity_pct == 60

    again = lego_bulk_import.import_storage_locations(db, data=data, actor_user_id=owner.id)
    assert again.created == 0
    assert again.updated == 2


def test_storage_import_reports_a_missing_area(db: Session, owner: User) -> None:
    data = _workbook("Arrumação", ["Área", "Contentor"], [["", "Caixa sem área"]])

    result = lego_bulk_import.import_storage_locations(db, data=data, actor_user_id=owner.id)

    assert result.created == 0
    assert result.updated == 0
    assert len(result.errors) == 1


def test_unreadable_file_is_a_validation_error(db: Session, entity: Entity) -> None:
    with pytest.raises(ValidationError):
        lego_bulk_import.preview_instances(
            db, data=b"nao sou um excel", household_id=entity.household_id, active_entity_id=None
        )
