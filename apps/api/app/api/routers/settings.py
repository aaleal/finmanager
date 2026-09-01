from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, File, Response, UploadFile
from pydantic import BaseModel

from app.api.deps import CurrentAuth, Db, Owner, Writer, household_entity_ids, resolve_write_entity
from app.schemas.backup import BackupImportReport, BackupModuleOut
from app.services import settings_service

router = APIRouter(prefix="/settings", tags=["settings"])

# Only these keys are readable/writable over the API; anything else stays internal.
EXPOSED_KEYS = {
    settings_service.CONFIDENCE_AUTO_ACCEPT,
    settings_service.CONFIDENCE_REVIEW,
    settings_service.BRICKSET_ENABLED,
    settings_service.BRICKSET_API_KEY,
    settings_service.LEGO_STALE_VALUE_DAYS,
}

SECRET_KEYS = {settings_service.BRICKSET_API_KEY}


class SettingsOut(BaseModel):
    values: dict[str, Any]


class SettingsUpdate(BaseModel):
    values: dict[str, Any]


def _read(db: Db) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in sorted(EXPOSED_KEYS):
        value = settings_service.get(db, key)
        # Never echo a provider credential back to the browser.
        result[key] = bool(value) if key in SECRET_KEYS else value
    return result


@router.get("", response_model=SettingsOut)
def read_settings(ctx: CurrentAuth, db: Db) -> SettingsOut:
    return SettingsOut(values=_read(db))


@router.patch("", response_model=SettingsOut)
def update_settings(payload: SettingsUpdate, ctx: Owner, db: Db) -> SettingsOut:
    for key, value in payload.values.items():
        if key not in EXPOSED_KEYS:
            continue
        settings_service.set_value(db, key, value, updated_by=ctx.user.id)
    db.flush()
    return SettingsOut(values=_read(db))


# --- Backup & restore ---------------------------------------------------------
# One archive per module (ADR-0032 for LEGO's), plus a global export that bundles
# every module's own archive unmodified. Distinct from a module's own report
# export (e.g. `/lego/export.xlsx`): this keeps identifiers and rebuilds a
# collection on an empty installation, legible to nothing but the importer.
@router.get("/backup/modules", response_model=list[BackupModuleOut])
def list_backup_modules(ctx: CurrentAuth, db: Db) -> list[BackupModuleOut]:
    from app.services import backup_service

    return [
        BackupModuleOut(key=module.key, label=module.label)
        for module in backup_service.modules().values()
    ]


@router.get("/backup.zip", response_class=Response)
def export_backup(ctx: CurrentAuth, db: Db, module: str = "all") -> Response:
    from app.services import backup_service

    entity_ids = household_entity_ids(db, ctx)
    if module == "all":
        payload = backup_service.build_global_archive(db, entity_ids=entity_ids)
        name = backup_service.global_filename()
    else:
        target_module = backup_service.get_module(module)
        payload = target_module.build_archive(db, entity_ids)
        name = target_module.filename()
    return Response(
        content=payload,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.post("/backup", response_model=BackupImportReport)
def import_backup(
    ctx: Writer,
    db: Db,
    file: Annotated[UploadFile, File()],
    entity_id: uuid.UUID | None = None,
) -> BackupImportReport:
    """Restore an archive onto one entity — a single module's, or the global
    container. Existing rows are kept, never merged (ADR-0032)."""
    from app.services import backup_service

    target = resolve_write_entity(db, ctx, entity_id)
    return backup_service.restore_any(
        db, file.file.read(), entity_id=target, actor_user_id=ctx.user.id
    )
