# 0023 — Fs observations carry the notional value in both price columns

## Context

An Fs article's `paid_price_eur` on the receipt line is always `0.00` — that is
the whole point of the Fs model
([ADR-0015](0015-fs-articles-are-appended-not-flagged.md)). Copying that zero
into the price history is the obvious thing to do, and is wrong.

## Decision

On an Fs observation, **both** `list_price_eur` and `paid_price_eur` carry the
notional value, never `0.00`, and `is_fs` travels onto the row so any analysis
can filter.

## Consequences

- The receipt item records what was *spent*; the price history records what the
  product was *worth*. Writing the literal zero would drag every paid-price
  trend for that product towards zero and poison both the €/kg series and the
  shrinkflation window.
- Safety comes from **visibility, not exclusion**: `is_fs` lives on the
  observation row itself, so the `fs` filter (`only`/`exclude`/`all`) never
  needs a join back to `receipt_items`.
- The two-measures grammar, stated plainly: `paid_price_eur` answers "what did
  I spend", `notional_value_eur` answers "what was it worth", and the two are
  identical on every non-Fs row — which is exactly what lets Fs articles join
  any dashboard without a special case.
