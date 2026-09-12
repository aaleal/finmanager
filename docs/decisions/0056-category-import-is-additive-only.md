# 0056 — Category import is additive-only, and it round-trips through the export

## Context

The taxonomy editor («Categorias» tab) already supports rename, reparent,
merge and retire, each a careful, audited, single-node operation with its
own impact check. The request was for two more buttons: an export of the
whole tree "and their relation" (the hierarchy, not just a flat list of
names), and an import that "receives an excel and imports that given set of
categories".

The obvious shape to copy is the LEGO module's export/import pair
(`lego_export.py` writes the PT-labelled columns `lego_bulk_import.py` reads
back, Decision #48): the file a household downloads should also be a valid
file to hand back in.

## Decision

**One workbook sheet, one row per category node.** Each row carries the
node's own name in the column matching its level (`Nível 1`/`Nível 2`/
`Nível 3`) and every ancestor's name to its left, plus `Eixo de marca` for
the node the row represents. This is the same "L1/L2/L3 by name" shape the
supermarket legacy importer already reads (`products_service.py`'s
`_category_from_sheet`-equivalent path lookup), so the format has one
precedent in this codebase, not two competing ones.

**Import only creates what's missing — it never renames, moves, merges or
deletes.** For each row, the L1→L2→L3 chain is walked top-down; a name
already present under the same parent (case-insensitive) is left exactly as
it is, and only a genuinely new node is created (with the row's own
`Eixo de marca` flag, since that column applies to that node only, not to
its ancestors). This mirrors `ensure_categories()`, the same idempotent,
additive contract the whole GROCERY tree is seeded with at boot: safe to
run against an installation that already has some or all of the sheet's
categories, and safe to re-run the same file twice.

Category *editing* already has a purpose-built, audited surface (rename /
reparent / merge / retire, each with an impact count first). Import
deliberately does not duplicate that: a row that names an existing category
under a *different* parent than the sheet implies does not move it — moving
is what «Mover» is for, with its own ancestor-refresh transaction. Making
import additive-only keeps its failure mode boring: the worst a bad file can
do is create a few oddly-named categories, never silently relocate or delete
real ones.

**A row with a gap (e.g. `Nível 3` filled but `Nível 2` blank) is rejected,
not guessed.** Every created node is still audited individually through
`create_category()`, so an import is fully reversible from `AuditLog` like
any other write in this module.

## Consequences

- `GET /api/categories/export.xlsx` and `POST /api/categories/import` join
  the categories router; both are household-wide (categories are not
  entity-scoped), same as the taxonomy editor itself.
- The import result reports `created` (new rows) and `existing` (rows whose
  whole path was already there) rather than "created/updated", since no
  field on an existing node is ever touched.
- If a future need arises to *change* an existing category via spreadsheet
  (rename in bulk, re-flag `Eixo de marca` on existing nodes), that is a
  distinct, separately-reviewed feature — not an extension of this importer.
