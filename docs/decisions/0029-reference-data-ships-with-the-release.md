# 0029 — Reference data ships with the release, not with the seed

## Context

The grocery taxonomy (`supermarket-categories.pt-PT.json`, ~500 nodes) and the
merchant parser profiles lived in `app.seed`, alongside the LEGO inventory and
the eleven demo *talões*. That put a hard dependency on `make seed` in a place
it does not belong: a household that starts from a clean database — the normal
case for a self-hosted install — got an application that **cannot read a *talão***
(no parser profile matches, not even the generic fallback) and **cannot file a
product** (no category exists). The only way out was to run a command that also
imports someone else's LEGO collection.

`seed_categories` made it worse: it short-circuited on `COUNT(GROCERY) > 0`, so
a taxonomy that grew in a later release never reached an installation created
before it.

## Decision

Reference data is split out of the seed into `app.services.reference_data`, and
is **ensured on every API boot** from the FastAPI lifespan, after the entrypoint
has run `alembic upgrade head`.

Three things move: the grocery taxonomy (JSON now at `app/data/`), the
Portuguese merchants, and the parser profiles. Merchants come along because a
per-merchant profile has nowhere to attach without them.

Every `ensure_*` function is **row-level** idempotent, matched on a stable key —
`Category.code_en`, `Merchant.name`, `MerchantParserProfile.parser_key` — and
soft-deleted rows count as present. A node the household retired stays retired;
a profile it edited stays edited; a node a new release adds appears at the next
restart.

The seed keeps a `reference data` step that calls the same `ensure_all()`, so
`make seed` still works against a database the API has never started against.

## Consequences

- A clean installation can ingest an invoice immediately after the first-run
  setup, with no seed and no demo data.
- Taxonomy changes ship like code: edit the JSON, release, restart.
- Boot does one query per reference table on a warm database and writes nothing.
  A failure is logged and swallowed — a missing category must not stop the API
  from serving the rest of the household's data.
- `app.seed` is now what its name says: demonstration data only.

> **Superseded in part by [ADR-0057](0057-the-grocery-taxonomy-loads-on-demand-not-at-boot.md):**
> the grocery taxonomy is no longer ensured at boot — it loads on demand,
> triggered by the household from an empty categories table. Merchants and
> parser profiles are unaffected and are still ensured on every boot exactly
> as described above.

