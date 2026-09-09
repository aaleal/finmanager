# 0054 — A storage purge clears the reference, not the copy

## Context

`DELETE /lego/storage-locations/{id}` refuses to remove a location that
still holds copies («Este local tem N cópia(s) guardada(s). Mova-as
primeiro.») — the same one-row-at-a-time caution as `delete_model`
(ADR-0053). Clearing storage ahead of a fresh import needs the same
shortcut: a household re-doing its arrumação layout, or re-importing after a
bad bulk-import of locations, should not have to move every copy to «no
location» by hand first, nor reach for `./fm reset`.

Storage locations are shared, not entity-scoped (ADR-0046), so there is no
household boundary to apply here the way ADR-0053 scopes the collection
purge to the caller's entities: a storage purge is necessarily all-or-nothing
for the whole installation.

## Decision

A new endpoint, `DELETE /lego/storage-locations`, hard-deletes every
`StorageLocation` — no per-row guard. Unlike the collection purge, it does
not cascade the copies that referenced those locations: `LegoSetInstance`
rows keep existing, with `storage_location_id` set to `NULL`. A copy losing
its shelf is not the same fact as a copy being discarded, and the two must
not be conflated by a single button.

Restricted to `OWNER`, same as ADR-0053, and audited as one `PURGE` row
carrying the count of locations removed.

## Consequences

- After this purge, copies that used to show an area/container show
  «sem local» instead, exactly like a copy that was never assigned one.
- Re-importing the storage sheet (`POST /lego/storage-locations/bulk`,
  ADR-0048) after a purge recreates the rows; existing copies do not
  reattach automatically, because the purge did not remember which location
  they came from — only that they no longer have one.
- Because storage locations carry no `entity_id`, this endpoint has no
  scoping to apply and always affects every location in the installation.
