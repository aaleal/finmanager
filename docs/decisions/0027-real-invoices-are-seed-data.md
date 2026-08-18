# 0027 — The eleven real *talões* are seed data, not test fixtures

## Context

The household's eleven real invoices lived under `apps/api/tests/fixtures/receipts/`
and were read only by the parser tests. The consequence was visible in the app:
a freshly seeded installation had exactly one demo receipt, created by writing
rows directly, with **no `Document` behind it** — so the review pane had nothing
to show, «Reprocessar» had nothing to re-read, and the crown-jewel screen could
not be demonstrated on a clean install.

The orchestrator brief already calls these files seed: *"For M1 the seed is
**real**: eleven fixtures and a 2,429-row spreadsheet live under
`seed/supermarket/`."*

## Decision

The invoices move to `app/seed/data/invoices/` and are exposed as
`app.seed.INVOICES_DIR`. The seed ingests them **through the ordinary upload
path** — `create_from_upload()` then `parse_receipt()` — rather than by writing
rows.

The parser tests import the very same constant, so there is one copy of each
file and a fixture cannot drift from what the demo shows.

## Consequences

- A seeded installation has eleven receipts, each with a stored `Document`, a
  `ProcessingJob`, and the `MerchantParserProfile` that actually ran. FR-1.16's
  *retry from the stored document* works on seeded data, which is the only way to
  exercise it without uploading by hand.
- The seed is idempotent for free: the same bytes hash to the same `Document`, so
  re-running returns the receipt already held. Nine of eleven were ingested on
  the run that introduced this, because two were already present from earlier
  manual uploads — which is the idempotency rule working, not a failure.
- The seed no longer invents plausible-looking numbers for those eleven. What it
  shows is what the parsers actually extract, including the two Continente
  receipts whose printed total genuinely **is** `0,00` because the cartão balance
  paid for them, and the Piquete photograph that lands in `NEEDS_REVIEW` at 0.58
  because OCR on a skewed *talão* is the hard case the module says it is.
- The hand-written demo receipt stays: it is the one that carries an appended Fs
  article, a prorated loyalty discount, a refund and a deposit return together,
  which no single real fixture does.
- These are real household documents, with masked loyalty numbers and the
  household NIF, committed to the repository. That was already true when they
  were test fixtures; this decision does not change what is stored, only where.
