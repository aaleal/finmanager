# Module 2 — Bank Statements & Transaction Ledger (`modules/banking`)

## Purpose
Import bank statements from Portuguese institutions (Millennium BCP, CGD, Santander, Novo Banco, Revolut, etc.), normalize them into the canonical `Transaction` ledger, auto-categorize on a 2-tier hierarchy, and reconcile with receipts, health claims, and utility bills. Detect recurring subscriptions, internal transfers, and statement gaps. Serve as the source-of-truth for household cash-flow analytics.

## Actors & User Stories
- *As a user*, I import a CSV export from my Portuguese bank; the system auto-detects the column format, maps fields, and saves the import profile for next time—no remapping needed.
- *As a reviewer*, I confirm high-confidence receipt↔transaction matches and fix miscategorized rows in a unified queue.
- *As an analyst*, I query spend by 2-tier category, by tag, and per entity; internal transfers don't pollute income/expense totals.
- *As a household member*, I see only my personal + joint/household transactions; others are hidden by RBAC.
- *As a maintainer*, I define categorization rules (e.g., "EDP → Electricity", regex patterns) and manage recurring charges.

## Data Model
All monetary fields (`_eur` suffix) are `NUMERIC(10,2)` decimal EUR amounts (e.g. `19.99`), never minor-unit integers; UI displays them pt-PT-formatted (e.g. `19,99€`).
- **BankAccount**: `id, entity_id, institution(MILLENNIUM_BCP|CGD|SANTANDER|NOVO_BANCO|REVOLUT|MANUAL|OTHER), short_code (e.g. AB, CR, REVO, MAN — the legacy “Source” code), name, iban, currency(EUR default), account_kind(CHECKING|SAVINGS|CREDIT|JOINT|MANUAL), opening_balance_eur, is_active, locale_format(pt_PT default)`.
- **Transaction** (canonical ledger, from D.3): `id, entity_id, account_id, booked_date (legacy “Date”, the accounting/analysis date), value_date (legacy “DateOriginal”, original movement date — may fall in a different year), amount_eur (signed), amount_net_eur (absolute magnitude, derived), currency, direction(DEBIT|CREDIT|NONE), description_raw, description_norm, merchant_id, category_l1_id, category_l2_id, category_nature(EXPENSE|INCOME|TRANSFER|OTHER|NA — legacy “Category_type”), bank_status(PENDING|BOOKED|REVERSED|CANCELLED), review_status(TODO|DONE|WARN — human validation state, distinct from bank_status), balance_after_eur, import_batch_id, split_group_fk (legacy “FK”, groups split/related rows), confidence, decision_reasons JSONB, notes (legacy “Comments”, free text), tags[], raw_payload JSONB`.
- **RecurringCharge**: `id, entity_id, merchant_id, description_pattern, expected_amount_eur, cadence(MONTHLY|QUARTERLY|ANNUAL|OTHER), last_detected_at, status(ACTIVE|PAUSED|ENDED), last_amount_variance_pct, alert_threshold_pct, created_by, tags[]`.
- **CsvMapping** (NEW): `id, bank_institution, name, column_map JSONB{date_idx, amount_idx, description_idx, balance_idx, ...}, delimiter(COMMA|SEMICOLON|TAB), decimal_sep(COMMA|PERIOD), date_format(DD/MM/YYYY, ISO_8601, ...), is_active`. Re-usable across imports.
- **TransferPair** (NEW, internal transfers): `id, from_transaction_id, to_transaction_id, paired_at, is_confirmed, created_by`. Prevents double-counting.
- **Rule** (NEW, auto-categorization): `id, entity_id, rule_type(KEYWORD|REGEX|MERCHANT_EXACT), pattern, category_l1_id, category_l2_id, priority, is_active`. Evaluated in order before merchant fallback.

## Functional Requirements
- **FR-2.1 Statement Ingestion & Format Detection.** Parse CSV (comma/semicolon/tab), OFX (1.x, 2.0), and structured PDF exports. Auto-detect column structure, decimal separator (comma-decimal for PT), date format (DD/MM/YYYY). Normalize `booked_date`/`value_date`.
- **FR-2.2 2-Tier Categorization.** Assign each transaction to `Category (L1→L2)`. Auto-suggest via (1) user-defined `Rule` engine (keyword/regex), (2) learned merchant→category mapping, (3) description similarity fallback. Confidence scored per signal.
- **FR-2.3 Reconciliation & Linking.** Suggest/confirm `Link` edges to receipts (M1), health claims (M3), utility bills (M4), vehicles (M5). Support 1:N and N:1. Match on date (±3 days configurable), amount (tolerance ±5% default), and merchant similarity.
- **FR-2.4 Contextual Tagging.** Apply multi-dimensional tags (`#vacation2026`, `#gifts`, `#daughter`) for cross-category aggregation; tags persist across linked entities.
- **FR-2.5 Recurring/Subscription Detection.** Identify recurring patterns by merchant and amount; alert when cadence shifts or amount deviates >threshold (default 10%). Maintain `RecurringCharge` records.
- **FR-2.6 Internal Transfer Detection (NEW).** Detect transfers between accounts in the same household via matching amount and opposite direction within 1 business day. Create `TransferPair`; exclude both from income/expense totals. Surface for confirmation.
- **FR-2.7 Balance Continuity & Statement Gaps (NEW).** Validate `balance_after` chains within a statement period. Alert on gaps. Store statement metadata: opening/closing balance, period start/end.
- **FR-2.8 Import Profile Persistence (NEW).** Save column mappings, delimiter, date format, merchant normalizations as reusable `CsvMapping` per institution; select a saved profile on re-import.

## Automation Rules (C.3 contract)
- **Categorization Engine**: Rules (keyword/regex) evaluated in priority order; unmatched fall to learned merchant mapping; low-confidence → review queue.
- **Reconciliation Engine**: Receipt↔transaction confidence combines date proximity (3-day window), amount tolerance (±5%), merchant similarity (≥0.80), OCR descriptor alignment. ≥0.85 auto-link; 0.60–0.85 → review; <0.60 flagged.
- **Internal Transfer Detector**: Two transactions in same household, opposite direction, same amount (within €1), booked_date within ±1 day → propose `TransferPair`. Confirmed pairs excluded from cash-flow aggregates.
- **Recurring Pattern**: On each new transaction, scan history for same merchant/normalized description. ≥2 prior occurrences with regular cadence (±3 days) → compute expected cadence/amount; deviation >threshold → alert + `RecurringCharge` state change.
- **Statement Validation**: After parsing, check sequential `balance_after` for consistency; flag gaps and prompt user.

## UI / Screens
- **Import Wizard**: upload → format auto-detect (CSV/OFX/PDF) → preview first 5 rows → column mapper (pre-populated from saved `CsvMapping`) → import confirmation + counts.
- **Ledger Grid** (TanStack Table): filterable/sortable by date, merchant, amount, category, entity, tags; inline category/tag edit; Pending/Booked badges; reconciliation status indicator.
- **Reconciliation Review Board**: split pane transaction ↔ suggested matches with confidence; bulk actions; manual link; approval persists `Link` and advances linked-entity workflow state.
- **Recurring Charges Dashboard**: detected subscriptions (merchant, cadence, amount, last-seen, variance %); alert badge on threshold breach.
- **Statement Summary**: per import, opening/closing balance, period, count, cash-flow in/out, top categories, gaps/anomalies.
- **Rule Manager**: CRUD keyword/regex rules; drag to reorder priority; test on sample transactions before save.

## API Surface
- `POST /accounts` · `GET /accounts` · `GET /accounts/{id}` · `PATCH /accounts/{id}` · `DELETE /accounts/{id}` (soft).
- `POST /transactions/import` (multipart: file + optional mapping_id, idempotent via Idempotency-Key) → `{ batch_id, counts, warnings[] }`.
- `GET /transactions` (rich filters, pagination) · `GET /transactions/{id}` · `PATCH /transactions/{id}` · `POST /transactions/{id}/links`.
- `GET /recurring-charges` · `PATCH /recurring-charges/{id}`.
- `GET/POST /import-profiles` · `DELETE /import-profiles/{id}`.
- `CRUD /categorization-rules`.
- `POST /transactions/detect-transfers`.
- `GET /accounts/{id}/statement-summary`.

## Analytics & KPIs
- Cash-flow: monthly income/expense by L1 category, net savings rate, trend.
- Category spend: L1→L2 over time, vs budget (if defined).
- Tag rollups: aggregate by tag.
- Subscription spend: total monthly recurring, breakout by merchant, variance alerts.
- Uncategorized backlog: count of `category_l1_id IS NULL`, oldest first.
- Reconciliation rate: % linked to M1/M3/M4, by month.
- Balance health: opening vs closing per statement, unexplained gaps.
- Entity cash-flow: personal vs joint vs household net savings.

## Edge Cases & Validation
- **Mixed-currency purchases (card abroad)**: store both original currency and EUR-converted amount (statement rate); flag FX markup >2%.
- **Duplicate re-import safety**: dedupe key `hash(account_id, booked_date, amount_eur, description_norm)`; existing row → skip and log "already present".
- **Reversed/cancelled**: status tracks `PENDING → BOOKED`/`REVERSED`; reversals link back via `raw_payload.ref_transaction_id`.
- **Split transactions**: one bank row linked to multiple receipts via multiple `Link(type=RECONCILES)`.
- **Portuguese comma-decimal (1.234,56)**: parser auto-detects via `CsvMapping.decimal_sep`; normalizes to a decimal EUR amount (e.g. `1234.56`), never minor units.
- **MB WAY / Multibanco references**: extract from description into `raw_payload.payment_method`; use for merchant/category hints.
- **Statement gaps**: flag in `ImportBatch` with gap range; user re-imports or confirms "not available".
- **Pending state changes**: allow `PENDING → BOOKED` without creating a duplicate.

## Additional / Enriched Requirements
1. **Portuguese Bank Format Support (NEW)**: codify CSV/OFX parsers for Millennium BCP, CGD, Santander, Novo Banco, Revolut (comma-decimal dates, accents, MB WAY identifiers); seed as `CsvMapping` templates.
2. **IBAN Validation (NEW)**: validate Portuguese IBAN (PT + 24 digits); mask all but last 4 in UI.
3. **Internal Transfer Pair Semantics (NEW)**: TransferPair as "zero-net-flow" for household; exclude from household income/expense; include in personal ledger only where the user is payer/payee.
4. **Rule Engine Extensibility (NEW)**: user-ordered priority; `OR` logic for multiple keywords; test UI to preview matches on history.
5. **Statement Metadata Capture (NEW)**: per-batch opening/closing balances; "verified with bank statement" flag + timestamp.
6. **Anomaly Alerting (NEW)**: subscription amount change >threshold, recurring cadence gap, spend spike vs rolling-3-month average → Alert Engine.

## Open Questions / Decisions
1. **Auto-link confidence threshold**: default 0.85; configurable per household/user.
2. **Internal transfer window**: default ±1 business day; consider 2–3 days for inter-bank delays.
3. **Recurring cadence tolerance**: default ±3 days; longer for annual charges.
4. **Statement gap handling**: auto-flag only (do not auto-reject).
5. **FX rates for multi-currency**: prefer statement-provided rate; historical lookup opt-in (privacy).

## Definition of Done
- CSV/OFX parsers handle Portuguese bank formats; tests with anonymized seed examples.
- 2-tier categorization confidence ≥0.80 on sample; learns from confirmed corrections.
- Receipt↔transaction reconciliation ≥0.60 suggested; ≥0.85 auto-links (with confirmation option).
- Internal transfer detection excludes paired transfers from household cash-flow; tested.
- `CsvMapping` persistence; re-import uses saved profile.
- Rule engine prioritized; test UI; unit tests for evaluation order.
- Balance continuity validation; gaps detected & flagged; unit tests.
- Recurring detection; alerts on >10% variance; lifecycle tested.
- Ledger grid supports entity filtering, reconciliation status, inline edit.
- Reconciliation review board with bulk actions.
- Analytics: cash-flow, category spend, tag rollups, subscription spend, uncategorized backlog, reconciliation rate.
- API idempotent on re-import; RFC 9457 errors.
- ≥80% auto-process on sample; ≥80% coverage; pt-PT dates/decimal/currency on all UI.

## Integration Contract
- **Exposes**: canonical `Transaction` ledger (D.3, shared source of truth); `Link` reconciliation edges to M1/M3/M4/M5; `RecurringCharge`; cash-flow aggregates for M6 and dashboards; entity-scoped transaction feeds.
- **Consumes**: `Merchant`, `Category` (L1→L2), `Tag`, `Entity`; `ImportBatch`, `ProcessingJob`, `ReviewTask`, `AuditLog`, `Document`; receipts/claims/bills/vehicles as link targets.
- **Triggers**: Reconciliation Engine, Alert Engine (anomalies/gaps/backlog), Analytics Engine.

## Source-of-Truth Mapping (legacy Excel → model)
The household's current `Extratos_YYYY` sheets (~5,000 rows across 2024–2026) are the migration source. This mapping is authoritative for the CSV/legacy import path; every legacy column must round-trip.

| Legacy column | Model target | Notes |
|---|---|---|
| `Date` | `Transaction.booked_date` | The accounting/analysis date (drives period rollups). |
| `DateOriginal` | `Transaction.value_date` | Original movement date; may be a **different year** than `Date` (cross-year re-accounting) — keep both, never collapse. |
| `Date_Format`, `Year`, `Month`, `Date_ID`, `Date_text` | *derived* | Do **not** store; compute (`YYYYMMDD`, `YYYY_MM`, month name) in queries/views. |
| `Identity` (`Andre`, `Daniela`, `Andre_Daniela`, `Carolina`) | `Entity` | `Andre_Daniela` → a **JOINT** entity; `Carolina` → a dependent's INDIVIDUAL entity (no login). Confirms the M7 attribution model. |
| `Source` (`AB`, `CR`, `REVO`, `MAN`) | `BankAccount.short_code` / `institution` | `MAN` → `institution=MANUAL` (hand-entered, no statement). |
| `Description` | `Transaction.description_raw` (+ normalized `description_norm`) | |
| `Amount` | `Transaction.amount_eur` | Signed; negative = OUT/expense, positive = IN. |
| `Amount_net` | `Transaction.amount_net_eur` | Absolute magnitude; **derived**, never treated as a balance. |
| `Category_1` / `Category_2` | `category_l1_id` / `category_l2_id` | 2-tier hierarchy (banking). |
| `Category_type` (`Despesas`/`Entrada`/`Outros`/`N/A`) | `Transaction.category_nature` | EXPENSE / INCOME / OTHER / NA. |
| `type` (`IN`/`OUT`/`N/A`) | `Transaction.direction` | CREDIT / DEBIT / NONE (derived from sign). |
| `Status` (`DONE`/`TODO`/`WARN`) | `Transaction.review_status` | Human validation state — `TODO`→Review Queue, `WARN`→flagged/anomaly. Distinct from `bank_status`. |
| `Comments` | `Transaction.notes` | Free text; may encode manual rules — preserve verbatim. |
| `Category_Aux` | `Tag` | Event/context tag (e.g. a named trip). |
| `Split` | `Link(SPLIT_OF)` / `payer_split` | Split-movement info. |
| `Is_Prendas` | seed `Tag` `#prendas` | Recurring analytical flag (gifts). |
| `Is_Puericultura` | seed `Tag` `#puericultura` | Recurring analytical flag (childcare/child). |
| `FK` | `Transaction.split_group_fk` | Cross-reference key grouping split/related rows. |

**Aux sheet** (controlled vocabularies: identities, sources, statuses, C1, and per-C1 C2 lists) seeds `Entity`, `BankAccount`, `Category` (L1→L2) and the review-status lookup — import it as the canonical starting vocabulary.
