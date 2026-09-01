"""Schemas for the generic backup/restore surface (Definições)."""

from __future__ import annotations

from pydantic import BaseModel


class BackupModuleOut(BaseModel):
    """One module this installation knows how to back up. LEGO is the only one
    today; the list grows as other modules register themselves."""

    key: str
    label: str


class ModuleBackupReport(BaseModel):
    """What one module's restore actually did, in module-agnostic shape."""

    module: str
    label: str
    counts: dict[str, int]
    skipped: dict[str, int]


class BackupImportReport(BaseModel):
    """One entry per module restored — one for a single-module archive, several
    for the global container."""

    modules: list[ModuleBackupReport]
