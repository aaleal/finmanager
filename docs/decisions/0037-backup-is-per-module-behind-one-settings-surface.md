# 0037 — Backup is per-module, behind one Definições surface

## Context

ADR-0032 gave LEGO a round-trip archive and put its buttons on the LEGO page,
because LEGO was the only module that had one. That stops being true the moment
a second module needs the same thing: nothing about "primary keys travel,
`entity_id`/`document_id` are remapped, existing rows are skipped" is specific to
LEGO, and a household with several modules will not want to hunt through each
one for its own backup button.

Two shapes were rejected:

- **One shared archive format for every module.** It would force every future
  module's tables into the same JSON shape LEGO happens to have today, or force
  the importer to know each module's schema. Neither survives a module whose
  rows do not look like LEGO's.
- **Concatenating every module's rows into one `collection.json`.** A module
  restoring its own archive would then have to parse a file it does not own,
  and a corrupt entry in one module would block every other module's rows in
  the same request from restoring.

## Decision

A tiny registry (`app/services/backup_service.py`) holds one `ModuleBackup` per
module — its own `build_archive` / `restore_archive` / `filename`, exactly what
`lego_backup.py` already exposed. Nothing about a module's archive shape leaves
its own file; the registry only reads the `format` string every module's own
manifest already carries, to route bytes back to the module that wrote them.

`GET /api/settings/backup.zip` takes a `module=` query (default `all`):

- **One module** returns that module's own archive, byte-identical to what
  `GET /lego/backup.zip` used to produce — an old LEGO archive still restores.
- **`all`** wraps every registered module's own archive, unmodified, under
  `modules/<key>.zip`, behind a `finmanager.backup` manifest that lists what is
  inside. No module's rows are merged into a shared structure.

`POST /api/settings/backup` accepts either shape without a `module=` hint: it
reads the root manifest, and if the format is the global one it restores every
nested archive through its own module, otherwise it matches the format against
the registered modules and restores that one. The response is one
`ModuleBackupReport` (counts + skips) per module actually restored — a single
entry for a lone archive, several for the global one.

The Definições page is now the only place a backup or restore button appears;
the LEGO page no longer carries its own.

## Consequences

- Every module keeps its own restore rules exactly as it defined them — LEGO's
  stay ADR-0032's, unchanged by this file. A future module writes its own
  `build_archive`/`restore_archive` and adds one entry to `modules()`; this file
  never grows a per-module branch.
- The global archive is only ever a container: restoring it can partially
  succeed (one module's rows land, another's do not) without one module's
  failure discarding another's, because each nested archive is opened and
  restored independently.
- An archive exported for a single module before this change still restores
  today, because that module's own byte format never changed — only where the
  button lives, and what wraps it for "back up everything", did.
