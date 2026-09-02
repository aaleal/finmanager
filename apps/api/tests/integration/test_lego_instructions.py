"""Protects: ADR-0040 «a manual is downloaded, not linked».

Two guarantees are worth a test. The import has to be idempotent — pressing
«Importar do Brickset» twice must not double the gallery — and the archive has to
carry the PDFs, because a restore that gives back every photograph and none of
the manuals has restored half a collection.
"""

from __future__ import annotations

import io
import json
import zipfile
from typing import Any

import pytest
from app.core.errors import Conflict, ValidationError
from app.models import Entity, User
from app.models.lego import LegoSetInstance, LegoSetInstruction, LegoSetModel, StorageLocation
from app.schemas.lego import LegoSetModelCreate
from app.services import documents, lego_backup, lego_provider, lego_service
from sqlalchemy import select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
    b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01"
    b"\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
)
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"

IMAGES = ["https://brickset.test/alt1.jpg", "https://brickset.test/alt2.jpg"]
MANUALS = [
    ("https://lego.test/6353618.pdf", "BI 3106, 80+4, 10280 V29", None),
    ("https://lego.test/10280_EN_Info_Booklet.pdf", "10280_EN_Info_Booklet", "EN"),
]


class _StubProvider:
    name = "brickset"
    enabled = True

    def lookup(self, set_number: str) -> Any:  # pragma: no cover - unused here
        raise NotImplementedError

    def additional_images(self, set_number: str) -> list[lego_provider.RemoteImage]:
        return [lego_provider.RemoteImage(url=url) for url in IMAGES]

    def instructions(self, set_number: str) -> list[lego_provider.RemoteInstruction]:
        return [
            lego_provider.RemoteInstruction(url=url, description=description, language=language)
            for url, description, language in MANUALS
        ]


@pytest.fixture
def brickset(monkeypatch: pytest.MonkeyPatch) -> None:
    """No network: a stub provider, and downloads that answer from memory."""

    def fake_download(
        db: Session,
        url: str,
        *,
        max_bytes: int | None = None,
        original_filename: str | None = None,
    ) -> Any:
        # Distinct bytes per URL, or the content-addressed store would fold every
        # manual into one document and hide the very duplication being tested.
        body = (PDF if url.endswith(".pdf") else PNG) + url.encode()
        return documents.store_bytes(
            db, body, source="URL", url=url, original_filename=original_filename
        )

    monkeypatch.setattr(lego_provider, "get_provider", lambda db: _StubProvider())
    monkeypatch.setattr(documents, "store_from_url", fake_download)


@pytest.fixture
def model(db: Session, entity: Entity, owner: User) -> LegoSetModel:
    return lego_service.create_model(
        db,
        LegoSetModelCreate(set_number="10280", name="Ramo de flores", theme="Icons"),
        entity_id=entity.id,
        actor_user_id=owner.id,
    )


def test_one_press_brings_the_photographs_and_the_manuals(
    db: Session, owner: User, model: LegoSetModel, brickset: None
) -> None:
    images, manuals, message = lego_service.import_from_brickset(db, model, actor_user_id=owner.id)

    assert (images, manuals, message) == (2, 2, None)
    assert [manual.language for manual in model.instructions] == [None, "EN"]
    assert len(model.images) == 2
    # Stored locally: a manual has bytes on this disk, not a lego.com address.
    stored = db.get(LegoSetInstruction, model.instructions[0].id)
    assert stored is not None
    assert documents.get(db, stored.document_id) is not None


def test_a_manual_can_be_added_by_hand(
    db: Session, owner: User, model: LegoSetModel, brickset: None
) -> None:
    manual = lego_service.add_model_instruction(
        db,
        model,
        url="https://household.test/scan.pdf",
        description="Caderno de notas da avó",
        language=None,
        actor_user_id=owner.id,
    )

    assert manual.description == "Caderno de notas da avó"
    assert [m.description for m in model.instructions] == ["Caderno de notas da avó"]


def test_a_hand_added_manual_refuses_a_repeated_description(
    db: Session, owner: User, model: LegoSetModel, brickset: None
) -> None:
    lego_service.add_model_instruction(
        db,
        model,
        url="https://household.test/scan.pdf",
        description="Caderno de notas da avó",
        language=None,
        actor_user_id=owner.id,
    )

    with pytest.raises(Conflict):
        lego_service.add_model_instruction(
            db,
            model,
            url="https://household.test/scan-2.pdf",
            description="Caderno de notas da avó",
            language=None,
            actor_user_id=owner.id,
        )


def test_pressing_twice_adds_nothing(
    db: Session, owner: User, model: LegoSetModel, brickset: None
) -> None:
    lego_service.import_from_brickset(db, model, actor_user_id=owner.id)

    images, manuals, message = lego_service.import_from_brickset(db, model, actor_user_id=owner.id)

    assert (images, manuals) == (0, 0)
    assert message is not None
    assert len(model.instructions) == 2


def test_a_moc_has_nothing_to_import(
    db: Session, entity: Entity, owner: User, brickset: None
) -> None:
    moc = lego_service.create_model(
        db,
        LegoSetModelCreate(is_custom=True, name="Construção própria"),
        entity_id=entity.id,
        actor_user_id=owner.id,
    )

    with pytest.raises(ValidationError, match="MOC"):
        lego_service.import_from_brickset(db, moc, actor_user_id=owner.id)


def test_the_manuals_survive_a_backup_round_trip(
    db: Session, entity: Entity, owner: User, model: LegoSetModel, brickset: None
) -> None:
    lego_service.import_from_brickset(db, model, actor_user_id=owner.id)
    payload = lego_backup.build_archive(db, entity_ids=[entity.id])

    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        manifest = json.loads(archive.read(lego_backup.MANIFEST_NAME))
        body = json.loads(archive.read(lego_backup.COLLECTION_NAME))
    assert manifest["counts"]["instructions"] == 2
    assert manifest["counts"]["documents"] == 4
    assert body["instructions"][1]["language"] == "EN"

    target = Entity(household_id=entity.household_id, name="Instalação nova")
    db.add(target)
    db.flush()
    for row in db.scalars(select(LegoSetInstance)):
        db.delete(row)
    for row in db.scalars(select(LegoSetModel)):
        db.delete(row)
    for row in db.scalars(select(StorageLocation)):
        db.delete(row)
    db.flush()

    report = lego_backup.restore_archive(db, payload, entity_id=target.id, actor_user_id=owner.id)

    assert (report.models, report.images, report.instructions) == (1, 2, 2)
    restored = db.scalars(select(LegoSetModel)).one()
    assert [manual.description for manual in restored.instructions] == [
        "BI 3106, 80+4, 10280 V29",
        "10280_EN_Info_Booklet",
    ]
