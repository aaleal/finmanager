# Module 3 — Health Expenses & Insurance Claims (`modules/health`)

## Purpose
Centralize medical expenses and their reimbursement lifecycle across Portuguese private insurers (Fidelidade, Allianz, Médis), mutual funds ("caixas"), and public subsidies (ADSE-style), computing out-of-pocket costs and automating claim matching to bank credits. Supports per-family-member coverage plans with coordination-of-benefits rules and deadline tracking per insurer.

## Actors & User Stories
- *As a household manager*, I log a medical receipt, and the system suggests which insurer(s) to claim from based on coverage.
- *As a claimant*, I upload a receipt once and receive automatic reminders if payment is pending past the insurer's SLA.
- *As a dependent*, my medical expenses are tracked under my name but rolled up in household views.
- *As a tax preparer*, I export all health expenses marked as IRS-deductible ("despesas de saúde") for e-fatura submission.
- *As an auditor*, I trace the complete chain: receipt → expense → claim(s) → bank credit(s) and see why each part was accepted/rejected.

## Data Model
All monetary fields (`_eur` suffix) are `NUMERIC(10,2)` decimal EUR amounts (e.g. `19.99`), never minor-unit integers; UI displays them pt-PT-formatted (e.g. `19,99€`).
- **MedicalExpense**: `id, entity_id, member_id, incurred_date, provider_nif (tax ID), provider_merchant_id, category(APPOINTMENT|DIAGNOSTIC|PHARMACY|DENTAL|OPTICAL|MENTAL_HEALTH|HOSPITAL|OTHER), description, gross_amount_eur, copay_amount_eur?, document_id, transaction_id?, is_irs_deductible, tags[]`.
- **Claim**: `id, medical_expense_id, insurer_id, status(INCURRED|SUBMITTED|PARTIALLY_REIMBURSED|FULLY_REIMBURSED|CLOSED|REJECTED), submitted_at, submission_reference?, expected_amount_eur, submitted_amount_eur, deadline_for_payment, last_status_update_at, rejection_reason?, tags[]`.
- **ClaimReimbursement** (one per payout, enabling partial/staged reimbursements): `id, claim_id, reimbursement_date, received_amount_eur, received_by_transaction_id, source_document_id, is_final, notes`.
- **Insurer**: `id, name, kind(INSURANCE|MUTUAL_FUND|PUBLIC_SUBSIDY), nif, contact_email, website, sla_days, is_active, logo_document_id`.
- **CoveragePlan**: `id, member_id, insurer_id, plan_name, coverage_start, coverage_end, eligible_categories[], deductible_eur, copay_pct?, max_out_of_pocket_annual_eur?, coordination_of_benefits_order, notes`.
- **PrescriptionItem** (recurring/standing treatments): `id, member_id, provider_nif, name, dosage, frequency(DAILY|WEEKLY|MONTHLY), start_date, end_date, copay_eur?, estimated_annual_cost_eur, linked_claims[]`.
- Derived: `out_of_pocket_eur = gross − Σ reimbursed` (respects deductible and CoB cap); `reimbursed_pct = Σ reimbursed / gross`. All Claim transitions logged in `AuditLog`; `ClaimReimbursement` links to the delivering bank `Transaction`.

## Functional Requirements
- **FR-3.1 Claim Lifecycle State Machine**: `INCURRED → SUBMITTED → PARTIALLY_REIMBURSED → FULLY_REIMBURSED/CLOSED` (+ `REJECTED`). Rejected claims revert the expense to fully out-of-pocket and may be resubmitted. Illegal transitions (e.g., `CLOSED → SUBMITTED`) rejected by the API.
- **FR-3.2 Multi-Insurer Stacking & Coordination of Benefits**: multiple claims per expense across insurers; `coordination_of_benefits_order` defines claim sequence (primary insurer → secondary mutual fund → tertiary public subsidy). Σ all claims cannot exceed `gross_amount_eur` minus deductible. Each subsequent insurer's share is computed net of prior reimbursements.
- **FR-3.3 Coverage Eligibility & Copay**: match expense category against `CoveragePlan.eligible_categories`; apply copay (flat or %) and deductible per plan; track annual out-of-pocket max; suggest applicable plans; flag out-of-coverage-window expenses.
- **FR-3.4 Deadline & SLA Tracking**: `Claim.deadline_for_payment = submitted_at + insurer.sla_days`; Alert Engine triggers overdue reminders; historical SLA compliance tracked per insurer.
- **FR-3.5 NIF & Provider Tax ID Capture**: store `provider_nif` on MedicalExpense and `Insurer.nif` for e-fatura matching and audit.
- **FR-3.6 Prescription & Recurring Treatment Plans**: `PrescriptionItem` tracks standing treatments; auto-create MedicalExpense records on cadence (Celery Beat); link multiple claims to the same prescription.
- **FR-3.7 Bank Credit Reconciliation**: propose `ClaimReimbursement` links by matching bank credits to open/partial claims (date within ±SLA_days of deadline, amount ±5%, insurer reference). High-confidence auto-confirmed; others → review.
- **FR-3.8 IRS Export for Despesas de Saúde**: flag `is_irs_deductible`; export CSV/XML with household NIF, provider NIF, amount, date for e-fatura integration.

## Automation Rules
- **Insurer Suggestion**: on new expense, scan member `CoveragePlan` records; suggest eligible insurers by category and active window.
- **CoB Ordering**: on confirming a claim, advance to next insurer in `coordination_of_benefits_order`; auto-adjust expected reimbursement based on prior payouts.
- **Overdue Alerts**: daily Celery Beat checks claims with `deadline_for_payment < today` and `status ≠ CLOSED|FULLY_REIMBURSED`; create alert.
- **Partial Accumulation**: each `ClaimReimbursement` updates `Claim.status` (engine decides `FULLY_REIMBURSED` vs stays `PARTIALLY_REIMBURSED` per `is_final`).

## UI / Screens
- **Expense Entry**: date, provider (search by name/NIF), category, gross/copay amounts, coverage plan selector, attachment, IRS-deductible checkbox.
- **Claims Kanban**: swimlanes by status; card shows expense summary, insurer, submitted date, deadline, expected vs received.
- **Reimbursement Matcher**: side-by-side open claims vs unmatched bank transactions; suggest + confirm.
- **Member & Insurer Summaries**: per-member out-of-pocket YTD, per-insurer reimbursement rate + SLA compliance, prescription status.
- **Overdue Dashboard**: claims past deadline with action buttons.

## API Surface
- `POST /medical-expenses` (with auto-insurer suggestion) · `GET /medical-expenses` (filters) · `PATCH /medical-expenses/{id}`.
- `POST /claims` · `GET /claims` (status, member, insurer, overdue) · `POST /claims/{id}/transition` (legal-transition validation).
- `POST /claims/{id}/reimbursements` · `GET /claims/{id}/reimbursements`.
- `CRUD /coverage-plans` · `CRUD /insurers` · `CRUD /prescriptions`.
- `GET /health/irs-export` · `GET /health/analytics`.

## Analytics & KPIs
- Out-of-pocket over time (by member, category, insurer status).
- Reimbursement rate per insurer; SLA compliance (% paid on time).
- Per-member annual out-of-pocket vs deductible and max thresholds.
- Spend by category & coverage gap (low-reimbursement categories → plan upgrade opportunities).
- Claims leakage: count of INCURRED expenses not yet submitted + value at risk.

## Edge Cases & Validation
- **Over-Reimbursement Guard**: Σ `ClaimReimbursement.received` across all claims for one expense **≤ `gross_amount_eur`**; second claim auto-adjusted; flag for review with override + documented reason.
- **Partial Accumulation**: `is_final=false` does not close claim; `is_final=true` triggers state check.
- **Rejected Reopen**: rejecting resets `Claim.status` to `INCURRED`; expense reverts to full out-of-pocket until resubmitted or closed.
- **Duplicate Receipt Prevention**: SHA-256 + provider NIF + amount + date; duplicates flagged for merge.
- **Prescription Cadence Validation**: frequency + dates must be logical; missed/skipped months flagged.
- **Provider NIF Format**: Portuguese 9-digit check-digit validation.

## Additional / Enriched Requirements
- **Preset Insurers (seeded)**: Fidelidade, Allianz, Médis, Multicare, Seguros Tranquilidade, ADSE, SNS-based reimbursements.
- **Mutual Funds ("Caixas")**: employer/union schemes tracked separately from commercial insurers.
- **Per-Plan Deductible** applied once per calendar year; **annual out-of-pocket cap** → 100% coverage for remainder of year once met.
- **Stacking example**: €100 expense → Insurer A covers €80 (OOP €20); Insurer B sees €20, covers €15 net of its €5 deductible → household OOP €5.
- **Recurring Treatments Auto-Submission**: monthly prescriptions may auto-create `Claim` in `SUBMITTED` with expected reimbursement from prior cadence (user reviews/overrides).
- **IRS Compliance**: "Despesas de Saúde" partially deductible above a threshold; export includes NIFs, date, amount, category.
- **Full Chain Traceability**: bank transaction → reimbursement → claim → expense → original receipt document.

## Open Questions / Decisions
1. **Auto-submit new claims?** → *Require confirmation; auto-submission opt-in per insurer.*
2. **Prescription auto-creation cadence job time?** → *Midnight (avoids lag).*
3. **Deductible reset date?** → *Per coverage plan anniversary; default Jan 1.*
4. **Over-reimbursement handling?** → *Flag to user; allow override with documented reason (fraud check).*
5. **Provider NIF capture?** → *Mandatory for professional providers; optional for walk-in clinics.*

## Definition of Done
- State machine enforced; illegal transitions rejected; all transitions logged.
- Multi-insurer math tested: CoB ordering, deductible, out-of-pocket-max, no over-reimbursement.
- Bank reconciliation: ClaimReimbursement linked to Transaction; SLA compliance tracked.
- Overdue alerts: Celery job runs; Review Queue receives alerts.
- Prescription cadence: auto-creates expenses + claims; no failures on month-end edge dates.
- IRS export: includes flagged expenses, validates NIF formats, correct sum.
- Analytics queries sub-100ms for typical household (100–500 expenses, 5–10 insurers).
- Frontend: Kanban, matcher, summaries, alerts; all tests pass.
- OpenAPI complete; data model in ERD.

## Integration Contract
- **Exposes**: `MedicalExpense`, `Claim`, `ClaimReimbursement` as link targets for Banking (M2) and Assets (M6); out-of-pocket totals feed Dashboards.
- **Consumes**: `Merchant` (provider validation), `Entity`/members, `Category` (health sub-tree), `Document` (receipts), `Transaction` (M2), `Tag`, `User` (attribution/audit).
- **Depends on**: Notification Engine (overdue alerts), Reconciliation Engine (bank-match proposals), Intelligence Provider (OCR when needed).
