# 0032 — The LEGO backup keeps its primary keys

## Context

`GET /lego/export.xlsx` already existed, and it is a **report**: three sheets
shaped for a human, with derived columns like ROI and no identifiers at all.
Nothing in it can rebuild the collection — the copies have no keys, the images
are absent, and a MOC and a retail set look the same once the set number is
blank.

Restoring a collection onto an installation that starts empty is a different
problem, and the obvious approaches both fail:

- **Re-import the workbook.** Every copy would have to be matched by a natural
  key, and a copy has none: two sealed 10307s bought the same day are genuinely
  indistinguishable. Importing twice would silently double the collection.
- **A plain SQL dump.** `entity_id` and `document_id` point at rows the target
  installation does not have, so the restore would either fail on a foreign key
  or import orphans.

## Decision

`GET /lego/backup.zip` writes an archive — `manifest.json`, `collection.json`,
`value-history.json` and the image bytes under `documents/` — and
`POST /lego/backup` restores it. Four rules govern it:

1. **Primary keys travel.** Every row keeps its UUID. Re-importing the same
   archive is therefore a no-op, because the rows are already there, and no
   natural key has to be invented for an instance that has none.
2. **Only two references are rewritten.** `entity_id` is remapped onto the
   entity the importer chose; `document_id` is remapped through the
   content-addressed store, which deduplicates by SHA-256.
3. **Existing rows are skipped, never merged.** An archive is a snapshot of a
   moment. Overwriting today's valuation with a month-old one is the single
   behaviour nobody would ask for, so the report counts the skips instead.
4. **`acquisition_transaction_id` is dropped.** It points into a ledger that
   does not exist yet (ADR-0005) and certainly not into the target
   installation's. A dangling id is worse than an honest gap.

## Consequences

- The valuation history comes along in `value-history.json`, read out of
  `audit_logs` — it lives there and nowhere else (ADR-0008), so an archive that
  skipped it would discard every price the collection was ever worth.
- Soft-deleted rows are left out. A backup restores a collection, and a row
  someone deleted is not part of it.
- The archive is opaque, and that is the trade: `export.xlsx` stays the file you
  open, this stays the file you keep. Neither is asked to be the other.
- The import trusts the archive no more than any upload: zip validity, a format
  marker, a version ceiling and an uncompressed-size limit are all checked
  before a single row is written.
