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
