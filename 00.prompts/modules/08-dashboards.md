# Module 8 — Dashboards & Insights (cross-cutting) (`modules/dashboards`)

## Purpose
Provide real-time and historical financial visibility across the household by aggregating data from all modules into interactive, shareable views. Empower users to detect trends, anomalies, budget deviations, and savings opportunities without query complexity. Enable drill-through from summary cards to source transactions and explainable decisions.

## Actors & User Stories
- *As a household owner*, I see a unified overview of net worth, monthly cash flow, top spending categories, and savings rate at a glance; I can drill down to individual purchases or accounts.
- *As a budget steward*, I set per-category spending limits, receive instant deviation alerts, and compare actual vs. budget by month/year.
- *As an analyst*, I investigate correlations (e.g., utility consumption vs. cost anomalies, supermarket spend vs. bank groceries category).
- *As a forecaster*, I view predicted cash flow and spending trends (moving-average, linear regression) to plan ahead.
- *As a member*, I see only my attributed expenses/assets while switching to a family view when needed.
- *As a reviewer*, I access a Review Queue widget consolidating all pending confirmations across modules in one location.

## Data Model
Read-only analytics artifacts (never part of ledger state). Monetary fields (`_eur` suffix) are `NUMERIC(10,2)` decimal EUR amounts (e.g. `19.99`), never minor-unit integers; UI displays them pt-PT-formatted (e.g. `19,99€`).
- **SavedView**: `id, entity_id, name, filter_preset{dateRange, tags, categories, entity}, chart_config[], is_shared`.
- **Budget**: `id, entity_id, category_id, period(MONTHLY|YEARLY), amount_eur, fiscal_year_month, status(ACTIVE|ARCHIVED)`.
- **BudgetDeviation** (derived): `id, budget_id, period, actual_eur, variance_eur, variance_pct, status(OK|WARNING|EXCEEDED)`.
- **Alert** (unified): `id, entity_id, type(BUDGET_EXCEEDED|ANOMALY|PENDING_REVIEW|REIMBURSEMENT_PENDING|SUBSCRIPTION_CHANGED), module, subject_id, message, severity, created_at, dismissed_at, is_actionable`.
- **ForecastCache** (materialized): `id, entity_id, metric(MONTHLY_SPEND|NET_INCOME|CATEGORY_SPEND), period, forecasted_value_eur, method(MOVING_AVG|LINEAR), confidence, computed_at`.
- **CorrelationView** (computed): `id, entity_id, metric_x, metric_y, periods[], correlation_coefficient, trend, last_computed_at`.

## Dashboards & Views
**Global Filter Bar (sticky, shared)**: entity selector (personal/joint/household) · date range · tag multi-select · category drill. All charts re-render reactively.

**Household Overview Dashboard**: net-worth trend (line, YTD highlight) · cash-flow (inflow/outflow stacked bar, current + rolling 12mo) · top categories (horizontal bar, sortable) · savings rate % (card + trend arrow) · budget status snapshot (% consumed, top 3 at-risk).

**Per-Module Drilldowns** (unified navigation): Supermarket (L1/L2/L3 breakdown, €/kg evolution, Fs excluded, merchant comparison) · Banking (ledger grid, recurring charges + change alerts, low-confidence backlog) · Health (claims kanban, out-of-pocket trend, reimbursement rate, overdue claims) · Utilities (consumption per meter normalized, cost anomalies) · Vehicles (L/100km, cost-per-km, per-member split, maintenance) · Assets (allocation donut, per-asset trend, liability paydown).

**Four Required Correlation Views**:
1. **Supermarket Spend ↔ Bank Groceries Category** (scatter + trendline): X = Σ ReceiptItems (non-Fs) by category, Y = bank `Groceries` transactions; highlights matches/mismatches.
2. **Health Out-of-Pocket ↔ Reimbursements** (stacked bar + cumulative line): out-of-pocket cumulative vs reimbursement rate %; reveals subsidy lag.
3. **Utility Cost ↔ Consumption** (dual-axis line): cost € vs kWh/m³; detects cost/volume divergence (rate hike).
4. **Household Income ↔ Total Expenses** (waterfall): inflow → outflow → net savings; monthly/annual.

**Additional Insights Panels**: Subscription Creep (recurring charges trending up) · Price Drift (products with €/kg increases) · Savings Opportunities (underutilized budgets) · Forecast Projections ("If current spend continues, you exceed <category> by €X on <date>").

## Functional Requirements
- **FR-D.1 Overview Widget Rendering.** Overview cards (net worth, cash flow, savings rate, budget status) with responsive typography + color status (green/yellow/red); values locale-formatted (pt-PT, EUR 2 decimals).
- **FR-D.2 Per-Module Drilldowns.** Each module exposes a read-only dashboard sharing the global filter bar; drill-through supported.
- **FR-D.3 Correlation View Computation & Caching.** Compute four correlations daily via Celery Beat; cache in Redis with TTL; recompute on expiry; <100ms from cache.
- **FR-D.4 Simple Forecasts.** Moving-average (default 6mo, configurable) + linear-regression on key metrics; store in `ForecastCache` with method + confidence; refresh on new confirmed data.
- **FR-D.5 Budget Management.** CRUD budgets per category/entity/period; actual vs budget; deviation alerts bubbled to Alert center.
- **FR-D.6 Alert Center.** Unified feed of anomalies/pending actions/deviations across modules; filter by type/severity/module; dismiss/snooze/act.
- **FR-D.7 Review Queue Widget.** Top 5 pending items (any module's `ReviewTask`); "View All" expands; count badge.
- **FR-D.8 SavedView Bookmarks.** Create/load/share filter+chart presets; export as link.
- **FR-D.9 Export & Reporting.** CSV/JSON/PDF export; in-app digest (weekly/monthly) as a saved view.
- **FR-D.10 Comparative Periods.** MoM and YoY overlays; highlight deltas + % change.
- **FR-D.11 Drill-Through Navigation.** Aggregate → filtered list → detail → source document, with breadcrumb.
- **FR-D.12 What-If Forecasting.** Adjust assumptions and re-run; non-persisted exploratory.
- **FR-D.13 Goal Progress Widget.** Track user-defined goals; current progress, runway, monthly-target burn.

## Automation Rules
- `ForecastCache` invalidated per metric/entity when a `ReviewTask` is confirmed (fine-grained, not full recompute).
- `BudgetDeviation` auto-created daily; thresholds (80%, 100%, 110%) trigger `Alert`s.
- Subscription Creep detection weekly: `RecurringCharge` amount change > threshold (5%) → `Alert type=SUBSCRIPTION_CHANGED`.
- Anomaly detection (utilities consumption >2σ, bank recurring change) feeds alerts.
- `CorrelationView` computed nightly with caching; expiry recomputes on access.

## UI / Screens
- **Main Dashboard**: overview cards, quick filters, four correlation mini-charts, top categories, budget status; responsive single-column mobile.
- **Module Drilldown Pages**: shared filter bar, module grids/charts, detail modals, breadcrumb.
- **Alert Center**: reverse-chrono feed, type/severity filters, dismiss/snooze/action, link to source.
- **Budget Manager**: table (category, period, amount, actual, variance, status), inline edit, templates.
- **SavedView Library**: dashboard thumbnails, create, share/export, auto-saved recent state.
- **Forecast Explorer**: historical + projected trend, adjust assumptions, see runway/deviation impact.

## API Surface
- `GET /dashboards/overview` → `{netWorth, cashFlow, savingsRate, budgetStatus, topCategories}`.
- `GET /dashboards/correlations/{view}` (SUPERMARKET_GROCERIES | HEALTH_OOP_REIMBURSE | UTILITY_COST_CONSUMPTION | INCOME_EXPENSES) → `{points[], correlationCoefficient, trendline, periods}`.
- `POST /dashboards/forecasts/{metric}` → `{forecasted[], confidence, nextRefresh}`.
- `GET /dashboards/alerts` (type, severity, module, sort, pagination) → `{data[], nextCursor}`.
- `CRUD /budgets` · `CRUD /saved-views`.
- `POST /dashboards/export` → signed URL or inline CSV.
- `GET /dashboards/drilldown/{module}`.

## Analytics & KPIs
- Net worth (Σ assets − Σ liabilities, trending).
- Monthly cash flow (inflow − outflow, excl. investments).
- Top categories (rank by L1, YoY).
- Savings rate ((net income − expenses)/net income %).
- Subscription creep (Σ recurring, % YoY).
- Price drift (products €/kg increase > threshold).
- Reimbursement rate (Σ reimbursed / Σ gross medical %).
- Utility anomalies (consumption/cost spikes).
- Budget variance ((actual − budgeted)/budgeted %).
- Forecast accuracy (MAPE, lagging KPI).

## Performance
Target <800ms p95 over 10 years:
- **Materialized Monthly Aggregates**: `monthly_spend_by_category` etc., populated nightly via Celery; dashboards query these, not raw transactions.
- **Indexed Queries**: `(entity_id, booked_date, category_id)` range scans; `(entity_id, status)` review counts.
- **Redis Caching**: `ForecastCache` + `CorrelationView`; hit <10ms; miss → async recompute (stale-while-revalidate).
- **Pagination & Limits**: grids default 50, lazy-load; charts cap 24mo/365 days (aggregate older).
- **Invalidation Strategy**: confirmed transactions → fine-grained invalidation (metric + entity + month); batch (every 5 confirms or 10 min).
- **Frontend Optimization**: React.memo, TanStack Query dedup, re-render on data change only.

## Additional / Enriched Requirements
- **User-Defined Budgets by Category & Entity**: fiscal years or calendar months; thresholds (80/100/110%).
- **Savings-Opportunity Insights**: underutilized buckets, below-average categories, subscription redundancy; reallocation suggestions.
- **Scheduled In-App Digests**: weekly/monthly summary (no email; saved-view highlights).
- **Drill-Through from Aggregate to Source**: one-click card → list → detail → document; breadcrumb.
- **Comparative Periods (MoM/YoY)**: every trend chart overlays prior period; % changes + outliers.
- **What-If Forecast Scenarios**: non-persisted exploratory ("reduce grocery 10%?").
- **Goal Progress Tracking**: progress, runway, burn-down.
- **Alert Center Consolidation**: all anomalies unified, filterable.
- **Export to CSV/PDF**: snapshots + detailed reports; PDF metadata (date, filters).

## Open Questions / Decisions
- **Default forecast method?** → *Moving-average (6-month); linear opt-in.*
- **Correlation recompute frequency?** → *Daily 02:00 UTC; on-demand "refresh now" only.*
- **Budget alert thresholds?** → *Hardcoded defaults (80/100/110%); per-budget override.*
- **Forecast confidence metric?** → *MAPE lagging; heuristic for real-time; update monthly.*
- **Digest frequency?** → *Monthly (customizable).*
- **Price drift threshold?** → *>10% over 6 months or >2%/month per product/merchant.*

## Definition of Done
- Overview <200ms; correlations from cache <50ms (miss recomputes async); drilldowns/ledger grids <300ms.
- Four correlation views implemented + tested (supermarket↔groceries gap; health OOP vs reimbursement lag; utility cost↔consumption divergence; income↔expenses waterfall).
- Shared global filter bar; all drilldowns respect entity/date/tag; drill-through end-to-end.
- Review Queue widget; one-click to detail; count badge updates on confirms.
- Budget CRUD + deviation detection + alerts; integration test.
- SavedView persistence + sharing; CSV/JSON/PDF export end-to-end.
- Forecast cache invalidation verified; MAPE tracked.
- Alerts feed aggregates all module types; filter + dismiss/snooze.
- Performance validated: p95 <800ms for 10-year dataset (load test/profiling).
- WCAG AA; mobile-responsive, no horizontal scroll.

## Integration Contract
- **Consumes**: canonical ledger (`Transaction`, M2), receipts (`ReceiptItem`, M1), claims (M3), utility bills (M4), vehicle expenses (M5), assets/snapshots (M6); all module `Alert`, `ReviewTask`, `AuditLog`.
- **Exposes**: nothing to other modules (read-only); no ledger entities created; chart data derived deterministically; saved views are user config.
- **Materialized Tables** (internal): `monthly_spend_by_category`, `monthly_income`, `net_worth_monthly`, `category_forecast_cache`, `correlation_pairs` — write-only from Celery, read-only by dashboard API.
- **Invalidation Contract**: on any module `ReviewTask` confirmation, emit `AnalyticsInvalidationEvent(metric, entity)` → selective cache invalidation in Analytics Engine.
