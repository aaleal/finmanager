# 0038 — An env-provided Brickset key switches itself on

## Context

`BRICKSET_API_KEY` has existed in `.env.example` since Phase 1, with a comment
promising it would "pre-populate the setting on first seed". It never did:
`seed_settings()` only ever wrote the hard-coded default (an empty string), and
`make seed` is itself a developer convenience an owner is never required to
run. The result: an operator who deploys with the key already in `.env` still
had to open Definições, switch "Consulta ao Brickset" on and paste the key in
by hand — the one thing the environment variable looked like it should have
skipped.

Reset makes this worse than a one-time inconvenience. `make reset` destroys the
`Setting` table along with everything else, so every reset repeats the same
manual step, on every clean install, forever.

## Decision

On every boot — not only `make seed` — `settings_service.ensure_brickset_from_env()`
runs from the same `lifespan` hook that ensures reference data (ADR-0029). If
`BRICKSET_API_KEY` is set in the environment **and** the `Setting` row for the
key does not exist yet, it writes both `lego.brickset.api_key` and
`lego.brickset.enabled = true` in one step. If the row already exists — because
an owner saved a key, cleared one, or flipped the switch off, in Definições —
the function returns immediately and touches nothing.

This does not weaken "external providers are off by default": nothing turns on
unless whoever deploys the instance explicitly supplied a key, and Brickset is
still contacted only on an explicit «Procurar» (ADR unchanged there). It only
removes the manual Definições visit that added nothing — the operator already
made the opt-in decision by putting the key in `.env`.

## Consequences

- Gated on the `api_key` row alone, not the `enabled` row: an owner who disables
  Brickset from Definições without clearing the key stays disabled on the next
  boot, because the `api_key` row already exists from the first boot that set
  it.
- `.env`'s value only ever matters once per database's lifetime — the first
  boot that finds no `Setting` row. Editing `.env` afterwards changes nothing
  until `make reset` (or a manual `DELETE` of that row) starts the database
  over, by design: a live install's own Definições always outrank a file
  sitting on disk.
- `.env.example` no longer ships a real-looking key. It shipped one for three
  commits before this ADR — a placeholder that reads as genuine is itself worth
  avoiding in an example file, independent of whether it was ever live.
