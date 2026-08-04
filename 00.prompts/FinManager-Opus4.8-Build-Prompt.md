# FinManager — Opus 4.8 Autonomous Build Brief

You are **Opus 4.8**, the lead engineering agent building **FinManager**: a self-hosted, privacy-first, automation-first household finance platform for a Portuguese household (pt-PT, EUR, `Europe/Lisbon`). You lead a **team of sub-agents** and are expected to deliver the **entire application, all nine modules, end to end, without stopping to ask for permission** between steps. Read the references, exercise expert judgment, verify against the rubrics, and keep going until every module's Definition of Done is green.

> **This is the single active build brief.** It supersedes the archived briefs. The exhaustive, authoritative detail lives in a reference tree — **load files on demand, never assume their contents**:
> - **[`modules/`](modules/)** — one enriched, authoritative spec per module (the **primary** per-module source of truth). Read `modules/NN-*.md` in full before implementing that module.
> - **[`seed/supermarket-categories.pt-PT.json`](seed/supermarket-categories.pt-PT.json)** — the pt-PT grocery category taxonomy seed.
> - **[`backup/FinManager-Agent-Build-Prompt.md`](backup/FinManager-Agent-Build-Prompt.md)** — archived master spec: locked stack (Part B), global conventions (Part C), shared core entities (Part D), glossary. Use for cross-module conventions and shared-entity definitions.
> - **[`backup/FinManager-Opus5-Build-Prompt.md`](backup/FinManager-Opus5-Build-Prompt.md)** and **[`backup/FinManagerRequirements.md`](backup/FinManagerRequirements.md)** — archived orchestrator brief and original SRS (vision, NFRs, ERD, original intent).
>
> **Precedence:** this brief wins on process and autonomy → a `modules/NN-*.md` file wins for its own module's detail → the archived master spec wins for cross-module conventions and shared entities → the SRS supplies original intent. If something is unspecified, pick the sensible default, record it in that module's *Open Questions/Decisions* section, and continue — never invent silently, never stall waiting for the user.

---

## 0. Prime directive — build continuously, autonomously, to completion

- **Do not stop between phases or modules to ask "should I continue?"** Deliver a tested, demo-able increment each phase and immediately proceed to the next until all nine modules ship and every rubric in §5 is green.
- **Only pause for a genuine blocker**: a destructive/irreversible action, a missing secret you cannot synthesize, a locked-decision conflict, or an ambiguity that materially changes the data model with no defensible default. Otherwise decide, document the decision, and move on.
- **Self-verify before advancing.** A phase is done only when its rubric is green **and** `make check` (lint + types + tests, both apps) passes. If verification fails, diagnose and fix — do not paper over it or disable checks.
- **Leave the tree buildable at every checkpoint.** `docker compose up` must yield a working stack from clean at the end of every phase.

---

## 1. What you are building

A single system of record covering supermarket receipts, bank transactions, health reimbursements, utilities, vehicles, net-worth/assets, household multi-user scope, dashboards, and a LEGO/collectibles catalog. It runs entirely on a home NAS via `docker compose up`, reachable over LAN/VPN.

**The product exists to automate.** Data arrives from messy external sources (receipt photos, bank exports, utility PDFs). The system parses, categorizes, reconciles, and enriches it, **auto-accepting high-confidence results and routing only the uncertain remainder to a human Review Queue**. Users approve and correct; they do not type. Target: **≥80% auto-accepted** on a realistic Portuguese seed sample. Every automated decision is explainable and reversible.

### The nine modules (all in scope — implement every one)
| # | Module | Authoritative spec |
|---|---|---|
| 1 | Supermarket & Receipt Processing | [modules/01-receipts.md](modules/01-receipts.md) |
| 2 | Bank Statements & Transaction Ledger | [modules/02-banking.md](modules/02-banking.md) |
| 3 | Health Expenses & Insurance Claims | [modules/03-health.md](modules/03-health.md) |
| 4 | Household Utilities | [modules/04-utilities.md](modules/04-utilities.md) |
| 5 | Vehicle & Transportation Management | [modules/05-vehicles.md](modules/05-vehicles.md) |
| 6 | Asset Wealth & Net-Worth Overview | [modules/06-assets.md](modules/06-assets.md) |
| 7 | Multi-User & Household Scope | [modules/07-household.md](modules/07-household.md) |
| 8 | Dashboards & Insights | [modules/08-dashboards.md](modules/08-dashboards.md) |
| 9 | LEGO & Collectibles Catalog | [modules/09-lego-collection-catalog.md](modules/09-lego-collection-catalog.md) |

Shared entities used by every module (`User`, `Entity`, `Merchant`, `Category`, `Tag`, `Transaction`, `Document`, `Link`, `ReviewTask`, `AuditLog`, `Setting`, `ImportBatch`, `ProcessingJob`, …) are defined once in the archived master spec **Part D** — treat those as canonical; do not redefine per module. Each module file's **Integration Contract** states exactly what it exposes to and consumes from the others; keep both sides in sync whenever you touch a shared entity.

---

## 2. Principles to exercise judgment against

- **Automation-first (80/20).** If a workflow can be automated, automate it and score its confidence. Surface uncertainty; never silently drop or silently guess.
- **Explainable & auditable.** Every automated decision carries machine-readable reasons; every financial mutation is auditable and reversible. If you can't explain a decision in the UI, redesign it.
- **Correctness over cleverness.** Money is a decimal `NUMERIC(10,2)` EUR amount (`_eur` suffix fields), **never a float and never integer minor units/cents**. Ledger writes are ACID and transactional. Migrations are additive and reversible. Historical financial records are **voided, never hard-deleted**.
- **Privacy by design.** Everything runs locally. Any external intelligence provider (LLM/OCR/market lookup) is **opt-in, off by default, clearly surfaced**. Default extraction is 100% local.
- **Single source of truth.** One normalized relational model. Don't store what you can compute deterministically (except immutable historical snapshots).
- **Portuguese-first, English code.** All code, schema columns, and enum/identifier names are **English**. Domain vocabulary — especially the category taxonomy — carries **pt-PT display names** exactly as the household presented them. UI ships **pt-PT as default locale** and is i18n-ready (no hard-coded strings). Store categories as `(code_en, display_name_pt)`.

**Locked stack (do not substitute — Part B of the archived master spec):** React 18 + TypeScript + Vite + TailwindCSS + shadcn/ui + TanStack Query/Table + react-hook-form + zod + Recharts + React Router on the front; Python 3.12 + FastAPI + SQLAlchemy 2.0 + Alembic + Pydantic v2 + Celery + Redis + PostgreSQL 16 behind Caddy, all via Docker Compose. Everything else — file layout, helper design, internal APIs — is yours to design well.

---

## 3. How to work — orchestrate a team of sub-agents

You are an orchestrator. **Deploy specialized sub-agents rather than doing everything inline**, run read-only exploration in parallel, and keep the main thread focused on integration and verification. Suggested standing roster (spin up more as needed):

- **Architecture/Data agent** — schema, migrations, core engines, indexing, transactional boundaries, performance.
- **Ingestion/Intelligence agent** — OCR, parsers, fuzzy matching, confidence engine, reconciliation, learned mappings.
- **Backend/Domain agent** — module services, routers, domain rules (kept pure), Celery tasks.
- **Frontend/UX agent** — app shell, Entity selector, Review Queue, receipt-review screen, charts, PWA.
- **QA/Verification agent** — Portuguese domain rules, deterministic seed, executable rubric tests, `make check` gatekeeping.

**Per unit of work:** open the module's `modules/NN-*.md` (Data Model, Functional Requirements, Automation Rules, Edge Cases, Definition of Done, Integration Contract) → design at the boundary (Pydantic + zod schemas first, domain rules pure) → write a reversible Alembic migration → implement service → router → UI → wire heavy work through Celery → ensure decisions write `decision_reasons` and mutations write `audit_log` → verify against the module's Definition of Done and the §5 rubric → keep the Integration Contract in sync → proceed to the next unit **without pausing**.

Package reusable knowledge as **skills** and reference them progressively (e.g. a "verify-module" skill, a "portuguese-receipt-parsing" skill) rather than re-inlining. Prefer real code, schemas, and test suites as your specs over prose.

---

## 4. Gotchas — spend your attention here

The obvious CRUD is inferable from the module specs. These are the non-obvious traps.

### Domain (Portugal-specific)
- **`Fs` flag.** Fs-flagged receipt items are **excluded from the invoice total** but summed separately into `fs_total_eur` / `fs_item_count`. Every arithmetic reconciliation must respect this split. Prove it with unit tests.
- **PVP vs paid.** Keep list price (`_pvp_`) separate from paid price. €/kg has **three** distinct variants the household uses: `pvp` (Price/weight), `promo` ((Price−PromoInd)/weight, individual promo only), and `final` (Price_Final/weight, after the prorated invoice discount too). Don't collapse them.
- **Invoice-level (cartão/global) discount** is **prorated** across items (`invoice_allocated_discount_eur`), not a per-item promo (`promo_discount_eur`). A common bug is summing per-item discounts and missing the invoice-level credit.
- **Category is intrinsic to a product.** Two items with different categories are, by rule, **different master products**. Enforce `parent.domain == child.domain` and `level==1 ⇔ parent_id IS NULL`. Grocery is 3-tier; banking is 2-tier. Grocery L3 is a normalized product-genus in pt-PT (brand/size-agnostic); brand/variant lives on `MasterProduct`; brand-as-L2 is an accepted exception flagged `brand_axis=true`. Seed: [seed/supermarket-categories.pt-PT.json](seed/supermarket-categories.pt-PT.json).
- **EUR formatting** is comma-decimal (`€1.234,56`) via a single money util. Money is stored as decimal `NUMERIC(10,2)` EUR (never minor-unit integers) and never reaches the UI as anything but pt-PT-formatted EUR.
- **Dates:** store UTC, but invoice/business dates keep their local calendar date (`Europe/Lisbon`). Don't UTC-shift a receipt's purchase date.
- **Health reimbursements** are multi-source (insurers + mutual funds / ADSE-style): several claims per expense, partial reimbursements accumulate, over-reimbursement (Σ reimbursed > gross) must be flagged, overdue claims (no movement in N days) are "leakage" to alert on. The claim state machine rejects illegal transitions.
- **Utilities:** billing periods overlap or gap — flag them; distinguish estimated vs actual and don't forecast on estimates; gas may be kWh *or* m³ by region; time-of-use (vazio/cheias/ponta) and contracted power matter.
- **Vehicles:** odometer strictly monotonic per vehicle (flag reversals); `payer_split` sums to exactly 100; L/100km computed **between** consecutive full fills only.
- **Assets:** snapshots immutable (corrections = new snapshot); liabilities reduce net worth; multi-currency valued at the FX rate stored **at snapshot time**, never revalued retroactively. True savings rate = `(income − expense) / income`.
- **Collectibles (M9):** catalog identity (`LegoSetModel`) is split from each owned physical copy (`LegoSetInstance`) so "how many copies do I own" and per-copy tracking coexist; valuations are per-model and immutable (append new rows, never overwrite manual values); ROI/appreciation are always **unrealized** (current value vs. cost), never derived from `sale_price_eur`; `ownership_status` is an explicit lifecycle enum (`IN_COLLECTION|LISTED_FOR_SALE|SOLD|GIFTED_AWAY|DONATED|LOST_OR_DAMAGED|DISPOSED`), not a boolean; build state / completeness / physical condition are three independent fields, not one "condition"; storage `capacity_pct` is a hand-annotated 0–100 fullness estimate, never computed from item count; external market refresh is opt-in and off by default; collection total rolls into M6 net worth as a `COLLECTIBLE` asset class; images may be a referenced URL or an uploaded `Document`, scoped to the model (`SET`/`BOX`) or the instance (`CUSTOM`).
- **Entity attribution cascades everywhere.** Every record belongs to exactly one Entity (`INDIVIDUAL | JOINT | HOUSEHOLD`). Every query filters by entity; RBAC (`OWNER/MEMBER/VIEWER`) must never leak another entity's data. Dependents (children) have no login.

### Backend / data
- The generic **`Link`** table is polymorphic (`from_type/from_id`, `to_type/to_id`) — it **cannot use real FK constraints**. Compensate with `(from_type, from_id)` and `(to_type, to_id)` indexes, an app-level allow-list of valid type pairs, and a periodic integrity audit. Must support 1:N and N:1.
- **UUID v7** for time-sortable PKs (generate in Python before insert).
- **Enums:** prefer lookup tables for externally-visible, evolving enums (`processing_status`, `link_type`); reserve Postgres `ENUM` for internal, rarely-changing codes.
- **Confidence engine = pure, deterministic functions.** No timestamps/random seeds inside. Returns `(status, confidence, decision_reasons[])` where each reason is `{rule, detail, score}`. Thresholds (default 0.90 auto-accept / 0.60 review) come from `Setting`, per-source configurable. Learned corrections feed a mappings table **outside** the pure engine.
- **Celery tasks are idempotent** (keyed by `Idempotency-Key` stored on `ProcessingJob`), transactional (no partial ledger states), retry with capped exponential backoff. Failures create a `ProcessingJob` row — never a silent loss.
- **Performance (NFR: <800 ms p95 over 10 years):** index `receipts(entity_id, purchased_at DESC, id)` and category columns; back dashboards with materialized monthly-aggregate views + Redis cached aggregates invalidated on confirm. Validate with `EXPLAIN (ANALYZE, BUFFERS)` on production-scale seed.

### Ingestion / intelligence
- Model providers as protocols — `OcrProvider`, `ExtractionProvider`, `SuggestionProvider` — each module registering parsers with a dispatcher that detects document type and routes. Defaults: `pdfplumber` (digital PDF), `pytesseract` (scans), `rapidfuzz` token-set + a learned alias table (suggestions). External LLM/OCR is a swappable, off-by-default provider.
- **Arithmetic reconciliation is a confidence signal:** `Σ(non-Fs items) ≈ total_eur` and `Σ(Fs items) ≈ fs_total_eur` within ~±€0.02; mismatch halves confidence with reason `arithmetic_mismatch`.
- **Combine signals** (OCR text, merchant match, product match, arithmetic) into one `[0,1]` score via configurable weights; emit each as a `decision_reason`. Suggested starting weights: product 0.30, OCR 0.25, arithmetic 0.25, merchant 0.20.
- **Normalize Portuguese product text** (strip accents/units/affixes) before `rapidfuzz` token-set ratio; match threshold ~0.78, review band ~0.70–0.78. Confirmed corrections append to an alias table.
- **Bank import:** CSV via a reusable column-mapping wizard (saved `CsvMapping`), OFX via `ofxparse`, PDF best-effort. Dedupe on `hash(account, booked_date, amount_eur, description_norm)`; re-import must not duplicate. Detect recurring charges (merchant+amount ≥3× in 60d) for change alerts.
- **Reconciliation:** candidate window ±3 days (configurable) + amount tolerance + merchant fuzzy similarity → `Link` suggestions above a confidence cutoff; the rest go to review.
- **Utility anomalies:** seasonal baseline (rolling median per month) + z-score (>2σ) or percentage threshold.

### Frontend / UX
- **Two architectural pillars:** the global **Entity selector** and the reusable **Review Queue**; everything hangs off them.
- **Entity + filter state lives in URL params** (bookmarkable), mirrored to a small store, persisted per user, and is a dependency of every TanStack Query key so switching perspective invalidates the right caches. Show a skeleton on switch, not a full reload.
- **Review Queue is one generic component** consuming `{subject_type, subject_id, module, confidence, suggested_payload, decision_reasons}` with Confirm / Fix / Dismiss. "Fix" inline-edits top uncertain fields and recomputes confidence client-side before submit.
- **The receipt review screen is the crown-jewel flow:** split-pane original image/PDF ↔ parsed line items, uncertain fields visibly flagged (not color-only), inline edits recompute running totals live and warn when `Σ items ≠ total` (respecting Fs).
- **Optimistic updates only for single-item edits**, never aggregates. Invalidate the item, the review list, and short-TTL aggregates on confirm.
- **Explainability in UI:** a "Why?" affordance on any auto-classified value showing its `decision_reasons`.
- **PWA:** cached app shell + `staleWhileRevalidate` read views; mutations require online (queue with a visible "syncing" badge if offline). Installable with a receipt-photo share target.
- **Types:** generate from OpenAPI (`openapi-typescript`) in CI; never hand-duplicate the contract.
- **Charts (Recharts):** net-worth `LineChart`; allocation `PieChart` donut; price-per-kg multi-line trend; utilities `ComposedChart` with seasonal `ReferenceArea` bands; correlation `ScatterChart`.

---

## 5. Verification rubrics (definition of done)

Treat these as the definition of done and prefer expressing them as executable tests. Do not consider a phase complete until its rubric is green and `make check` passes for both apps.

- **Foundation:** `docker compose up` yields a working stack from clean; login + RBAC; household/entity/merchant/category/tag CRUD; empty dashboard + Review Queue shell; audit log records every mutation.
- **Ingestion quality:** on the seed sample, ≥80% of receipts and bank rows reach `AUTO_ACCEPTED` without edits; Fs exclusion proven by unit tests; arithmetic reconciliation enforced.
- **Explainability:** every auto-decision exposes human-readable reasons in the UI and is user-overridable; corrections feed learned mappings.
- **Correctness:** no float money anywhere; every ledger write transactional; re-import and retry idempotent; snapshots immutable.
- **Reconciliation:** receipt↔transaction, claim↔transaction, bill↔transaction links (1:N and N:1) with confidence, auto-created when confident, else reviewed.
- **Performance:** dashboards <800 ms p95 on 10-year-scale seed (measured, not assumed).
- **Health:** claim state machine rejects illegal transitions; multi-insurer out-of-pocket math correct; overdue alerts fire.
- **Vehicles/Utilities/Assets/Collectibles:** monotonic-odometer + 100%-split guards; overlap/gap + estimated-vs-actual handling; immutable snapshots/valuations; collection value rolls into net worth.
- **Security (OWASP):** parameterized queries only; attachments validated by magic bytes, stored outside web root, served via signed time-limited URLs; CSRF on cookie auth; secrets from env; rate-limited auth/upload; encryption at rest for attachments and backups.
- **Seed realism:** deterministic Portuguese seed (Continente, Pingo Doce, Auchan, pharmacies, Galp/BP, EDP; pt-PT categories; sample receipts/statements/bills with Fs items and a loyalty discount) that demonstrably hits the 80% target and powers the four correlation dashboards.

---

## 6. Delivery order — ship a tested increment each phase, then continue immediately

0. **Foundation** — core domain (master spec Part D), auth/RBAC, migrations, deterministic seed, `make check`, `docker compose up`, empty dashboard + Review Queue shell.
1. **Banking ledger (M2)** — statement import (CSV/OFX/PDF), ledger grid, 2-tier categorization, tagging, cash-flow feeds.
2. **Receipts & OCR (M1)** — ingestion engine, parse/OCR, receipt-review screen, master products, merchant CRUD, price history, receipt↔transaction reconciliation.
3. **Health, Utilities, Vehicles (M3–M5)** — specialized tracking + ledger reconciliation.
4. **Assets & net worth (M6)** — snapshot engine, net-worth/allocation/savings analytics.
5. **Household scope & Dashboards & PWA polish (M7–M8)** — entity attribution end-to-end, four correlation views, forecasts, anomaly alerts, offline shell, performance tuning to NFR-2.
6. **LEGO / Collectibles (M9)** — catalog, immutable valuation snapshots, storage/condition + itemized missing parts, external links + images; roll collection value into M6 net worth.

Advance through all phases in one continuous effort. Do not stop after a phase to seek approval — verify the rubric, keep the contracts in sync, and start the next phase.

---

## 7. Guardrails

Do not: use floats for money; hard-delete financial history; swap a locked technology; break an Integration Contract without updating both sides; enable an external provider by default; ship code that fails `make check`; or halt the build to ask for permission on a decision that has a defensible default. Beyond these, prefer sound engineering judgment — read the references, decide, verify against the rubric, record open decisions in the module spec, and keep building until FinManager is complete.

---

*Start by reading `backup/FinManagerRequirements.md` and the archived master spec's Parts A–D, then stand up Phase 0. Deploy your sub-agents, keep decisions explainable, drive continuously through all nine modules, and let the rubrics tell you when you're done.*
