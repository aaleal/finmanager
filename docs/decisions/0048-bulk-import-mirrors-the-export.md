# 0048 — Bulk import mirrors the export, and only local data is checked before Brickset runs

## Context

Registering a real household's backlog of LEGO sets one dialog at a time does
not scale once there are dozens to enter. The request was for a spreadsheet
upload — one row per physical copy — with a corrective preview step before
anything is written, and an equivalent shortcut for populating storage
locations in bulk next to «Novo local».

Two existing surfaces already define the shape of this data and could not be
ignored:

- `GET /lego/export.xlsx` (`lego_export.py`) already writes a «Cópias» sheet
  (30 columns, mostly derived/read-only) and an «Arrumação» sheet, in pt-PT
  labels.
- The manual add-copy dialog (`add-set-dialog.tsx`) already defines the
  minimum a copy needs: a set number, and everything else about the *copy*
  (cost, date, origin, storage, build state, condition). Everything about the
  *set* — name, theme, dates, piece count, RRP, cover photo, manuals — comes
  from Brickset, contacted only on an explicit action (the module-wide
  guarantee behind `lego_provider.py`).

## Decision

**Bulk import reads columns by header name, not position, against the same
PT labels the export writes.** The practical effect: exporting the collection
and re-uploading that exact file through "Importar em lote" is a supported
round trip, not a coincidence — every export column the importer doesn't
need (name, theme, ROI, ...) is simply ignored rather than rejected. The
importer accepts either the full export sheet or a hand-built spreadsheet
carrying only the columns it actually reads: Número, Entidade, Área,
Contentor, Estado de construção, Condição, Tem caixa, Tem instruções, Peças
em falta, Data de aquisição, Origem, Custo (€), Notas.

**Preview only resolves local references — it never contacts Brickset.**
`POST /lego/instances/bulk/preview` matches each row's entity name and
storage area/container against the household's own data and normalizes the
PT enum labels (origem/estado/condição), returning per-field errors for
anything it can't resolve (unknown entity, unknown location, unrecognised
label). The review table lets the user fix exactly those cells. Whether a
set number actually exists on Brickset is discovered only at
`POST /lego/instances/bulk/commit`, one row at a time — the same lookup the
manual "Procurar" button performs, including the automatic gallery/manuals
import for a genuinely new set. This keeps the "Brickset only on an explicit
action" guarantee intact: a preview never touches the network, even for 500
rows.

**A row whose set isn't found on Brickset (or Brickset is off) fails only
that row.** Bulk import has no name field to fall back on the way the manual
form does (typing the name by hand when lookup fails) — the sheet's contract
is deliberately just the 13 columns above. That row's result reports
"registe-o manualmente primeiro" instead of blocking the other 499 rows.
Commit is therefore **not transactional across rows**: each row is created
(model find-or-create, then instance) independently in the same request, and
a later row's failure never undoes an earlier row's success.

**Instance rows are never deduplicated; storage rows are upserted.** A copy
has no natural key — re-importing the same export doubles every copy, exactly
as registering it twice by hand would. Storage rows *are* keyed on
`(area, container)` (ADR-0046's own unique constraint) and upserted:
re-importing the exported «Arrumação» sheet updates capacity/description in
place. This asymmetry is intentional, not an oversight — it follows directly
from what each row already means in the rest of the module.

## Consequences

- `apps/api/app/services/lego_bulk_import.py` is the only place spreadsheet
  headers are matched by name; `lego_export.py`'s PT labels are the source of
  truth it reads from (`SOURCE_PT`/`BUILD_STATE_PT`/`CONDITION_PT`), so a
  label added there is understood here for free.
- The review table's "green" state is a client-side mirror of the same
  per-field checks the preview endpoint runs — editing a cell (via the same
  entity/storage/enum options the rest of the app already offers) clears
  that field's error locally without a round trip; only the initial parse and
  the final commit hit the API.
- A set created mid-batch (model row written, Brickset gallery import
  attempted, but the instance itself failing for an unrelated reason) is left
  in place rather than rolled back — harmless, and it means the same row
  succeeds on retry via the ordinary find-or-create path instead of hitting
  Brickset twice.
- MOCs (`is_custom`) and brand-new sets Brickset has never heard of are out of
  scope for bulk import — they have no way to supply a name through 13
  columns. They stay on the manual dialog, which already handles them.
