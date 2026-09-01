# 0034 — Reopening a confirmed receipt, and what confirming costs

## Context

Confirming a receipt did two things: it moved the status to `CONFIRMED` and it
froze one price observation per **resolved** line. `record_observations()` skips
a line with no `master_product_id`, so confirming a receipt that still had
unresolved lines silently dropped those purchases from the price history — the
one record the module exists to build — with no way to notice and no way back.

`CONFIRMED` also transitioned only to `VOID`. Reprocessing was therefore
impossible after confirmation, but the button stayed enabled and simply failed,
and a receipt confirmed in error had no remedy short of voiding a document that
was perfectly valid.

## Decision

Two changes, one at each end.

**Confirming is blocked while lines are unresolved.** The button is disabled and
says why. Every line resolving to a product is a rubric of the module, not a
nicety: without one there is no category, no price history and no €/kg.

**`CONFIRMED → NEEDS_REVIEW` is a legal transition**, exposed as
`POST /receipts/{id}/reopen` and offered as *Reabrir* where *Confirmar* used to
be. Reprocessing stays illegal from `CONFIRMED`, and the button is now disabled
to match: re-reading the document would discard the review that was just done.

## Consequences

- Reopening is **not** an undo. The observations frozen on confirmation are
  append-only (ADR-0022) and stay exactly where they are; a correction made
  after reopening writes a new observation beside the old one, and re-confirming
  an unchanged receipt writes nothing because `record_observations()` skips an
  observation whose date, prices and weight are all unchanged.
- `VOID` remains terminal and remains the answer to a receipt that should not
  exist. Reopening is the answer to a receipt that was read wrongly.
- The status machine keeps its shape: every transition is still explicit in
  `RECEIPT_TRANSITIONS` and anything absent from it is still refused.
