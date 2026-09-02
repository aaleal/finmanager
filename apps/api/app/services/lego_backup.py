"""Round-trip backup of the LEGO collection.

The XLSX export is a **report**: shaped for a human, lossy by design. This is the
other thing — an archive that can rebuild the collection on an installation that
starts empty, which forces three decisions the report never had to make.

1. **Primary keys travel.** Every row keeps the UUID it had. Re-importing the
   same archive is therefore a no-op instead of a second copy of the collection,
   and no natural key has to be invented for an instance, which has none.
2. **Two references are rewritten, one by name.** ``document_id`` is remapped
   through the content-addressed store, which deduplicates by SHA-256 — the
   same photo imported twice is one file on disk either way. A model's or
   instance's ``entity_id`` is resolved by the owning entity's *name* against
   the target household, because a copied UUID means nothing on another
   installation but the name is exactly how a household already tells its
   entities apart — an archive with entities split across owners restores
   with that split intact, instead of collapsing onto whoever ran the import.
   A name with no match is refused, not guessed (ADR-0007): import that
   entity first (Definições → Cópia de segurança → módulo Entidades). An
   archive written before this existed (v1/v2) carries no name, so its rows
   fall back to the entity the caller chose, exactly as before.
3. **Storage locations carry no entity at all.** They are household-level
   reference data, not entity-scoped (ADR-0046) — the same trade already made
   for the product catalogue (ADR-0019).
4. **The valuation history comes along.** It lives in ``audit_logs`` and nowhere
   else (ADR-0008), so an archive that skipped it would silently discard every
   price this collection was ever worth.
"""

from __future__ import annotations

import datetime as dt
import io
import json
import uuid
import zipfile
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.core.errors import ValidationError
from app.models.core import AuditLog, Document
from app.models.household import Entity
from app.models.lego import (
    LegoSetImage,
    LegoSetInstance,
    LegoSetInstruction,
    LegoSetModel,
    StorageLocation,
)
from app.schemas.lego import LegoBackupReport
from app.services import documents

FORMAT = "finmanager.lego.backup"
#: v2 added ``instructions``; v3 added the owning entity's ``name`` on models and
#: instances (resolved on restore instead of forcing one entity onto everything).
#: An older archive simply has none of these.
VERSION = 3

MANIFEST_NAME = "manifest.json"
COLLECTION_NAME = "collection.json"
HISTORY_NAME = "value-history.json"
DOCUMENTS_DIR = "documents"

_MODEL_TABLE = "lego_set_models"
#: Guards against a zip bomb: the archive is trusted no more than any upload.
_MAX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024


# --- Serialisation ------------------------------------------------------------


def _plain(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dt.datetime | dt.date):
        return value.isoformat()
    return value


def _row(instance: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: _plain(getattr(instance, field)) for field in fields}


def _row_with_entity(
    instance: Any, fields: tuple[str, ...], entity_names: dict[uuid.UUID, str]
) -> dict[str, Any]:
    row = _row(instance, fields)
    row["entity"] = entity_names.get(instance.entity_id)
    return row


_MODEL_FIELDS = (
    "id",
    "set_number",
    "is_custom",
    "name",
    "theme",
    "subtheme",
    "release_date",
    "retirement_date",
    "piece_count",
    "minifig_count",
    "age_min",
    "age_max",
    "box_height_cm",
    "box_width_cm",
    "box_depth_cm",
    "box_weight_kg",
    "rrp_eur",
    "current_value_eur",
    "value_updated_at",
    "image_document_id",
    "short_description",
    "notes",
    "created_at",
    "updated_at",
)

_INSTANCE_FIELDS = (
    "id",
    "lego_set_model_id",
    "acquisition_date",
    "acquisition_cost_eur",
    "acquisition_source",
    "storage_location_id",
    "build_state",
    "condition",
    "has_box",
    "has_instructions",
    "missing_parts",
    "ownership_status",
    "sale_price_eur",
    "sale_date",
    "photo_document_id",
    "notes",
    "created_at",
    "updated_at",
)

_IMAGE_FIELDS = ("id", "lego_set_model_id", "document_id", "position", "caption")

_INSTRUCTION_FIELDS = (
    "id",
    "lego_set_model_id",
    "document_id",
    "description",
    "language",
    "position",
)

_STORAGE_FIELDS = ("id", "area", "container", "description", "capacity_pct")


# --- Export -------------------------------------------------------------------


def build_archive(db: DbSession, *, entity_ids: list[uuid.UUID]) -> bytes:
    """Everything needed to rebuild this collection elsewhere, as one zip.

    Soft-deleted rows are left out: a backup restores a collection, and a row
    someone deleted is not part of it. The audit log keeps that story.
    """
    models = list(
        db.scalars(
            select(LegoSetModel).where(
                LegoSetModel.entity_id.in_(entity_ids), LegoSetModel.is_deleted.is_(False)
            )
        )
    )
    model_ids = {model.id for model in models}
    instances = [
        instance
        for instance in db.scalars(
            select(LegoSetInstance).where(
                LegoSetInstance.entity_id.in_(entity_ids),
                LegoSetInstance.is_deleted.is_(False),
            )
        )
        if instance.lego_set_model_id in model_ids
    ]
    # Shared reference data (ADR-0046): every live location travels regardless
    # of which entity's collection is being exported.
    locations = list(
        db.scalars(select(StorageLocation).where(StorageLocation.is_deleted.is_(False)))
    )
    images = [image for model in models for image in model.images]
    instructions = [manual for model in models for manual in model.instructions]
    entity_names = {
        row[0]: row[1]
        for row in db.execute(select(Entity.id, Entity.name).where(Entity.id.in_(entity_ids))).all()
    }

    collection = {
        "storage_locations": [_row(row, _STORAGE_FIELDS) for row in locations],
        "models": [_row_with_entity(row, _MODEL_FIELDS, entity_names) for row in models],
        "images": [_row(row, _IMAGE_FIELDS) for row in images],
        "instructions": [_row(row, _INSTRUCTION_FIELDS) for row in instructions],
        "instances": [_row_with_entity(row, _INSTANCE_FIELDS, entity_names) for row in instances],
    }

    document_ids = {
        value
        for value in (
            [model.image_document_id for model in models]
            + [instance.photo_document_id for instance in instances]
            + [image.document_id for image in images]
            + [manual.document_id for manual in instructions]
        )
        if value is not None
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        written = _write_documents(db, archive, document_ids)
        archive.writestr(COLLECTION_NAME, json.dumps(collection, ensure_ascii=False, indent=1))
        archive.writestr(
            HISTORY_NAME,
            json.dumps(_value_history(db, model_ids), ensure_ascii=False, indent=1),
        )
        archive.writestr(
            MANIFEST_NAME,
            json.dumps(
                {
                    "format": FORMAT,
                    "version": VERSION,
                    "exported_at": dt.datetime.now(dt.UTC).isoformat(),
                    "counts": {
                        "storage_locations": len(locations),
                        "models": len(models),
                        "images": len(images),
                        "instructions": len(instructions),
                        "instances": len(instances),
                        "documents": len(written),
                    },
                },
                ensure_ascii=False,
                indent=1,
            ),
        )
    return buffer.getvalue()


def _write_documents(
    db: DbSession, archive: zipfile.ZipFile, ids: set[uuid.UUID]
) -> dict[str, dict[str, Any]]:
    """Image bytes, named by the hash that already addresses them on disk."""
    if not ids:
        return {}
    written: dict[str, dict[str, Any]] = {}
    for document in db.scalars(select(Document).where(Document.id.in_(ids))):
        try:
            data = documents.absolute_path(document).read_bytes()
        except (OSError, ValidationError):
            # A missing file must not cost the whole backup; the row is dropped
            # and the import simply finds no image for it.
            continue
        name = f"{DOCUMENTS_DIR}/{document.sha256_hash}"
        archive.writestr(name, data)
        written[str(document.id)] = {
            "sha256_hash": document.sha256_hash,
            "original_filename": document.original_filename,
            "url": document.url,
            "source": document.source,
        }
    archive.writestr(
        f"{DOCUMENTS_DIR}/index.json", json.dumps(written, ensure_ascii=False, indent=1)
    )
    return written


def _value_history(db: DbSession, model_ids: set[uuid.UUID]) -> list[dict[str, Any]]:
    """Every value a set was ever worth, read out of the audit log (ADR-0008)."""
    if not model_ids:
        return []
    rows = db.scalars(
        select(AuditLog)
        .where(AuditLog.table_name == _MODEL_TABLE, AuditLog.record_id.in_(model_ids))
        .order_by(AuditLog.created_at)
    )
    history: list[dict[str, Any]] = []
    for row in rows:
        before = (row.before or {}).get("current_value_eur")
        after = (row.after or {}).get("current_value_eur")
        if before == after:
            continue
        history.append(
            {
                "record_id": str(row.record_id),
                "observed_at": _plain(row.created_at),
                "before": before,
                "after": after,
            }
        )
    return history


def filename(exported_on: dt.date | None = None) -> str:
    return f"colecao-lego-backup-{exported_on or dt.date.today():%Y%m%d}.zip"


# --- Import -------------------------------------------------------------------


def _read_json(archive: zipfile.ZipFile, name: str) -> Any:
    try:
        return json.loads(archive.read(name))
    except KeyError as exc:
        raise ValidationError(f"O arquivo não contém {name}.") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{name} não é JSON válido.") from exc


def _as_uuid(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    try:
        return uuid.UUID(str(value))
    except ValueError as exc:
        raise ValidationError(f"Identificador inválido no arquivo: {value!r}.") from exc


def _as_decimal(value: Any) -> Decimal | None:
    return None if value in (None, "") else Decimal(str(value))


def _as_date(value: Any) -> dt.date | None:
    return None if value in (None, "") else dt.date.fromisoformat(str(value)[:10])


def restore_archive(
    db: DbSession,
    payload: bytes,
    *,
    entity_id: uuid.UUID,
    actor_user_id: uuid.UUID | None = None,
) -> LegoBackupReport:
    """Rebuild a collection from an archive.

    A model's or instance's row is attributed to the entity named on it,
    resolved against the caller's own household — not forced onto whichever
    entity the caller picked. A row from an archive written before entities
    travelled by name (v1/v2) falls back to that chosen entity, exactly as it
    always did.

    Rows that already exist are **skipped, not merged**: an archive is a snapshot
    of a moment, and silently overwriting today's edits with a month-old value is
    the one behaviour nobody would ask for.
    """
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile as exc:
        raise ValidationError("O ficheiro não é um arquivo zip válido.") from exc

    with archive:
        if sum(info.file_size for info in archive.infolist()) > _MAX_UNCOMPRESSED_BYTES:
            raise ValidationError("Arquivo demasiado grande.")

        manifest = _read_json(archive, MANIFEST_NAME)
        if manifest.get("format") != FORMAT:
            raise ValidationError("Este arquivo não é uma cópia de segurança LEGO.")
        if int(manifest.get("version", 0)) > VERSION:
            raise ValidationError("O arquivo foi criado por uma versão mais recente da aplicação.")

        target_entity = db.get(Entity, entity_id)
        if target_entity is None:
            raise ValidationError("Entidade de destino não encontrada.")

        collection = _read_json(archive, COLLECTION_NAME)
        report = LegoBackupReport()
        document_map = _restore_documents(db, archive, report)
        entity_cache: dict[str, uuid.UUID] = {}

        _restore_locations(db, collection, report)
        _restore_models(
            db,
            collection,
            target_entity.household_id,
            entity_id,
            entity_cache,
            document_map,
            report,
        )
        _restore_images(db, collection, document_map, report)
        _restore_instructions(db, collection, document_map, report)
        _restore_instances(
            db,
            collection,
            target_entity.household_id,
            entity_id,
            entity_cache,
            document_map,
            report,
        )
        db.flush()

    return report


def _restore_documents(
    db: DbSession, archive: zipfile.ZipFile, report: LegoBackupReport
) -> dict[uuid.UUID, uuid.UUID]:
    """Old document id → new one. The store deduplicates by hash, so re-importing
    the same photo costs nothing."""
    try:
        index = json.loads(archive.read(f"{DOCUMENTS_DIR}/index.json"))
    except KeyError:
        return {}

    mapping: dict[uuid.UUID, uuid.UUID] = {}
    for old_id, meta in index.items():
        old_uuid = _as_uuid(old_id)
        if old_uuid is None:
            continue
        try:
            data = archive.read(f"{DOCUMENTS_DIR}/{meta['sha256_hash']}")
        except KeyError:
            report.skipped_images += 1
            continue
        document = documents.store_bytes(
            db,
            data,
            source=meta.get("source") or "UPLOAD",
            url=meta.get("url"),
            original_filename=meta.get("original_filename"),
        )
        mapping[old_uuid] = document.id
        report.documents += 1
    return mapping


def _resolve_entity(
    db: DbSession,
    row: dict[str, Any],
    *,
    household_id: uuid.UUID,
    fallback_entity_id: uuid.UUID,
    cache: dict[str, uuid.UUID],
) -> uuid.UUID:
    """The entity a restored row is attributed to.

    By name, if the archive carries one (v3+) — refused, not guessed, when no
    entity of that name exists here yet (ADR-0007). Onto the entity the caller
    chose, for a v1/v2 archive that never recorded a name.
    """
    name = row.get("entity")
    if name is None:
        return fallback_entity_id
    if name in cache:
        return cache[name]
    entity = db.scalar(
        select(Entity).where(
            Entity.household_id == household_id,
            Entity.name == name,
            Entity.is_deleted.is_(False),
        )
    )
    if entity is None:
        raise ValidationError(
            f"A entidade «{name}» não existe neste agregado. Importe as entidades "
            "primeiro, em Definições › Cópia de segurança › Entidades."
        )
    cache[name] = entity.id
    return entity.id


def _restore_locations(db: DbSession, collection: dict[str, Any], report: LegoBackupReport) -> None:
    for row in collection.get("storage_locations", []):
        location_id = _as_uuid(row["id"])
        if location_id is None or db.get(StorageLocation, location_id) is not None:
            report.skipped_storage_locations += 1
            continue
        db.add(
            StorageLocation(
                id=location_id,
                area=row["area"],
                container=row.get("container"),
                description=row.get("description"),
                capacity_pct=row.get("capacity_pct"),
            )
        )
        report.storage_locations += 1
    db.flush()


def _restore_models(
    db: DbSession,
    collection: dict[str, Any],
    household_id: uuid.UUID,
    fallback_entity_id: uuid.UUID,
    entity_cache: dict[str, uuid.UUID],
    document_map: dict[uuid.UUID, uuid.UUID],
    report: LegoBackupReport,
) -> None:
    for row in collection.get("models", []):
        model_id = _as_uuid(row["id"])
        if model_id is None or db.get(LegoSetModel, model_id) is not None:
            report.skipped_models += 1
            continue
        entity_id = _resolve_entity(
            db,
            row,
            household_id=household_id,
            fallback_entity_id=fallback_entity_id,
            cache=entity_cache,
        )
        old_image = _as_uuid(row.get("image_document_id"))
        db.add(
            LegoSetModel(
                id=model_id,
                entity_id=entity_id,
                set_number=row.get("set_number"),
                is_custom=bool(row.get("is_custom")),
                name=row["name"],
                theme=row.get("theme"),
                subtheme=row.get("subtheme"),
                release_date=_as_date(row.get("release_date")),
                retirement_date=_as_date(row.get("retirement_date")),
                piece_count=row.get("piece_count"),
                minifig_count=row.get("minifig_count"),
                age_min=row.get("age_min"),
                age_max=row.get("age_max"),
                box_height_cm=_as_decimal(row.get("box_height_cm")),
                box_width_cm=_as_decimal(row.get("box_width_cm")),
                box_depth_cm=_as_decimal(row.get("box_depth_cm")),
                box_weight_kg=_as_decimal(row.get("box_weight_kg")),
                rrp_eur=_as_decimal(row.get("rrp_eur")),
                current_value_eur=_as_decimal(row.get("current_value_eur")),
                value_updated_at=_as_date(row.get("value_updated_at")),
                image_document_id=document_map.get(old_image) if old_image else None,
                short_description=row.get("short_description"),
                notes=row.get("notes"),
            )
        )
        report.models += 1
    db.flush()


def _restore_images(
    db: DbSession,
    collection: dict[str, Any],
    document_map: dict[uuid.UUID, uuid.UUID],
    report: LegoBackupReport,
) -> None:
    for row in collection.get("images", []):
        image_id = _as_uuid(row["id"])
        model_id = _as_uuid(row["lego_set_model_id"])
        new_document = document_map.get(_as_uuid(row["document_id"]) or uuid.uuid4())
        if image_id is None or new_document is None or db.get(LegoSetImage, image_id) is not None:
            report.skipped_images += 1
            continue
        if model_id is None or db.get(LegoSetModel, model_id) is None:
            report.skipped_images += 1
            continue
        db.add(
            LegoSetImage(
                id=image_id,
                lego_set_model_id=model_id,
                document_id=new_document,
                position=row.get("position") or 0,
                caption=row.get("caption"),
            )
        )
        report.images += 1
    db.flush()


def _restore_instructions(
    db: DbSession,
    collection: dict[str, Any],
    document_map: dict[uuid.UUID, uuid.UUID],
    report: LegoBackupReport,
) -> None:
    for row in collection.get("instructions", []):
        instruction_id = _as_uuid(row["id"])
        model_id = _as_uuid(row["lego_set_model_id"])
        new_document = document_map.get(_as_uuid(row["document_id"]) or uuid.uuid4())
        if (
            instruction_id is None
            or new_document is None
            or db.get(LegoSetInstruction, instruction_id) is not None
        ):
            report.skipped_instructions += 1
            continue
        if model_id is None or db.get(LegoSetModel, model_id) is None:
            report.skipped_instructions += 1
            continue
        db.add(
            LegoSetInstruction(
                id=instruction_id,
                lego_set_model_id=model_id,
                document_id=new_document,
                description=row.get("description") or "Manual",
                language=row.get("language"),
                position=row.get("position") or 0,
            )
        )
        report.instructions += 1
    db.flush()


def _restore_instances(
    db: DbSession,
    collection: dict[str, Any],
    household_id: uuid.UUID,
    fallback_entity_id: uuid.UUID,
    entity_cache: dict[str, uuid.UUID],
    document_map: dict[uuid.UUID, uuid.UUID],
    report: LegoBackupReport,
) -> None:
    for row in collection.get("instances", []):
        instance_id = _as_uuid(row["id"])
        model_id = _as_uuid(row["lego_set_model_id"])
        if instance_id is None or db.get(LegoSetInstance, instance_id) is not None:
            report.skipped_instances += 1
            continue
        if model_id is None or db.get(LegoSetModel, model_id) is None:
            report.skipped_instances += 1
            continue
        entity_id = _resolve_entity(
            db,
            row,
            household_id=household_id,
            fallback_entity_id=fallback_entity_id,
            cache=entity_cache,
        )
        location_id = _as_uuid(row.get("storage_location_id"))
        if location_id is not None and db.get(StorageLocation, location_id) is None:
            location_id = None
        old_photo = _as_uuid(row.get("photo_document_id"))
        db.add(
            LegoSetInstance(
                id=instance_id,
                entity_id=entity_id,
                lego_set_model_id=model_id,
                acquisition_date=_as_date(row.get("acquisition_date")),
                acquisition_cost_eur=_as_decimal(row.get("acquisition_cost_eur")) or Decimal("0"),
                acquisition_source=row.get("acquisition_source"),
                # `acquisition_transaction_id` is deliberately dropped: it points
                # into a ledger this installation does not have (ADR-0005), and a
                # dangling id is worse than an honest gap.
                storage_location_id=location_id,
                build_state=row.get("build_state"),
                condition=row.get("condition"),
                has_box=bool(row.get("has_box", True)),
                has_instructions=bool(row.get("has_instructions", True)),
                missing_parts=row.get("missing_parts"),
                ownership_status=row.get("ownership_status") or "IN_COLLECTION",
                sale_price_eur=_as_decimal(row.get("sale_price_eur")),
                sale_date=_as_date(row.get("sale_date")),
                photo_document_id=document_map.get(old_photo) if old_photo else None,
                notes=row.get("notes"),
            )
        )
        report.instances += 1
    db.flush()
