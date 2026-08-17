# 0022 — Price history is append-only and stores no quotient

## Context

The household wants €/kg trends and shrinkflation alerts. The obvious shape is a
mutable "current price" row per product/merchant, with €/kg and a shrinkflation
flag stored alongside it, updated whenever a fresher observation arrives.

## Decision

`product_price_history` is append-only. A correction — a review edit made after
the price was first frozen — writes a **new** row; the superseded one stays.
€/kg is not a column: price and weight share a row, so the division is always
consistent with its own inputs and there is no second value to keep in step.
`shrinkflation_indicator` is not a column either; it is computed over the
12-month window at query time.

## Consequences

- The index on `source_receipt_item_id` is deliberately **not** unique, which is
  what permits the correction; idempotency instead comes from
  `record_observations()` skipping an observation whose date, prices and weight
  are all unchanged.
- A stored quotient would silently disagree with its own inputs after any edit —
  the price could move and the €/kg column stay stale until something remembered
  to recompute it. A frozen shrinkflation flag would be worse: a claim about a
  future the row could not see when it was written.
- The cost is that the table grows with corrections, which is exactly the audit
  trail this module wants — the same trade `audit_logs` already makes for every
  other financial fact.
