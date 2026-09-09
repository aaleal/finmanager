# 0055 — The supermarket module stops calling itself "receipts"

## Context

Module 1's code lived under `receipts` almost everywhere — `app/models/receipts.py`,
`app/services/receipts/`, `app/api/routers/receipts.py`, `app/schemas/receipts.py`,
`web/src/features/receipts/`, `/api/receipts/*` — even though the module's own
docstring already called it *"Supermarket & Receipt Processing"*, and the
frontend route has been `routes/supermercado.tsx` from the start. Parsing a
receipt is *how* this module works; being the household's supermarket ledger —
merchants, products, categories, prices, loyalty — is *what* it is. Nothing else
in the brief needs a "receipts" module; several things need their own kind of
receipt.

That collision is not hypothetical. [00.prompts/modules/03-health.md](../../00.prompts/modules/03-health.md)
already describes logging a *"medical receipt"* as Module 3's own concept, and
[00.prompts/modules/02-banking.md](../../00.prompts/modules/02-banking.md)
reconciles bank transactions against three sibling document kinds — this
module's receipts, health claims, and utility bills. `app/models/__init__.py`
re-exports every model into one flat namespace for Alembic's autogenerate, so a
future `Receipt` defined by the Health module would collide outright with this
one. Compare Module 9: `LegoSetModel`/`LegoSetInstance`/`lego_set_models` all
carry the module's name, while genuinely shared reference data — `Merchant`,
`StorageLocation` — deliberately does not (ADR-0046). `Receipt`/`ReceiptItem`
were the one module-specific pair that never got that prefix.

## Decision

The module is `supermarket` in code, matching what it has always been called
in prose:

- Folders and files: `app/models/receipts.py` → `app/models/supermarket.py`,
  `app/services/receipts/` → `app/services/supermarket/`,
  `app/api/routers/receipts.py` → `app/api/routers/supermarket.py`,
  `app/schemas/receipts.py` → `app/schemas/supermarket.py`,
  `web/src/features/receipts/` → `web/src/features/supermarket/`. Test files
  follow (`test_receipt_*.py` → `test_supermarket_*.py`).
- ORM classes: `Receipt` → `SupermarketReceipt`, `ReceiptItem` →
  `SupermarketReceiptItem`. Tables follow: `receipts` → `supermarket_receipts`,
  `receipt_items` → `supermarket_receipt_items`, and every index/constraint
  derived from those names, via a real `ALTER TABLE ... RENAME` migration (no
  data loss, a real `downgrade()`).
- The public surface: `/api/receipts/*` → `/api/supermarket/*`,
  `/api/receipt-items` → `/api/supermarket-items`,
  `/api/receipts/analytics/*` → `/api/supermarket/analytics/*`,
  `/api/receipts/import/legacy` → `/api/supermarket/import/legacy`. Routes that
  never carried "receipt" in their path (`/parser-profiles`, `/master-products`,
  `/categories`, `/product-aliases`) are unchanged.
- Everywhere a string literal encoded the old name as *data*, not just as code —
  `ReviewTask.module`, `ReviewTask.subject_type`, `Link.from_type`,
  `AuditLog.table_name`, `ProcessingJob.job_type`, `ImportBatch.module`, the
  `Setting.key` for the arithmetic tolerance — the migration also rewrites the
  existing rows, so history stays legible instead of silently going stale.

What did **not** change: the Pydantic response/request schemas
(`ReceiptSummary`, `ReceiptDetail`, `ReceiptItemOut`, `ReceiptDerived`, …) and
their generated TypeScript types. They live in `app/schemas/`, which — unlike
`app/models/__init__.py` — is never aggregated into one shared namespace, so
they carry none of the collision risk that forced the model rename. Renaming
them would have doubled the size of this change (every frontend component that
already reads a `ReceiptSummary` off the wire) for no corresponding benefit. A
receipt is still, correctly, called a receipt in the API response — it is only
the module's *identity* that needed disambiguating from a health claim or a
utility bill that also happens to arrive as a "receipt".

## Consequences

- Any local clone or fork with in-flight branches against the old paths needs a
  rebase; this is a single-household, self-hosted app with no external API
  consumers, so the breaking path change ships in the same release as the rest
  of the rename rather than behind a deprecation shim.
- The next time the Health module needs its own notion of a receipt, it can be
  called exactly that — `HealthClaim` or similar — without stepping on this
  module's `SupermarketReceipt`.
- `docs/architecture.md`, `docs/database.md`, `docs/testing.md`,
  `docs/capabilities.md` and `README.md` were updated to match; ADRs before this
  one keep referencing the old names, because an ADR records the decision as it
  was made, not as the code reads today.
