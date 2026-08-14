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
