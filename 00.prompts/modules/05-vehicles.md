# Module 5 — Vehicle & Transportation Management (`modules/vehicles`)

## Purpose
Track all vehicle lifecycle costs (fuel, maintenance, insurance, taxes, inspections), compute fuel efficiency and cost-per-km, support multi-payer expense splitting, and provide per-member accountability and total cost-of-ownership analytics. Integrate Portuguese compliance requirements (IUC annual tax, IPO mandatory inspection) and support mixed fuel fleets (petrol, diesel, LPG, electric).

## Actors & User Stories
- *As a driver*, I log fuel purchases with odometer, and the system computes L/100km automatically.
- *As a household manager*, I track multi-vehicle expenses and split costs by driver (e.g., User A: 60%, User B: 40%).
- *As a tax/compliance officer*, I receive reminders for IUC renewal and IPO inspection due dates.
- *As an EV owner*, I log home and public charging separately and track cost-per-kWh.
- *As an analyst*, I view fuel efficiency trends, cost-per-km evolution, and per-member cost accountability.

## Data Model
All monetary fields (`_eur` suffix) are `NUMERIC(10,2)` decimal EUR amounts (e.g. `19.99`), never minor-unit integers; UI displays them pt-PT-formatted (e.g. `19,99€`).
- **Vehicle**: `id, entity_id, name, make, model, plate_masked, fuel_type(PETROL_95|PETROL_98|DIESEL|LPG|ELECTRIC), odometer_km, purchase_date, purchase_price_eur, resale_value_snapshot_id?, is_deleted, tags[]`.
- **VehicleExpense** (base): `id, vehicle_id, expense_type(FUEL|MAINTENANCE|INSURANCE|TAX|REPAIR|OTHER), date, amount_eur, odometer_km, description, document_id, transaction_id?, payer_split JSONB, tags[], confidence, decision_reasons`.
- **FuelEvent** (efficiency analytics): `id, vehicle_id, date, odometer_km, fuel_type, liters NUMERIC(8,3), price_per_liter_eur, total_cost_eur, station_merchant_id, is_full_fill BOOLEAN, source_expense_id, confidence`. *L/100km computed only between consecutive full fills; partial fills recorded but excluded.*
- **MaintenanceSchedule**: `id, vehicle_id, service_type(OIL|FILTER|TIRES|BRAKES|INSPECTION|OTHER), interval_km, interval_months, next_due_km, next_due_date, notes, reminder_sent_at`.
- **RecurringVehicleCost**: `id, vehicle_id, cost_type(INSURANCE|IUC|PORTAGEM|INSPECTION|REGISTRATION), amount_eur, cadence(MONTHLY|QUARTERLY|ANNUAL), due_date, last_paid_date, next_due_date, notes, linked_transaction_id?`.
- **VehicleInsurance**: `id, vehicle_id, insurer_name, policy_number, premium_amount_eur, coverage_type, renewal_date, document_id`.
- **TireLog**: `id, vehicle_id, brand, size, install_date, install_odometer_km, removal_date, removal_odometer_km, cost_eur, notes`.
- **EVChargeEvent**: `id, vehicle_id, date, odometer_km, energy_kwh NUMERIC(7,2), cost_eur, charger_type(HOME|PUBLIC_DC|PUBLIC_AC), location, cost_per_kwh_eur`.
- **VehicleResaleSnapshot**: `id, vehicle_id, as_of_date, estimated_value_eur, source_url, notes`.
- Derived: `l_per_100km` (inter-full-fill), `cost_per_km_eur`, `cost_per_month_eur`, `total_ownership_cost_eur`. Money as `amount_eur NUMERIC(10,2)`; `payer_split` JSONB `[{entity_id, percentage}]` summing exactly **100**.

## Functional Requirements
- **FR-5.1 Expense Logging.** Record fuel, maintenance, insurance, taxes, repairs; auto-linked to bank transactions by date/amount/merchant.
- **FR-5.2 Fuel Event Tracking & Efficiency.** Log with odometer, liters (full/partial), date. Compute `L/100km` **only between consecutive full fills**; partial fills excluded and clearly marked.
- **FR-5.3 Multi-Payer Cost Splitting.** `payer_split` array; validate sum = 100; per-member rollup.
- **FR-5.4 Mileage Consistency Validation.** Odometer strictly monotonic per vehicle; retroactive entries with earlier odometer rejected.
- **FR-5.5 Maintenance Scheduling & Reminders.** Intervals (km/months); auto-generate reminder tasks in Review Queue when due.
- **FR-5.6 Recurring Cost Management.** Insurance, IUC, portagens, inspection; auto-reconcile with bank; alert on missed/changed amounts.
- **FR-5.7 Portuguese Compliance Tracking.** IUC (annual road tax; 30-day reminder), IPO (biennial inspection; due-date + pass/fail), Via Verde / Portagens (toll charges; stored-value + reconciliation).
- **FR-5.8 EV Charging Cost Tracking.** Log home/public charging (kWh + cost); configurable home rate (€/kWh).
- **FR-5.9 Resale Value Snapshots.** Link to Assets; periodically snapshot estimated resale value.
- **FR-5.10 Trip-Level Tagging.** Tag expenses/events (`#commute`, `#vacation`, `#work`, `#errands`).
- **FR-5.11 Tire & Oil-Change Tracking.** Dedicated tire log + oil-change intervals for proactive maintenance.

## Automation Rules
- Efficiency computed only between full fills: `(liters_consumed / distance_km) × 100`; partial fills break the chain.
- Fuel events auto-matched to bank transactions (±2 days, amount ±5%, merchant similarity).
- Recurring costs auto-suggested to matching transactions; confirmations advance `last_paid_date`.
- Maintenance reminders when `next_due_km ≤ odometer` or `next_due_date ≤ today`; creates ReviewTask; completion updates next interval.
- IUC/IPO due-date alerts 30 days prior (configurable).
- Per-member cost = Σ (`expense_amount × payer_split[member].percentage / 100`).

## UI / Screens
- **Vehicle Manager**: list/add/edit (make, model, plate, fuel type, purchase price, resale link).
- **Fuel Log**: date, odometer, liters, price/L, is_full_fill (highlighted if partial), linked transaction.
- **Expense Log**: type-filtered, odometer, amount, split summary, tags.
- **Efficiency Dashboard**: L/100km trend (excludes partials); cost-per-km; annual summary.
- **Maintenance Board**: scheduled services, completion, next-due countdown.
- **Recurring Cost Calendar**: IUC/IPO/portages timeline, reconciliation status.
- **Cost-Split Summary**: per-member accountability; total ownership cost; cost-per-km per member.
- **EV Charging Dashboard**: kWh vs cost, home vs public split, estimated annual cost.

## API Surface
`CRUD /vehicles` · `CRUD /fuel-events` · `CRUD /vehicle-expenses` · `CRUD /maintenance-schedules` · `CRUD /recurring-costs` · `POST /vehicles/{id}/confirm-expense` · `GET /vehicles/{id}/analytics` · `GET /vehicles/{id}/maintenance-forecast` · `GET /vehicles/iuc-ipo-calendar` · `POST /ev-charge-events` · `GET /vehicles/{id}/resale-snapshots`.

## Analytics & KPIs
- Fuel efficiency trend (L/100km per vehicle/fuel type, rolling 3-month avg).
- Cost metrics (cost-per-km, cost-per-month, total cost of ownership).
- Per-member attribution (cost share, by trip tag).
- Compliance readiness (IUC/IPO due dates, overdue flags).
- Maintenance forecast (upcoming services + estimated cost).
- EV economics (cost-per-kWh home vs public; annual electricity vs petrol/diesel equivalent).

## Edge Cases & Validation
- **Odometer monotonicity**: retroactive event with earlier odometer → error.
- **Efficiency calc**: only between full fills; zero liters/distance → null (flagged "incomplete").
- **Payer split**: sum exactly 100; fractional allowed (33.33/33.33/33.34); rejected at API if invalid.
- **Partial fill**: marked and excluded from efficiency buckets; user educated on impact.
- **Multi-fuel vehicles**: L/100km not computed across fuel-type boundaries.
- **Recurring cost overrun**: actual >10% over expected → anomaly; confirm or update expected.
- **Resale value expiry**: snapshots >12 months grayed out; annual refresh encouraged.

## Additional / Enriched Requirements
1. **Portuguese IUC Compliance**: automate due-date tracking; optional CO₂-emission-based tax lookup; 30-day-prior reminder.
2. **Multi-Fuel Fleet Efficiency**: separate L/100km per fuel type; side-by-side comparison.
3. **Trip-Level Cost Attribution**: tag by trip; aggregate cost-per-trip insights.
4. **Tire Service Integration**: rotations, wear patterns, replacement intervals; cost-per-tire-life amortization.
5. **EV Home Charging Rate Config**: household €/kWh per tariff period; auto-compute home cost; compare to public.
6. **Resale Value Linkage**: Vehicle → Assets link; depreciation curve.
7. **Via Verde Integration Hint**: PORTAGEM cost type → toll pass balance/consumption affordance.
8. **Anomaly Detection**: efficiency drop >15% YoY (engine issue); fuel price/L spike (market vs rogue entry).
9. **Commute/Work Mileage Tracking**: tag commute (potentially deductible); business vs personal analytics.

## Open Questions / Decisions
1. **EV home charging rate global or per-vehicle?** → *Per-household with per-vehicle override if multi-rate tariff.*
2. **L/100km rounding?** → *2 decimals.*
3. **Partial-fill recovery?** → *No auto-repair; user toggles `is_full_fill` to reconcile.*
4. **IUC auto-renewal suggestion?** → *Yes, with confirmation.*
5. **Trip attribution with multi-payer split?** → *Yes; trip cost = expense × payer_split %.*

## Definition of Done
- All FRs + edge cases implemented; ≥80% test coverage on domain logic.
- Odometer monotonicity enforced by DB constraint + validation.
- Payer split sum-to-100 enforced at API + DB; fractional supported.
- L/100km correct between full fills; partials excluded.
- Maintenance reminders routed to Review Queue; completion updates schedule.
- IUC/IPO reminders fire 30 days prior; due-date calendar rendered.
- Recurring cost reconciliation; anomaly alerts on amount change.
- EV charging events logged; cost-per-kWh metrics.
- Per-member rollup queries <500ms over 10 years.
- UI screens: manager, fuel log, expense log, efficiency dashboard, cost-split, maintenance board, compliance calendar.

## Integration Contract
- **Exposes**: `Vehicle`, `VehicleExpense`, `FuelEvent` as link targets for Banking (M2); per-member cost series feed Dashboards and Household analytics.
- **Consumes**: `Entity` (payer attribution), `Merchant` (stations/garages/insurers), `Category`, `Transaction` (M2), `Document`, `Asset` (resale snapshot).
- **Automation Hook**: Recurring cost matching in Reconciliation Engine (M2); Maintenance reminders for Review Queue; anomaly detection on efficiency/charge amounts.
