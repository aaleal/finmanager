# 0005 — LEGO purchase link kept as a column until the ledger exists

## Context

M9 FR-9.5 lets a user link a copy to the bank `Transaction` that paid for it, via
the shared transaction picker (UX-9.7). M9 is built **second**; the canonical
`Transaction` table belongs to M2 and is built third. The brief is explicit that the
ledger row must never be redefined outside M2, and equally explicit that the link
should be "wired for real once M2 exists".

Two bad options were available: invent a partial `transactions` table now and risk
contradicting the M2 specification, or drop the link entirely and retrofit both the
schema and the UI later.

## Decision

Ship the **contract**, defer the **constraint**.

- `lego_set_instances.acquisition_transaction_id` exists now as a nullable `UUID`
  column with **no foreign key**. It is written, read and cleared through the normal
  API.
- `GET /api/transactions/suggest` exists now and answers
  `{"ledger_available": false, "items": [], "message": …}`.
- The shared `TransactionPicker` component is built now, in the shared frontend
  layer, and renders that message instead of an empty list — so the UI explains
  itself rather than appearing broken.

When M2 lands: create `transactions`, implement `/transactions/suggest` for real, and
add the FK in an additive migration. No M9 schema column, API field or component
prop changes.

## Consequences

- The M9 Definition of Done item is genuinely satisfied end to end today, minus the
  data that does not exist yet.
- Referential integrity for this one column is unenforced in the interim. The column
  is nullable and only ever set from a picker that currently returns nothing, so the
  practical exposure is zero.
- The FK migration is a follow-up task owned by M2 and is recorded here so it is not
  forgotten.
