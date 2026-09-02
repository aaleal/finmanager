"""Registry that turns per-module backups into one Definições surface.

Each module owns its own archive shape and its own restore rules — LEGO's are
ADR-0032 (primary keys travel, only ``entity_id``/``document_id`` are remapped,
existing rows are skipped). This file never touches those rules; it only routes
bytes to the module that wrote them, and bundles every module's own archive,
unmodified, behind one manifest for a "back up everything" export.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import io
import json
import uuid
import zipfile
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session as DbSession

from app.core.errors import ValidationError
from app.schemas.backup import BackupImportReport, ModuleBackupReport

#: The global container's own manifest format, distinct from any module's.
GLOBAL_FORMAT = "finmanager.backup"
GLOBAL_VERSION = 1
MODULES_DIR = "modules"

#: Guards against a zip bomb: an archive is trusted no more than any upload.
_MAX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024


@dataclasses.dataclass(frozen=True)
class ModuleBackup:
    key: str
    label: str
    #: The ``format`` string the module's own manifest carries — how a lone
    #: archive is recognised without a ``module=`` hint from the caller.
    format: str
    build_archive: Callable[[DbSession, list[uuid.UUID]], bytes]
    restore_archive: Callable[..., Any]
    filename: Callable[[], str]
    report_fields: tuple[str, ...]
    skipped_fields: tuple[str, ...]


def _entities_module() -> ModuleBackup:
    from app.services import entity_backup

    return ModuleBackup(
        key="entities",
        label="Entidades",
        format=entity_backup.FORMAT,
        build_archive=lambda db, entity_ids: entity_backup.build_archive(db, entity_ids),
        restore_archive=entity_backup.restore_archive,
        filename=entity_backup.filename,
        report_fields=("entities",),
        skipped_fields=("skipped_entities",),
    )


def _lego_module() -> ModuleBackup:
    from app.services import lego_backup

    return ModuleBackup(
        key="lego",
        label="Coleção LEGO",
        format=lego_backup.FORMAT,
        build_archive=lambda db, entity_ids: lego_backup.build_archive(db, entity_ids=entity_ids),
        restore_archive=lego_backup.restore_archive,
        filename=lego_backup.filename,
        report_fields=(
            "storage_locations",
            "models",
            "images",
            "instructions",
            "instances",
            "documents",
        ),
        skipped_fields=(
            "skipped_storage_locations",
            "skipped_models",
            "skipped_images",
            "skipped_instructions",
            "skipped_instances",
        ),
    )


def modules() -> dict[str, ModuleBackup]:
    """Every module that can back itself up.

    ``entities`` is registered first — and deliberately so — because a global
    archive's restore walks this dict in order: an entity referenced by name
    elsewhere (LEGO's own archive resolves its rows this way) must already
    exist by the time that module's own restore runs.
    """
    return {"entities": _entities_module(), "lego": _lego_module()}


def get_module(key: str) -> ModuleBackup:
    found = modules().get(key)
    if found is None:
        raise ValidationError(f"Módulo de cópia de segurança desconhecido: {key!r}.")
    return found


def _report_of(module: ModuleBackup, report: Any) -> ModuleBackupReport:
    dump = report.model_dump() if hasattr(report, "model_dump") else dict(report)
    return ModuleBackupReport(
        module=module.key,
        label=module.label,
        counts={field: int(dump.get(field, 0)) for field in module.report_fields},
        skipped={field: int(dump.get(field, 0)) for field in module.skipped_fields},
    )


# --- Export -------------------------------------------------------------------


def build_global_archive(db: DbSession, *, entity_ids: list[uuid.UUID]) -> bytes:
    """Every module's own archive, byte for byte, bundled behind one manifest."""
    included: dict[str, dict[str, str]] = {}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for module in modules().values():
            archive.writestr(
                f"{MODULES_DIR}/{module.key}.zip", module.build_archive(db, entity_ids)
            )
            included[module.key] = {"label": module.label}
        archive.writestr(
            "manifest.json",
            json.dumps(
                {
                    "format": GLOBAL_FORMAT,
                    "version": GLOBAL_VERSION,
                    "exported_at": dt.datetime.now(dt.UTC).isoformat(),
                    "modules": included,
                },
                ensure_ascii=False,
                indent=1,
            ),
        )
    return buffer.getvalue()


def global_filename(exported_on: dt.date | None = None) -> str:
    return f"copia-seguranca-finmanager-{exported_on or dt.date.today():%Y%m%d}.zip"


# --- Import -------------------------------------------------------------------


def _restore_module_bytes(
    db: DbSession,
    module: ModuleBackup,
    payload: bytes,
    *,
    entity_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
) -> ModuleBackupReport:
    report = module.restore_archive(db, payload, entity_id=entity_id, actor_user_id=actor_user_id)
    return _report_of(module, report)


def restore_any(
    db: DbSession,
    payload: bytes,
    *,
    entity_id: uuid.UUID,
    actor_user_id: uuid.UUID | None = None,
) -> BackupImportReport:
    """Restore whatever the archive is — one module's own file, or the global
    container — detected from the root manifest's ``format``, never guessed."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile as exc:
        raise ValidationError("O ficheiro não é um arquivo zip válido.") from exc

    with archive:
        if sum(info.file_size for info in archive.infolist()) > _MAX_UNCOMPRESSED_BYTES:
            raise ValidationError("Arquivo demasiado grande.")
        try:
            manifest = json.loads(archive.read("manifest.json"))
        except KeyError as exc:
            raise ValidationError("O arquivo não contém manifest.json.") from exc
        except json.JSONDecodeError as exc:
            raise ValidationError("manifest.json não é JSON válido.") from exc

        fmt = manifest.get("format")

        if fmt == GLOBAL_FORMAT:
            reports: list[ModuleBackupReport] = []
            for module in modules().values():
                try:
                    inner = archive.read(f"{MODULES_DIR}/{module.key}.zip")
                except KeyError:
                    continue
                reports.append(
                    _restore_module_bytes(
                        db, module, inner, entity_id=entity_id, actor_user_id=actor_user_id
                    )
                )
            if not reports:
                raise ValidationError("O arquivo não contém nenhum módulo reconhecido.")
            return BackupImportReport(modules=reports)

        matched: ModuleBackup | None = next(
            (candidate for candidate in modules().values() if candidate.format == fmt), None
        )
        if matched is None:
            raise ValidationError("Este arquivo não é uma cópia de segurança reconhecida.")
        report = _restore_module_bytes(
            db, matched, payload, entity_id=entity_id, actor_user_id=actor_user_id
        )
        return BackupImportReport(modules=[report])
