# 0053 — A collection purge skips the per-row guards

## Context

`DELETE /lego/models/{id}` refuses to remove a set that still has live copies
(«Elimine-as primeiro»), because a single accidental click on the wrong row
should not take a household's whole history with it. That guard is correct
for editing one set at a time, but it turns into an obstacle for the case
that actually shows up in practice: the legacy spreadsheet was imported
wrong, or a fresh Brickset key changed how sets should be matched, and the
fix is to empty the collection and re-run the import from a clean slate.

The only tool that already does that is `./fm reset`, which drops and
recreates the whole database — every module, every user, every session.
Reaching for it to fix one module's data is disproportionate, and it forces
whoever is testing a re-import to also redo first-run setup (ADR-0011)
before they can try again.

## Decision

A new endpoint, `DELETE /lego/collection`, hard-deletes every `LegoSetModel`
(and, by cascade, every `LegoSetInstance`, gallery image and manual) owned by
the entities the caller can see — no live-copies guard, no soft delete, no
recovery. It is restricted to `OWNER` (`Owner` dependency), same as the
backup restore endpoints, because it is equally destructive and equally
scoped to a full-module operation rather than a single record.

The action is audited once, as a single `PURGE` row carrying the count of
sets removed, rather than one `DELETE` row per set — the per-row audit trail
that `delete_model` produces exists to explain an individual deletion later;
a purge has one cause and one moment, and a thousand identical audit rows
would not make it easier to understand.

Storage locations are untouched by this endpoint — see ADR-0054 for why that
is a second, independent action.

## Consequences

- Re-importing after a bad run is a button in Definições, not a shell
  command: `DELETE /lego/collection` then re-upload the sheet or bulk-import
  file.
- The endpoint bypasses the "has live copies" guard on purpose — it is the
  point of the feature, not an oversight. Anyone who wants to keep a
  household's current collection must not click this button.
- Because it is entity-scoped like every other LEGO read (ADR-0007), a
  caller only ever purges the collection they can already see; running it
  once per household is what a full clean-up requires.
