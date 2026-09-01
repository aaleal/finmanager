# Architecture Decision Records

One short file per non-obvious decision, append-only. The module specification says
*what* was decided; the ADR says *why*.

| # | Decision |
|---|---|
| [0001](0001-sync-sqlalchemy-with-fastapi.md) | Synchronous SQLAlchemy behind FastAPI |
| [0002](0002-session-cookie-and-csrf.md) | Server-side sessions, cookie auth and double-submit CSRF |
| [0003](0003-varchar-check-over-postgres-enum.md) | `VARCHAR` + `CHECK` instead of Postgres `ENUM` |
| [0004](0004-signed-document-urls.md) | Signed, time-limited attachment URLs |
| [0005](0005-defer-transaction-fk.md) | LEGO purchase link kept as a column until the ledger exists |
| [0006](0006-caddy-serves-the-spa.md) | The web container *is* Caddy |
| [0007](0007-entity-is-not-a-security-boundary.md) | Entity is attribution, not permission |
| [0008](0008-lego-value-history-from-audit-log.md) | No valuation-history table for LEGO |
| [0009](0009-lego-evolution-is-an-acquisition-curve.md) | The LEGO evolution chart is an acquisition curve, not a price history |
| [0010](0010-lego-cost-roi-and-rrp-roi.md) | Two readings of value: cost ROI and RRP ROI, never merged |
| [0011](0011-first-run-setup-over-seeded-credentials.md) | First-run setup instead of seeded credentials |
| [0012](0012-lego-retirement-is-a-date.md) | LEGO retirement is a date, and it has to arrive |
| [0013](0013-lego-set-gallery.md) | The LEGO set gallery is worth a fourth table |
| [0014](0014-seed-creates-no-users.md) | The demo seed no longer creates users |
| [0015](0015-fs-articles-are-appended-not-flagged.md) | An Fs article is appended, never a printed line reclassified |
| [0016](0016-per-merchant-parsers-over-one-configurable-parser.md) | Per-merchant parsers over one configurable parser |
| [0017](0017-fiscal-qr-is-the-highest-confidence-anchor.md) | The fiscal QR is the highest-confidence anchor |
| [0018](0018-a-stage-that-did-not-run-is-not-a-stage-that-failed.md) | A stage that did not run is not a stage that failed |
| [0019](0019-the-product-catalogue-is-shared-not-entity-scoped.md) | The product catalogue is shared, not entity-scoped |
| [0020](0020-deepest-assigned-category-plus-maintained-ancestors.md) | Deepest assigned category, plus maintained ancestors |
| [0021](0021-the-legacy-sheet-is-validated-not-trusted.md) | The legacy sheet is validated, not trusted |
| [0022](0022-price-history-is-append-only-and-stores-no-quotient.md) | Price history is append-only and stores no quotient |
| [0023](0023-fs-observations-carry-the-notional-value-in-both-price-columns.md) | Fs observations carry the notional value in both price columns |
| [0024](0024-attachment-storage-is-group-owned.md) | The attachment volume is shared by two users, so it is group-owned |
| [0025](0025-one-review-queue-deep-linked-into-modules.md) | One Review Queue, deep-linked into the module that can resolve it |
| [0026](0026-carregar-is-an-action-not-a-place.md) | Carregar is an action, not a place |
| [0027](0027-real-invoices-are-seed-data.md) | The eleven real *talões* are seed data, not test fixtures |
| [0028](0028-line-grid-shows-category-not-merchant-section.md) | The line grid shows the category, not the merchant's section heading |
| [0029](0029-reference-data-ships-with-the-release.md) | Reference data ships with the release |
| [0030](0030-a-pack-format-is-matched-by-value-not-referenced.md) | A pack format is matched by value, not referenced |
| [0031](0031-the-review-grid-shows-the-price-per-kg-that-was-paid.md) | The review grid shows the €/kg that was paid |
| [0032](0032-the-lego-backup-keeps-its-primary-keys.md) | The LEGO backup keeps its primary keys |
| [0033](0033-line-confidence-is-scored-again-after-the-catalogue-answers.md) | A line's confidence is scored again after the catalogue answers |
| [0034](0034-reopening-a-confirmed-receipt.md) | Reopening a confirmed receipt, and what confirming costs |
| [0035](0035-confirming-a-category-is-a-statement-about-the-product.md) | Confirming a category is a statement about the product |
| [0036](0036-the-comparable-price-per-kg-is-before-the-loyalty-card.md) | The comparable €/kg is the one before the loyalty card (supersedes 0031) |
