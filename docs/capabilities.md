# Capabilities inventory

**What exists, where it lives, and which phase shipped it.** Per the orchestrator
brief §5a, this file — not any module specification — answers *"has this already been
built?"*. Check it before starting any module, and update it in the same change that
ships a feature.

Module specs deliberately do **not** name file paths or build order; that information
lives here, where it can be corrected when code moves.

---

## Shared core domain (brief §1a)

| Capability | Where | Shipped by |
| :--- | :--- | :--- |
| `Merchant` — global reference data, kinds, aliases, default categories | `apps/api/app/models/core.py` | Phase 0 |
| `Category` — 3-tier tree, `code_en` + `display_name_pt`, `brand_axis`, domain/level CHECK invariants | `apps/api/app/models/core.py` | Phase 0 |
| `Tag` — household-scoped labels | `apps/api/app/models/core.py` | Phase 0 |
| `Document` — SHA-256 content addressing, magic-byte validation, storage outside the web root | `apps/api/app/models/core.py`, `apps/api/app/services/documents.py` | Phase 0 |
| `Link` — polymorphic reconciliation edges, `RECEIPT_TRANSACTION` / `CLAIM_TRANSACTION` / … | `apps/api/app/models/core.py` | Phase 0 |
| `ReviewTask` — backs the shared Review Queue | `apps/api/app/models/core.py` | Phase 0 |
| `AuditLog` + `record()` / `snapshot()` helpers | `apps/api/app/models/core.py`, `apps/api/app/core/audit.py` | Phase 0 |
| `Setting` — scoped config; `confidence.auto_accept` (0.90), `confidence.review` (0.60) | `apps/api/app/services/settings_service.py` | Phase 0 |
| `ImportBatch`, `ProcessingJob` (unique `idempotency_key`) | `apps/api/app/models/core.py` | Phase 0 |

## Platform

| Capability | Where | Shipped by |
| :--- | :--- | :--- |
| Docker Compose stack — Postgres 16, Redis 7, API, Celery worker, Caddy+SPA | `docker-compose.yml`, `docker-compose.dev.yml` | Phase 0 |
| Task runners with engine auto-detection (`docker compose` / `podman-compose`) | `Makefile`, `fm` | Phase 0 |
| Alembic migrations; the API migrates on boot | `apps/api/alembic/`, `apps/api/docker-entrypoint.sh` | Phase 0 |
| Celery worker + `claim_job()` idempotency gate | `apps/api/app/worker.py` | Phase 0 |
| UUID v7 primary keys generated in Python | `apps/api/app/core/ids.py` | Phase 0 |
| Decimal EUR money helpers — `to_eur`, `eur_sum`, `roi_pct`, `appreciation_eur` | `apps/api/app/core/money.py` | Phase 0 |
| pt-PT formatting — EUR, dates, percentages, relative staleness | `apps/web/src/lib/format.ts` | Phase 0 |
| Fixed-window rate limiting (fails open) | `apps/api/app/core/ratelimit.py` | Phase 0 |
| Security headers middleware | `apps/api/app/main.py` | Phase 0 |
| Signed, time-limited document URLs (HMAC, 15 min) | `apps/api/app/core/security.py`, `apps/api/app/api/routers/documents.py` | Phase 0 |
| OpenAPI → TypeScript contract generation | `apps/api/app/openapi_export.py`, `apps/web/src/api/schema.d.ts` | Phase 0 |

## Identity, household and access (M7)

| Capability | Where | Shipped by |
| :--- | :--- | :--- |
| `User`, `Household`, `HouseholdMember`, `Entity`, `Session` | `apps/api/app/models/household.py` | Phase 0 |
| Argon2 login, Redis-cached server-side sessions, double-submit CSRF | `apps/api/app/services/auth.py` | Phase 0 |
| RBAC gates — `require_write`, `require_owner`, `resolve_write_entity` | `apps/api/app/api/deps.py` | Phase 0 |
| Member and entity management, last-OWNER safeguard, dependent profiles | `apps/api/app/services/household_service.py` | Phase 0 |
| Global entity selector, persisted per session and keyed into every query | `apps/web/src/components/entity-selector.tsx`, `apps/web/src/features/auth/session.tsx` | Phase 0 |

## Shared frontend layer

| Capability | Where | Shipped by |
| :--- | :--- | :--- |
| App shell — sidebar, nav, theme toggle, mobile drawer | `apps/web/src/components/app-shell.tsx` | Phase 0 |
| UI primitives — button, card, dialog/sheet, select, table, dropdown, tabs, slider, tooltip, popover | `apps/web/src/components/ui/` | Phase 0 |
| Generic **Review Queue** (Confirm / Fix / Dismiss) | `apps/api/app/api/routers/review.py`, `apps/web/src/routes/review.tsx` | Phase 0 |
| Shared **transaction picker** — proposes ledger lines near a date and amount | `apps/web/src/components/transaction-picker.tsx` | Phase 1 (M9) |
| URL-backed filter state feeding TanStack Query keys | `apps/web/src/lib/filters.ts` | Phase 1 (M9) |
| API client with CSRF handling and typed errors | `apps/web/src/lib/api.ts` | Phase 0 |

## Reference data surfaces

| Capability | Where | Shipped by |
| :--- | :--- | :--- |
| Merchant CRUD + Portuguese NIF checksum validation | `apps/api/app/api/routers/reference.py` | Phase 0 |
| Category read API (filter by domain, level, parent) | `apps/api/app/api/routers/reference.py` | Phase 0 |
| Tag CRUD | `apps/api/app/api/routers/reference.py` | Phase 0 |
| pt-PT grocery taxonomy seeded from the canonical JSON (27 L1 nodes) | `apps/api/app/seed/__init__.py` | Phase 0 |
| Portuguese merchant seed (Continente, Pingo Doce, Auchan, Galp, EDP, …) | `apps/api/app/seed/__init__.py` | Phase 0 |

## LEGO collection (M9)

| Capability | Where | Shipped by |
| :--- | :--- | :--- |
| `LegoSetModel`, `LegoSetInstance`, `StorageLocation` | `apps/api/app/models/lego.py` | Phase 1 |
| Collection overview, catalog grid, detail sheet, storage sheet | `apps/web/src/features/lego/` | Phase 1 |
| Brickset provider behind a `MetadataProvider` protocol, opt-in via `Setting` | `apps/api/app/services/lego_provider.py` | Phase 1 |
| Filtered summary, tri-state discovery filters, area-level storage filter, field+direction sort | `apps/api/app/services/lego_service.py` | Phase 1 (M9.1) |
| Derived RRP appreciation/ROI, cumulative acquisition timeline | `apps/api/app/services/lego_service.py` | Phase 1 (M9.1) |
| `GET /lego/export.xlsx` workbook export (copies, sets, storage) | `apps/api/app/services/lego_export.py` | Phase 1 (M9.1) |
| Exact `release_date` / `retirement_date`, with `is_retired` waiting for the date to pass | `apps/api/app/models/lego.py` | Phase 1 (M9.2) |
| Full catalog editing from the detail sheet («Editar conjunto» tab) | `apps/web/src/features/lego/detail-sheet.tsx` | Phase 1 (M9.2) |
| Collapsible two-level storage filter (areas, then containers) | `apps/web/src/features/lego/storage-filter.tsx` | Phase 1 (M9.2) |
| Real household inventory as seed data (93 sets, 97 copies) | `apps/api/app/seed/data/lego-inventory.json` | Phase 1 (M9.2) |

## First-run setup (M10)

| Capability | Where | Shipped by |
| :--- | :--- | :--- |
| `GET /setup/status`, `POST /setup` — the only unauthenticated write, one-shot | `apps/api/app/api/routers/setup.py` | Phase 1 (M10) |
| Household + first OWNER + entity + default settings bootstrap | `apps/api/app/services/setup_service.py` | Phase 1 (M10) |
| Setup screen chosen automatically when there is no session and no user | `apps/web/src/routes/setup.tsx` | Phase 1 (M10) |

---

## Not yet built

| Capability | Owning module |
| :--- | :--- |
| `Transaction` ledger, `CsvMapping`, statement import | M2 — Banking |
| `/api/transactions/suggest` currently answers `ledger_available: false` | M2 — Banking |
| Receipt ingestion, OCR, master products, price history | M1 — Supermarket |
| Health claims, utilities, vehicles, assets, dashboards | M3–M6, M8 |
| Playwright e2e tooling (`apps/web/tests/e2e/`) | first module that needs it |
