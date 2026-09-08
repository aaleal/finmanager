# 0052 — The sheet's own PVP only fills what Brickset left empty

## Context

[ADR-0051](0051-a-dollar-rrp-is-better-than-no-rrp.md) already stretched how
far Brickset itself will go to avoid an empty `rrp_eur`: DE first, US as a
1:1 fallback. Some sets still come back with neither — very old, very
regional, or simply never priced on either LEGO.com store. Bulk import
(ADR-0048) is exactly where this bites hardest: a household transcribing a
real backlog usually knows the PVP it actually paid or saw printed on the
box, and the export/import sheet already has a "PVP original (€)" column
(the same one `lego_export.py` writes) sitting unread next to "Preço atual
(€)" — which bulk import *already* uses to seed `current_value_eur`.

The alternative — parsing every set-level column the export writes (name,
theme, dates, piece count, ...) and asking the user to arbitrate every
mismatch against Brickset — was considered and rejected. Bulk import's
entire premise (ADR-0048) is that *set* data comes from Brickset and the
sheet only supplies what's true of the *copy*; reopening that boundary for
every field turns a 13-column contract into a general-purpose reconciliation
tool, for a problem (RRP is occasionally missing) that a narrow fallback
already solves.

## Decision

**`rrp_eur` gains one more fallback, after Brickset's own DE→US chain: the
sheet's "PVP original (€)" column, read by `lego_bulk_import.py` exactly
like "Preço atual (€)" already is.** It only ever fills a gap:

- **New set (model created by this row's Brickset lookup):** `rrp_eur` is
  `lookup.rrp_eur` when Brickset returned one; the sheet's value is used
  only when Brickset's is `None`.
- **Existing set (model already on file):** the sheet's PVP backfills
  `model.rrp_eur` only when it is currently `None` — never overwriting a
  value already recorded, and (unlike `current_value_eur`) never taking a
  "highest across rows" reading, since RRP is a fixed historical fact, not
  something that legitimately varies copy to copy.

A Brickset-supplied RRP always wins. This is deliberately the same shape as
`current_value_eur`'s existing rule, not a new pattern.

## Consequences

- No other set-level field (name, theme, dates, piece count, ...) is read
  from the sheet — ADR-0048's 13-column contract is otherwise untouched.
- A household backfilling PVPs for its existing collection can simply
  re-import the same export with that column filled in; rows for sets that
  already have an RRP are no-ops on that field.
- If a future request needs the same treatment for another field, this ADR
  is the pattern to repeat — not a reason to build the general reconciliation
  tool this decision explicitly declined.
