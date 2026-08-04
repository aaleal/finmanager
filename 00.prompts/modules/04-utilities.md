# Module 4 — Household Utilities (`modules/utilities`)

## Purpose
Track utility billing periods, physical consumption, and costs across electricity (EDP/Galp/Endesa), gas, and water ("águas" municipal). Compute cost-per-unit, seasonal baselines, and anomaly detection. Distinguish estimated vs. actual readings and reconcile bills to bank transactions. Support Portuguese tariff complexity: time-of-use rates (vazio/cheias/ponta), contracted power (potência contratada), fixed terms, IVA rates, and self-consumption credits.

## Actors & User Stories
- *As a household manager*, I upload or manually enter utility bills; the system detects anomalies and alerts me to consumption spikes before I see the bill.
- *As an auditor*, I compare bill totals to transaction history and flag mismatches or missing readings.
- *As an energy analyst*, I see consumption by time-of-use tariff bucket (kWh@vazio, kWh@cheias, kWh@ponta) and track seasonal patterns.
- *As a solar prosumer*, I record self-consumption and injection credits, ensuring net costs reflect grid exchanges only.
- *As a multi-property household*, I roll up utilities across meters in the main residence and summer house, detecting anomalies per address.

## Data Model
All monetary fields (`_eur` suffix) are `NUMERIC(10,2)` decimal EUR amounts (e.g. `19.99`), never minor-unit integers; UI displays them pt-PT-formatted (e.g. `19,99€`).
**UtilityMeter**: `id, entity_id, utility_type(ELECTRICITY|GAS|WATER), provider_merchant_id, unit(kWh|m3), address_id?, contracted_power_kw?` (electricity), `tariff_plan_id?, tariff_type(TIME_OF_USE|FLAT|TIERED), start_date, end_date, is_active, notes`.

**UtilityBill** (distinct from Reading): `id, meter_id, billing_period_start, billing_period_end, is_estimated, actual_read_date?, estimated_read_date?, consumption NUMERIC(14,4), unit, total_cost_eur, fixed_cost_eur ("termo fixo"), variable_cost_eur ("termo variável"), iva_eur, credit_eur (self-consumption/injections), document_id, transaction_id?, processing_status, confidence, decision_reasons, tou_breakdown JSONB{vazio_kwh, cheias_kwh, ponta_kwh, vazio_cost_eur, cheias_cost_eur, ponta_cost_eur}`.

**UtilityMeterReading** (raw physical readings): `id, meter_id, reading_date, consumption_kwh_or_m3, is_estimated, reading_type(METER_PHOTO|UTILITY_INVOICE|SMART_METER_API), raw_payload JSONB`.

**TariffPlan** (user-curated master): `id, provider_id, name, tariff_type, rate_tiers JSONB[{bucket, rate_eur_per_kwh (NUMERIC(8,5)), hours_weekday, hours_weekend}], power_tier_limits?, fixed_cost_eur, start_date, end_date, iva_rate_pct (13 PT)`.

**ProviderContract**: `id, meter_id, provider_merchant_id, tariff_plan_id, contract_start, contract_end, contracted_power_kw`.

**DailyBaselineConsumption** (derived, anomaly detection): `id, meter_id, month_season, daily_avg_consumption, daily_avg_cost_eur, daily_std_dev, reading_count`.

## Functional Requirements
- **FR-4.1 Consumption Tracking.** Log billing periods with consumption (kWh, gas kWh/m³, water m³) and cost; distinguish estimated vs. actual. Estimated readings flagged and excluded from forecasts.
- **FR-4.2 Efficiency Analytics.** Compute cost/unit (€/kWh, €/m³), daily average consumption/cost, period-over-period % change; compare against seasonal baseline; support time-of-use per-bucket breakdown.
- **FR-4.3 Anomaly Detection.** Alert on consumption spikes >1.5× seasonal baseline or Z-score >2.5 (configurable, default 2.0). Separate cost-spike alerts. Rules: "Read changed but not recorded," "Missing reads (gap >60 days)," "Estimated consecutive—actual expected."
- **FR-4.4 Bill Reconciliation.** Match bills to bank transactions (M2) by date (±5 days), amount (±5%), provider name; surface link confidence; low-confidence flagged.
- **FR-4.5 Time-of-Use Tariff Breakdown.** For vazio/cheias/ponta plans, parse per-bucket kWh and cost; if detail unavailable, flag for manual entry; render per-bucket trends.
- **FR-4.6 Contracted Power & Fixed Term.** Record `potência contratada` and "termo fixo"; alert if peaks exceed contracted power; track fixed cost separately.
- **FR-4.7 Self-Consumption & Grid Injection Credits.** Record self-consumption and injection credits (`credit_eur`, `credit_reason SOLAR_INJECTION|OTHER`); net cost = total − credit.
- **FR-4.8 Estimated-to-Actual Reconciliation.** When an estimated bill is replaced by an actual read, auto-link, compute true difference, adjust cost if rates changed; preserve both for audit.
- **FR-4.9 Provider & Tariff History.** On provider switch/renewal, create new `ProviderContract` with retroactive tariff context; support switching windows with dual bills.
- **FR-4.10 Multi-Meter Household Rollup.** Aggregate consumption/cost across meters (main + secondary addresses); configurable aggregation; household-level anomaly alerts.

## Automation Rules
1. **Estimated Reading Detection.** `is_estimated=true` or bill date ≠ actual read date → PENDING_REVIEW; never used in forecasts/baselines.
2. **Anomaly Scoring.** Z-score = (daily_avg − baseline_mean)/baseline_std vs same month/season; Z > threshold (default 2.0) → alert + ReviewTask.
3. **Cost Anomaly.** total_cost > expected by ±15% with no rate change → alert.
4. **Missing Reads.** Gap between consecutive bills > 60 days → alert.
5. **Consecutive Estimated.** N consecutive estimated bills without actual read → escalate alert.
6. **Time-of-Use Learning.** Track shift between buckets month-over-month; surface behavioral efficiency.
7. **Bill↔Transaction Reconciliation.** Confidence = date_proximity × amount_match × merchant_match; auto-accept ≥0.90 else ReviewTask.

## UI / Screens
1. **Meter Manager** — list/add/edit/delete meters (address, type, provider, contracted power, tariff).
2. **Bill Entry & Parsing** — upload PDF or manual entry; auto-parse (pdfplumber/OCR); confirm/edit.
3. **Consumption Trend Charts** — daily/monthly with seasonal overlay + anomaly points; toggle consumption/cost.
4. **Time-of-Use Breakdown** — stacked bar (vazio|cheias|ponta) + cost overlay + recommendations.
5. **Anomaly Alerts Panel** — recent anomalies with severity; click-through; dismiss/confirm as expected.
6. **Multi-Meter Household Rollup** — aggregate + per-address breakdown + comparative flags.
7. **Bill Reconciliation Review** — bill ↔ suggested transaction; confirm/reject.

## API Surface
`CRUD /meters` · `POST /utility-bills` (upload/ingest, idempotent) · `GET /utility-bills` (filters: meter, date, is_estimated, status) · `PATCH /utility-bills/{id}` · `POST /utility-bills/{id}/confirm` · `GET/POST /utility-readings` · `POST /meter-readings/{id}/link-to-bill` · `GET /meters/{id}/analytics` · `CRUD /tariff-plans` · `POST /tariff-plans/{id}/apply-to-meters` · `GET /utilities/anomalies` · `POST /utilities/anomalies/{id}/confirm` · `GET /utilities/reconciliation-suggestions` · `POST /utilities/{id}/link-to-transaction` · `GET /households/{id}/utilities/rollup`.

## Analytics & KPIs
- Consumption trends (monthly/yearly by meter/type; daily avg; vs prior year/3-year avg).
- Cost evolution (total, €/unit, €/day; period % change).
- Seasonal comparison (winter vs summer).
- Time-of-use profile (% per bucket; higher vazio% ≈ better).
- Anomaly flags (count, trend, dismissal rate).
- Cost-per-occupant; contracted power utilization; self-consumption ratio.

## Edge Cases & Validation
1. **Overlapping billing periods** → flag duplicate/overlap.
2. **Gapped periods** (>60 days) → alert.
3. **Unit consistency** — bill must match meter unit.
4. **Estimated vs actual** — delta >10% → alert.
5. **Negative consumption** — allowed for net metering; flag unusual.
6. **Time-of-use data missing** — `tou_breakdown_available=false`; exclude from analytics; offer manual entry.
7. **Rate changes mid-period** — split accounting or flag.
8. **Provider switch during period** — record both; compute net once actual confirmed.
9. **Meter replacement** — link old→new; prevent false anomaly from discontinuity.

## Additional / Enriched Requirements
- **ER-4.1 Degree-Day Normalization.** Normalize heating/cooling consumption to standard HDD/CDD (18°C baseline) so warm winters don't read as drops. Opt-in weather fetch.
- **ER-4.2 Behavioral Alerts & Efficiency Recommendations.** Non-alarm insights (e.g., shift load off ponta hours to save).
- **ER-4.3 IVA Rate Tracking & Tax Reporting.** Track `iva_rate_pct` per bill (13% default PT); export VAT-paid summaries.
- **ER-4.4 Subscription/Fixed-Cost Predictability.** Decompose variable + fixed + credits; predict next bill.
- **ER-4.5 Multi-Tariff Optimization.** Simulate 12-month cost under alternative plans; recommend cheapest.
- **ER-4.6 Per-Meter Address & Location Context.** `address_id` shared with Assets; per-location anomalies.
- **ER-4.7 Estimated Reading Follow-Up Workflow.** Celery Beat reminder before next expected read; escalate if unconfirmed.
- **ER-4.8 Smart Meter Data Ingestion (FUTURE).** Optional API polling (EDP) to populate readings automatically.

## Open Questions / Decisions
1. **Anomaly thresholds global or per-meter/season?** → *Per-meter, per-season, configurable (default Z ≥ 2.0).*
2. **Shared meters across entities?** → *Attributed to bill-payer entity; split via `payer_split` JSONB.*
3. **Degree-day normalization auto or opt-in?** → *Opt-in per meter (privacy; external API optional).*
4. **Link estimated bills to transactions?** → *Yes, provisional (`link_status=PROVISIONAL`); auto-update on actual.*
5. **SLA for overdue read?** → *Alert after 40 days; urgent after 60.*
6. **Self-consumption credits netted or separate?** → *Both: show total_before_credits, credit, net.*

## Definition of Done
- [ ] Meter CRUD (address, type, unit, provider, contracted power, tariff).
- [ ] Bill upload/parse (PDF + manual); auto-extraction.
- [ ] `is_estimated` flag; estimated excluded from forecasts.
- [ ] UtilityMeterReading + linking for audit.
- [ ] DailyBaselineConsumption + anomaly detection (Z-score, cost %) configurable.
- [ ] Consumption & cost trend charts per meter/type.
- [ ] Time-of-use breakdown (vazio|cheias|ponta) parsing + visualization.
- [ ] Bill↔Transaction reconciliation (M2); confidence scoring.
- [ ] Anomaly alerts UI; confirm/dismiss.
- [ ] Multi-meter rollup with per-address filtering.
- [ ] TariffPlan master + CRUD; time-of-use tiers definable.
- [ ] ProviderContract; provider-switch handled (no false anomalies).
- [ ] Self-consumption credits; IVA tracking (13% default).
- [ ] API + OpenAPI; tests (Z-score, reconciliation, edge cases).
- [ ] Seed: EDP, Galp, EPAL/"Águas", sample tariffs/bills.
- [ ] ≥80% auto-accept on uploads + anomaly detection; low-confidence → ReviewTask.

## Integration Contract
- **Exposes**: `UtilityBill`, `UtilityMeter` as recordable entities; `Link` targets for Banking (M2); anomaly alerts to Alert Engine; consumption/cost to Dashboards (M8); per-entity cost to Household budgeting (M7).
- **Consumes**: `Merchant` (providers), `Entity`, `Transaction` (M2), `Document` (bill PDFs), `Category`, `Tag`.
