# 0046 — Storage locations are shared, not entity-scoped

## Context

`StorageLocation` carried `entity_id` from M9's first migration, unique per
`(entity_id, area, container)`. That was never argued for specifically — it
followed the module-wide habit of every LEGO table carrying `entity_id`
(ADR-0007). Asked directly, it does not hold up: «Garagem › Caixa A» is one
shelf. It does not become a second shelf because a different household member
put a set in it, any more than a tin of tomatoes becomes a different tin
because a different member paid for it — the exact question ADR-0019 already
answered for the product catalogue.

The bug this produced was concrete: with the entity selector on one member,
`GET /lego/storage-locations` returned only *that* member's locations, even
though the physical box holds everyone's sets; and nothing stopped two rows,
`(Ana, Garagem, Caixa A)` and `(Bruno, Garagem, Caixa A)`, from coexisting as
if they were different places.

## Decision

`StorageLocation` drops `entity_id` entirely. Its unique constraint becomes
`(area, container)` — one shelf, one row, regardless of who is looking.
Attribution stays exactly where it already lived for everything else a
location holds: `LegoSetInstance.entity_id`.

Creating, renaming or deleting a location no longer asks for an entity, and is
no longer refused while the selector is on «todas» — there is nothing left to
attribute. The LEGO backup archive (ADR-0032) now exports every live location
unconditionally, the same way it would a shared catalogue, rather than
filtering by whichever entity's collection is being exported.

## Consequences

- The storage panel, and the storage-location picker inside the copy dialog,
  show the same list no matter which entity is selected.
- The export workbook's «Arrumação» sheet drops its «Entidade» column — a
  location has none.
- A pre-existing archive's storage rows still restore: they never carried
  more than `area`/`container`/`description`/`capacity_pct` in the first
  place, so the shape on disk is unchanged, only what the restore *does* with
  it (it no longer forces an entity onto the row).
- Downgrading the migration cannot recover which entity a location used to
  belong to — the column returns `NULL` on every row, to be filled in by hand
  if the deployment ever needs it.
