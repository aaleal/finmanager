# Module 6 — Asset Wealth & Portfolio Overview (`modules/assets`)

## Purpose
Capture immutable, multi-currency financial snapshots across all household assets and liabilities; compute true savings rate and net-worth trajectory; and provide per-entity attribution views. This module is the household's "net-worth scorecard," answering: *How much are we worth? Where is the money? How fast are we building wealth? What portion is earned vs. market-driven?*

## Actors & User Stories
- *As a household head*, I review my net-worth dashboard monthly; see allocation across accounts/investments/real estate; and identify where savings are growing fastest.
- *As an investor*, I link my brokerage holdings (units × unit price) and see real-estate valuations update alongside liquid accounts; I distinguish contribution from market-driven gains.
- *As a planner*, I run FIRE/coast-FIRE projections: given my current savings rate, how long until financial independence?
- *As a reviewer*, I validate annual snapshots (pulling live account balances) and correct outliers due to temporary market swings.
- *As a privacy advocate*, I control whether optional price refresh (stocks, crypto, forex) is enabled; it defaults **off**.

## Data Model
All monetary fields (`_eur` suffix) are `NUMERIC(10,2)` decimal EUR amounts (e.g. `19.99`), never minor-unit integers; UI displays them pt-PT-formatted (e.g. `19,99€`).
- **Asset**: `id, entity_id, name, asset_class(CHECKING|SAVINGS|INVESTMENT|REAL_ESTATE|VEHICLE|CRYPTO|FOREX|LIABILITY), currency, iban_masked?, ticker?, description, is_deleted, linked_account_id?`.
- **AssetSnapshot** (immutable, append-only): `id, asset_id, as_of_date, value_eur, fx_rate_to_eur NUMERIC(10,6), source(MANUAL|DERIVED|LINKED_ACCOUNT_AUTO_SYNC), snapshot_batch_id, created_at`. Every correction is a new row.
- **CashFlowPeriod** (derived from M2): `id, entity_id, period_start, period_end, income_eur, expense_eur, net_savings_eur, savings_rate NUMERIC(4,3)`. Savings rate = `(income − expense)/income`.
- **FxRate** (historical, immutable): `id, from_currency, to_currency, rate NUMERIC(10,6), as_of_date, source(MANUAL|PROVIDER|HISTORICAL_ECB)`.
- **Holding** (investments): `id, asset_id, ticker, quantity NUMERIC(14,8), unit_value_eur NUMERIC(18,6) (finer precision for crypto/forex sub-cent prices), last_updated_at`. Price refresh optional, off by default.
- **Liability** (or asset_class=LIABILITY): `id, entity_id, name, principal_eur, interest_rate_annual, term_months, issue_date, currency, creditor_merchant_id, status(ACTIVE|PAID_OFF), description`.
- **LiabilityAmortization** (derived, append-only): `id, liability_id, period_start, period_end, principal_paid_eur, interest_paid_eur, remaining_balance_eur`.
- **SnapshotBatch**: `id, entity_id, period, status, executed_at, note`.

## Functional Requirements
- **FR-6.1 Periodic Snapshot Scheduling.** Celery Beat (configurable cadence) fetches balances from linked accounts (M2) and creates AssetSnapshot rows. Non-linked assets manual or bulk import. High-confidence auto-accepted; manual → review.
- **FR-6.2 Inflow/Outflow & True Savings Rate.** Consume `Transaction` ledger per entity/period; compute income (credit tagged income/salary/bonus/transfer_in), expense (rest), net savings, savings rate; handle zero/negative income. Store in `CashFlowPeriod`.
- **FR-6.3 Net-Worth Analytics.** Aggregate active assets by entity/date: net-worth = Σ(asset snapshots) − Σ(liability balances). Time-series (1yr/5yr/all-time); allocation pie by class; entity filters.
- **FR-6.4 Multi-Currency Consolidation.** Foreign snapshots store `fx_rate_to_eur` at snapshot date; EUR default with original-currency drill-down.
- **FR-6.5 Investment Holding Valuation.** `Holding` links asset↔ticker; `value_eur = quantity × unit_value_eur`. Optional price refresh (opt-in) is logged, **never** auto-updates holdings.
- **FR-6.6 Liability Principal & Interest Decomposition.** Auto-compute amortization; monthly snapshots record principal vs interest; display liabilities as negative net worth; paydown as separate trend.
- **FR-6.7 Real-Estate Manual Valuation.** REAL_ESTATE assets allow periodic manual valuation; track history; surface cadastral reference + last appraisal date.
- **FR-6.8 Crypto & Forex Spot Holdings.** CRYPTO/FOREX store quantity + spot value; optional refresh if enabled. Privacy default off.
- **FR-6.9 Correction & Audit Trail.** Snapshots immutable; corrections spawn new `source=MANUAL` snapshot + reason; AuditLog records each. UI shows history + reasons.
- **FR-6.10 Savings Goal Tracking.** Optional target net-worth + timeline; dashboard overlays progress; projects forward on current rate.
- **FR-6.11 FIRE / Coast-FIRE Projections.** From net-worth, savings rate, assumed real return (default 5%), compute years to FI (25× spend or target); coast scenario supported.
- **FR-6.12 Account-to-Asset Linking.** Link `BankAccount` (M2) to `Asset` so snapshots auto-derive; idempotent; no future dating.
- **FR-6.13 Contribution vs. Market Attribution.** Store `contributed_eur`; `market_gain_eur = value − contributed`; dashboard shows earned vs market growth.

## Automation Rules
1. **Scheduled Snapshots** (Celery Beat): daily 02:00 UTC for linked accounts; manual for others; on error → ProcessingJob + alert.
2. **FX Rate Refresh**: daily 09:00 UTC; 6-month historical for EUR/USD, EUR/GBP, EUR/CHF, EUR/JPY (ECB or open source).
3. **Amortization Auto-Compute**: on liability create/edit, compute term schedule; monthly snapshots derive balance.
4. **Cash Flow Derivation**: daily recompute of prior-month `CashFlowPeriod` (idempotent) from confirmed M2 transactions.
5. **Anomaly Alert**: net-worth drops >15% in a month without explainable spike → review.
6. **Price Refresh (Opt-In, Off by Default)**: weekly task fetches latest prices for INVESTMENT/CRYPTO; results **logged only**, never auto-update; non-blocking on failure.

## UI / Screens
1. **Net-Worth Dashboard**: line chart (YTD + all-time); current total; YoY %; allocation pie; savings rate, contribution vs gain, months to FI.
2. **Asset Manager**: list w/ latest value; add/edit/delete; link account; price-refresh opt-in; real-estate appraisal upload.
3. **Snapshot History**: timeline per asset; prior values + edit reasons; manual entry.
4. **Allocation Donut**: drill-down; compare vs target allocation.
5. **Savings Rate Trend**: 12-month line; target overlay; highlight below-target months.
6. **Liability Dashboard**: remaining balance, interest paid YTD, payoff date, amortization detail.
7. **Projection Panel**: FIRE timeline, coast-FIRE scenarios; sliders for return and retirement spend.
8. **Entity Selector**: any single entity, or "todas" (global, persistent).

## API Surface
`POST/GET/PATCH /assets` · `GET/POST /assets/{id}/snapshots` · `GET /assets/net-worth?entity_id=&as_of_date=` · `GET /cashflow?entity_id=&period=` · `POST /assets/{id}/correct-snapshot` · `CRUD /liabilities` · `GET /liabilities/{id}/amortization` · `CRUD /holdings` · `POST /holdings/{id}/refresh-price` (opt-in, non-blocking) · `GET /analytics/projection`.

## Analytics & KPIs
- Net-worth over time (multi-year line).
- Asset allocation (pie by class; donut by account).
- True savings rate (`(income − expense)/income`, monthly + YTD).
- Contribution vs market gain (stacked bar).
- Liability paydown (waterfall: principal/interest/remaining).
- YoY net-worth growth (%, CAGR).
- Months to FIRE.
- Real-estate appreciation (€ and % per property).
- Cash-flow sustainability (months of expenses in liquid reserves).

## Edge Cases & Validation
1. **Snapshot immutability**: only latest per (asset, date) corrected; priors read-only; corrections spawn rows + reason.
2. **Liabilities reduce net worth**: `Σ(assets) − Σ(liability.remaining_balance)`.
3. **Multi-currency**: each snapshot stores `fx_rate_to_eur`; EUR sum + optional original-currency display.
4. **Linked account idempotency**: as-of-date check prevents duplicates; balance change → new snapshot.
5. **Negative snapshots**: overdrafts valid; treated as liabilities.
6. **Zero/negative income**: savings rate null / `N/A`; no division by zero.
7. **Future dates rejected**: snapshots ≤ today.
8. **Stale price data**: >7 days old → UI warning; value not silently degraded.
9. **Correction reasoning**: every manual snapshot has a `note`; audit surfaces it.

## Additional / Enriched Requirements
- **Investment Holdings with Quantity Valuation**: security-granular tracking without live feeds; optional refresh non-destructive (logged only), off by default.
- **Liability Amortization & Interest Attribution**: term/rate → amortization tables; principal vs interest split; "true cost of debt".
- **Real-Estate Valuation Audit Trail**: appraisal dates, cadastral references, manual valuations; multi-property.
- **Crypto & Forex Micro-Holdings**: quantity + unit price; privacy-respecting optional feeds.
- **Savings Goal & FIRE Projections**: target net-worth + retirement date; interactive scenarios (5%/7%/10% real return).
- **Contribution Attribution**: cumulative contributions per asset; market gain = value − contributed.
- **Entity-Scoped Net-Worth**: filter net worth to a single entity or view the whole household; filtering at query time, not a permission check.
- **Real Return Assumption (Configurable)**: default 5%; sensitivity analysis.
- **Annual Snapshot Validation Ritual**: yearly review prompt to confirm/correct holdings.

## Open Questions / Decisions
1. **Price refresh provider?** → *ECB (forex) + Alpha Vantage free tier default; premium optional.*
2. **FIRE target formula?** → *Default 25× annual spend, override option.*
3. **Crypto holdings tracking?** → *Manual entry only (privacy); optional Koinly-style import if opt-in.*
4. **Liability interest compounding?** → *Monthly.*
5. **Snapshot confidence threshold?** → *First 3 months manual → review; then auto-accept if consistent.*
6. **Forex rounding?** → *Store all EUR amounts as `NUMERIC(10,2)` (never minor-unit integers); original-currency amount stored alongside `fx_rate_to_eur` for drill-down, presented with currency-specific decimals.*

## Definition of Done
- [ ] Asset + Liability CRUD (all fields).
- [ ] AssetSnapshot immutability; correction spawns new rows.
- [ ] Scheduled snapshot engine (Celery Beat) daily linked accounts.
- [ ] FxRate populated daily (ECB, 6-month history); snapshot lookup works.
- [ ] CashFlowPeriod nightly from M2; savings-rate formula unit-tested.
- [ ] Net-worth aggregation: ≥10 entities × 5 years in <200ms.
- [ ] Liability amortization auto-computed; monthly snapshots match (±0.01€).
- [ ] Holding valuation tested.
- [ ] FIRE/coast-FIRE logic unit-tested.
- [ ] UI dashboard renders (net-worth line, allocation pie, savings trend, FIRE timeline).
- [ ] Price refresh (opt-in, off default) logs without modifying holdings.
- [ ] Entity filtering tested (single entity vs. whole household totals).
- [ ] Audit log for every snapshot create/correct.
- [ ] E2E: create asset → 3 snapshots → correct latest → verify history + audit.

## Integration Contract
- **Exposes**: net-worth series (`GET /assets/net-worth`) + cash-flow (`GET /cashflow`) for Dashboards; `Asset`/`AssetSnapshot` as link targets for Banking (M2); liability balances as negative contributors.
- **Consumes**: `Transaction` cash-flow (M2), `BankAccount` (M2) for auto-sync, `Entity` (household scope), `FxRate`, `Merchant` (creditors), and `Document` (appraisal attachments).
