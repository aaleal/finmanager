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
| Attachment storage shared by the root and non-root containers — setgid, group-writable shards; entrypoint reconciles the volume then drops privileges | `apps/api/app/services/documents.py`, `apps/api/docker-entrypoint.sh`, `apps/api/Dockerfile` | M1 fixes (ADR-0024) |
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
| Generic **Review Queue** (Confirm / Dismiss, cross-module, deep-links into the owning module) | `apps/api/app/api/routers/review.py`, `apps/web/src/components/review-queue.tsx`, `apps/web/src/routes/review.tsx` | Phase 0, wired up in M1 fixes (ADR-0025) |
| Shared **transaction picker** — proposes ledger lines near a date and amount | `apps/web/src/components/transaction-picker.tsx` | Phase 1 (M9) |
| URL-backed filter state feeding TanStack Query keys | `apps/web/src/lib/filters.ts` | Phase 1 (M9) |
| API client with CSRF handling and typed errors | `apps/web/src/lib/api.ts` | Phase 0 |

## Reference data surfaces

| Capability | Where | Shipped by |
| :--- | :--- | :--- |
| Merchant CRUD + Portuguese NIF checksum validation | `apps/api/app/api/routers/reference.py` | Phase 0 |
| Category read API (filter by domain, level, parent) | `apps/api/app/api/routers/reference.py` | Phase 0 |
| Tag CRUD | `apps/api/app/api/routers/reference.py` | Phase 0 |
| pt-PT grocery taxonomy shipped with the release and ensured at every boot (27 L1 nodes) | `apps/api/app/services/reference_data.py`, `apps/api/app/data/supermarket-categories.pt-PT.json` | Phase 0, moved out of the seed (ADR-0029) |
| Portuguese merchants (Continente, Pingo Doce, Auchan, Galp, EDP, …) ensured at every boot | `apps/api/app/services/reference_data.py` | Phase 0, moved out of the seed (ADR-0029) |
| Merchant NIFs (Continente, Pingo Doce, Lidl, Piquete da Fruta) and the five parser profiles ensured at every boot | `apps/api/app/services/reference_data.py`, `apps/api/app/main.py::lifespan` | Phase 3 (M1a), moved out of the seed (ADR-0029) |

## LEGO collection (M9)

| Capability | Where | Shipped by |
| :--- | :--- | :--- |
| `LegoSetModel`, `LegoSetInstance`, `StorageLocation` | `apps/api/app/models/lego.py` | Phase 1 |
| Collection overview, catalog grid, detail sheet, storage sheet | `apps/web/src/features/lego/` | Phase 1 |
| Brickset provider behind a `MetadataProvider` protocol, opt-in via `Setting` | `apps/api/app/services/lego_provider.py` | Phase 1 |
| A bare set number tries the closed-pack `-0` variant before the ordinary `-1` (an explicit suffix is never second-guessed) — ADR-0050 | `apps/api/app/services/lego_provider.py::_set_number_candidates` | Phase 1 |
| Filtered summary, tri-state discovery filters, area-level storage filter, field+direction sort | `apps/api/app/services/lego_service.py` | Phase 1 (M9.1) |
| Derived RRP appreciation/ROI, cumulative acquisition timeline | `apps/api/app/services/lego_service.py` | Phase 1 (M9.1) |
| `GET /lego/export.xlsx` workbook export (copies, sets, storage) | `apps/api/app/services/lego_export.py` | Phase 1 (M9.1) |
| Exact `release_date` / `retirement_date`, with `is_retired` waiting for the date to pass | `apps/api/app/models/lego.py` | Phase 1 (M9.2) |
| Full catalog editing from the detail sheet («Editar conjunto» tab) | `apps/web/src/features/lego/detail-sheet.tsx` | Phase 1 (M9.2) |
| Collapsible two-level storage filter (areas, then containers) | `apps/web/src/features/lego/storage-filter.tsx` | Phase 1 (M9.2) |
| Real household inventory as seed data (93 sets, 97 copies) | `apps/api/app/seed/data/lego-inventory.json` | Phase 1 (M9.2) |
| Sort on every grid column, incl. derived `copies` and `roi`, ordinal `condition` | `apps/api/app/services/lego_service.py` | Phase 1 (M9.3) |
| Set image gallery + carousel (box shot plus extra views) | `apps/api/app/models/lego.py`, `apps/web/src/features/lego/set-carousel.tsx` | Phase 1 (M9.3) |
| Gallery editor on the summary tab — append-only order, a star marks the set's cover, capped at one row with a "+N" overflow tile (ADR-0045) | `apps/web/src/features/lego/detail-sheet.tsx::GalleryEditor` | Phase 1 (M9.4) |
| Per-copy table image picked from the set's own images, falling back to the set's cover (ADR-0045) | `apps/api/app/services/lego_service.py::set_instance_display_image`, `apps/web/src/features/lego/detail-sheet.tsx::DisplayImagePicker` | Phase 1 (M9.4) |
| Real Brickset box art downloaded once into the seed | `apps/api/app/seed/__init__.py` | Phase 1 (M9.3) |
| Set dates read from the set's own `launchDate` / `exitDate`, and the RRP only from the euro store (ADR-0039) | `apps/api/app/services/lego_provider.py` | Phase 1 (M9.4) |
| Recommended age range and box dimensions (`age_min`/`age_max`, `box_*`), looked up and hand-editable | `apps/api/app/models/lego.py`, `apps/web/src/features/lego/detail-sheet.tsx` | Phase 1 (M9.4) |
| `POST /lego/models/{id}/brickset` — one press downloads `getAdditionalImages` into the gallery and `getInstructions2` (PT/EN + language-neutral) into `lego_set_instructions`, all stored locally and carried by the backup (ADR-0040). Runs automatically once, from set creation, never again from the sheet (ADR-0044) | `apps/api/app/services/lego_service.py::import_from_brickset`, `apps/api/app/services/lego_backup.py` | Phase 1 (M9.4) |
| `POST /lego/models/{id}/instructions` — add a manual by hand (file or URL), same storage and dedupe rules as the Brickset import (ADR-0044) | `apps/api/app/services/lego_service.py::add_model_instruction` | Phase 1 (M9.4) |
| `DateInput` — every date in the application is typed `dd/mm/aaaa` over an ISO value, because the native picker follows the browser's locale (ADR-0041) | `apps/web/src/components/ui/input.tsx` | Phase 1 (M9.4) |
| Manual import dedupes by description before downloading, not by file content (ADR-0043) | `apps/api/app/services/lego_service.py::_import_instructions` | Phase 1 (M9.4) |
| Bulk import of copies from a spreadsheet — preview resolves entity/storage/enum columns only (no Brickset call), a review table lets errors be fixed inline, commit does one find-or-create-and-Brickset-lookup per row; reads the same PT column headers `export.xlsx` writes, so the export is itself a valid import (ADR-0048); the sheet's own "PVP original (€)" backfills `rrp_eur` only when Brickset itself left it empty (ADR-0052) | `apps/api/app/services/lego_bulk_import.py`, `apps/web/src/features/lego/bulk-import-dialog.tsx` | Phase 1 (M9.5) |
| Bulk import of storage locations — upserted on (área, contentor), so re-importing the exported «Arrumação» sheet is safe (ADR-0048) | `apps/api/app/services/lego_bulk_import.py::import_storage_locations`, `apps/web/src/features/lego/storage-bulk-import-dialog.tsx` | Phase 1 (M9.5) |

## Settings & backup (Definições)

| Capability | Where | Shipped by |
| :--- | :--- | :--- |
| Provider toggles (Brickset), confidence thresholds, password change | `apps/api/app/api/routers/settings.py`, `apps/web/src/routes/settings.tsx` | Phase 0 / Phase 1 |
| `BRICKSET_API_KEY` in the environment switches Brickset on by itself on a fresh install, once, from the boot `lifespan` hook — never overrides a later choice made in Definições (ADR-0038) | `apps/api/app/services/settings_service.py::ensure_brickset_from_env`, `apps/api/app/main.py::lifespan` | Phase 1 |
| Per-module backup registry — one archive per module, plus a global export bundling every module's own archive unmodified (ADR-0037, LEGO's own rules per ADR-0032) | `apps/api/app/services/backup_service.py`, `apps/api/app/services/lego_backup.py` | Phase 1 |
| `GET /settings/backup/modules`, `GET /settings/backup.zip?module=`, `POST /settings/backup` — restore auto-detects a single-module or a global archive from its manifest | `apps/api/app/api/routers/settings.py` | Phase 1 |

## Supermarket & receipts (M1)

| Capability | Where | Shipped by |
| :--- | :--- | :--- |
| `SupermarketReceipt`, `SupermarketReceiptItem`, `MerchantParserProfile` | `apps/api/app/models/supermarket.py` | Phase 3 (M1a) |
| Ingestion pipeline — detect merchant, select profile, extract, normalize, resolve product (seam), reconcile, score | `apps/api/app/services/supermarket/pipeline.py` | Phase 3 (M1a) |
| `ExtractionProvider` / `OcrProvider` seams — `pdfplumber` word boxes, `pytesseract`, PDF-page OCR fallback | `apps/api/app/services/supermarket/extraction.py` | Phase 3 (M1a) |
| Five merchant parsers behind a registry — `continente_v1`, `pingodoce_v1`, `lidl_v1`, `piquete_v1`, `generic_v1` | `apps/api/app/services/supermarket/parsers/` | Phase 3 (M1a) |
| Confidence engine — pure `(status, confidence, decision_reasons)`, unavailable stages redistribute weight rather than scoring zero | `apps/api/app/services/supermarket/confidence.py` | Phase 3 (M1a) |
| Fiscal QR / ATCUD reader — `pyzbar` decode, printed-ATCUD fallback, NIF checksum and merchant-vs-buyer disambiguation | `apps/api/app/services/supermarket/fiscal.py` | Phase 3 (M1a) |
| Merchant resolution — NIF → profile → fuzzy-name (`rapidfuzz`) | `apps/api/app/services/supermarket/merchants.py` | Phase 3 (M1a) |
| Fs valuation and the three €/kg variants (PVP, promo-adjusted, final) | `apps/api/app/services/supermarket/arithmetic.py` | Phase 3 (M1a) |
| Receipt status machine — `UPLOADED → PARSING → AUTO_ACCEPTED/NEEDS_REVIEW → CONFIRMED → VOID`, with `FAILED` retry and `CONFIRMED → NEEDS_REVIEW` reopen | `apps/api/app/models/supermarket.py`, `POST /api/supermarket/{id}/reopen` | Phase 3 (M1a) |
| `/api/supermarket`, `/api/supermarket-items`, `/api/parser-profiles` | `apps/api/app/api/routers/supermarket.py` | Phase 3 (M1a) |
| Parsing queue and batch upload (Carregar, Fila) | `apps/web/src/features/supermarket/upload-panel.tsx`, `queue-table.tsx` | Phase 3 (M1a) |
| Upload as a button + modal on the invoice list, with a parser-profile override carried into `SupermarketReceipt.parser_profile_id` | `apps/web/src/features/supermarket/upload-panel.tsx::ReceiptUploadDialog`, `POST /api/supermarket?parser_profile_id=` | M1 fixes (ADR-0026) |
| «Processamento» — the processing queue, explicitly not a review queue; reusable compactly inside the upload modal | `apps/web/src/features/supermarket/queue-table.tsx` | M1 fixes (ADR-0025) |
| Review split-pane — document alongside extracted fields, «Porquê?» reasons | `apps/web/src/features/supermarket/review-pane.tsx`, `why-popover.tsx` | Phase 3 (M1a) |
| Full-screen review split pane with a zoomable document column, URL-addressable (`?tab=faturas&receipt=`) | `apps/web/src/features/supermarket/review-pane.tsx`, `apps/web/src/components/ui/dialog.tsx::FullscreenContent` | M1 fixes (UX-1.2) |
| Line grid — `L1 › L2 › L3` category column, weights in g or kg, integer quantity (`—` when sold by weight) | `apps/web/src/features/supermarket/{review-pane,items-table}.tsx`, `apps/web/src/lib/format.ts` | M1 fixes (ADR-0028) |
| Create a `MasterProduct` inline, from the review pane or the catalogue | `apps/web/src/features/supermarket/product-create-dialog.tsx` | M1 fixes (FR-1.2) |
| Estado status board — totals, queue depth, failures, auto-accept rate | `apps/web/src/features/supermarket/status-panel.tsx` | Phase 3 (M1a) |
| Supermercado tile on the Painel (despesa registada + n.º de faturas) | `apps/api/app/api/routers/dashboard.py` | Phase 3 |
| Faturas — receipts list | `apps/web/src/features/supermarket/receipts-table.tsx` | Phase 3 (M1a) |
| Faturas — parser-profile column and an `impressos/Fs` article count (`5/2`) | `apps/web/src/features/supermarket/receipts-table.tsx` | M1 fixes (UX-1.3) |
| Artigos — line-level item explorer across every invoice | `apps/web/src/features/supermarket/items-table.tsx` | Phase 3 (M1a) |
| Artigos — «Resumo por produto»: units, weight, spend and a **weight-weighted** €/kg per product, drilling down into the individual purchases | `GET /api/supermarket-items/summary`, `apps/web/src/features/supermarket/product-summary-table.tsx` | M1 fixes |
| Pack formats as a curated vocabulary — unique weights per product, matched to a line **by value at the gram**, idempotent append (ADR-0030) | `apps/api/app/services/supermarket/products_service.py::sanitize_pack_variants`, `POST /api/master-products/{id}/pack-variants` | M1 fixes (ADR-0030) |
| Manual alias entry beside the learned ones — same call the review pane makes on a correction | `POST /api/product-aliases/learn`, `apps/web/src/features/supermarket/products-panel.tsx::AddAliasForm` | M1 fixes |
| Hand-added invoice lines and hand-removed ones, with an editable `line_no` that orders the grid | `POST /api/supermarket/{id}/items` (`is_fs=false`), `DELETE /api/supermarket/{id}/items/{item_id}` | M1 fixes |
| Confidence shown as its two signals (leitura / produto) with the formula behind it | `apps/web/src/features/supermarket/{review-pane,why-popover}.tsx` | M1 fixes |
| Perfis de leitura — parser-profile administration | `apps/web/src/features/supermarket/parser-profiles-panel.tsx` | Phase 3 (M1a) |
| Golden extraction fixtures — committed word boxes for all eleven real *talões* | `apps/api/tests/fixtures/golden/` | Phase 3 (M1a) |
| The eleven real *talões* as seed data, ingested through the upload path so each has a `Document` and stays reprocessable | `apps/api/app/seed/data/invoices/`, `apps/api/app/seed/__init__.py::seed_supermarket_invoices` | M1 fixes (ADR-0027) |
| `MasterProduct` / `ProductAlias` — canonical product identity and learned merchant vocabulary | `apps/api/app/models/products.py` | Phase 3 (M1b) |
| Product resolution and the alias learning loop — alias-exact → fuzzy ≥ 0.78 (review band 0.70–0.78), `learn()` correction loop, `CatalogueResolver` registered as the pipeline's `ProductResolver` | `apps/api/app/services/supermarket/catalogue.py` | Phase 3 (M1b) |
| Local category classifier — `VocabularyClassifier` over the pt-PT L3 vocabulary, fed by description and `merchant_section`; `register_classifier()` seam for a remote one | `apps/api/app/services/supermarket/classify.py` | Phase 3 (M1b) |
| Category administration — rename, reparent, merge, retire, each with impact counts | `apps/api/app/api/routers/products.py`, `apps/api/app/services/supermarket/products_service.py` | Phase 3 (M1b) |
| Whole-tree endpoint for the taxonomy editor | `GET /api/categories/tree` | Phase 3 (M1b) |
| Product merge and merge-candidate detection | `apps/api/app/services/supermarket/products_service.py` | Phase 3 (M1b) |
| Master product manager UI («Produtos» tab) | `apps/web/src/features/supermarket/products-panel.tsx` | Phase 3 (M1b) |
| Taxonomy editor UI («Categorias» tab) | `apps/web/src/features/supermarket/categories-panel.tsx` | Phase 3 (M1b) |
| Product and category autocomplete pickers | `apps/web/src/features/supermarket/product-picker.tsx`, `category-picker.tsx` | Phase 3 (M1b) |
| Legacy spreadsheet importer — the `SUPERMARKET_YYYY` migration («Importar folha» tab) | `apps/api/app/services/supermarket/legacy_import.py`, `apps/web/src/features/supermarket/legacy-import-panel.tsx` | Phase 3 (M1b) |
| `confirm-categories` and line-level product reassignment | `POST /api/supermarket/{id}/confirm-categories`, `PATCH /api/supermarket-items/{id}/product`, `apps/web/src/features/supermarket/review-pane.tsx` | Phase 3 (M1b) |
| Confirmation is refused while any line is unresolved — an unresolved line would be dropped from the price history in silence | `apps/web/src/features/supermarket/review-pane.tsx`, `ReceiptDerived.is_complete` | M1 fixes |
| `ProductPriceHistory` — append-only price observation, frozen on parse-time decision and again on confirm | `apps/api/app/models/prices.py` | Phase 3 (M1c) |
| Append-only observation recording — `record_observations()`, idempotent on unchanged date/prices/weight, a correction appends rather than rewrites | `apps/api/app/services/supermarket/prices_service.py` | Phase 3 (M1c) |
| Derived last-known price — pre-fills manual entry and Fs valuation, never stored | `apps/api/app/services/supermarket/prices_service.py::last_known_price` | Phase 3 (M1c) |
| €/kg list and paid trends, filterable by `fs` (`all`/`only`/`exclude`) | `apps/api/app/services/supermarket/prices_service.py::price_history` | Phase 3 (M1c) |
| Shrinkflation detection — `margin_signal` over a rolling 365-day window, ≥ 3 prior observations, fires at ≤ −0.05 | `apps/api/app/services/supermarket/prices_service.py::shrinkflation` | Phase 3 (M1c) |
| Category spend over both measures (`paid_eur`/`notional_eur`), outer-joined so an unresolved line still counts under «Sem categoria» | `apps/api/app/services/supermarket/prices_service.py::category_spend` | Phase 3 (M1c) |
| Loyalty `GROUP BY` view and per-receipt allocation | `apps/api/app/services/supermarket/prices_service.py::loyalty_summary`, `apps/api/app/api/routers/prices.py` | Phase 3 (M1c) |
| Receipt↔transaction `Link` behind a `LedgerProvider` seam, `AbsentLedger` the honest placeholder | `apps/api/app/services/supermarket/ledger.py` | Phase 3 (M1c) |
| Receipt and item tagging | `PUT /api/supermarket/{id}/tags`, `PUT /api/supermarket/{id}/items/{itemId}/tags` | Phase 3 (M1c) |
| Price-history, spend and loyalty endpoints, plus CSV export of a price series | `apps/api/app/api/routers/prices.py` | Phase 3 (M1c) |
| Price-evolution, spend and loyalty UI panels («Preços», «Despesa», «Fidelização» tabs) | `apps/web/src/features/supermarket/{price-evolution-panel,spend-panel,loyalty-panel}.tsx` | Phase 3 (M1c) |
| Receipt link panel and `fs` tri-state filter in the review pane | `apps/web/src/features/supermarket/link-panel.tsx`, `apps/web/src/features/supermarket/review-pane.tsx` | Phase 3 (M1c) |
| Demo supermarket receipt in the seed — `seed_supermarket()`, one reconciling receipt carrying an appended Fs article, a prorated loyalty discount, a refund and a deposit return together | `apps/api/app/seed/__init__.py` | Phase 3 (M1c) |
| Legacy importer now records a price observation for every imported group (2,386 observations from the real 2025 sheet) | `apps/api/app/services/supermarket/legacy_import.py` | Phase 3 (M1b) |

## Household administration (M7)

| Capability | Where | Shipped by |
| :--- | :--- | :--- |
| Entity colour picker, rename and membership editing | `apps/web/src/routes/household.tsx` | Phase 1 (M9.3) |
| Owner sets a member's password; `./fm passwd` does it from the host | `apps/api/app/reset_password.py` | Phase 1 (M10) |

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
| `receipts` already writes `Link(RECEIPT_TRANSACTION)` edges through `register_provider()` (`apps/api/app/services/supermarket/ledger.py`) — only the real `LedgerProvider` is missing | M2 — Banking |
| Health claims, utilities, vehicles, assets, dashboards | M3–M6, M8 |
| Playwright e2e tooling (`apps/web/tests/e2e/`) | first module that needs it |
