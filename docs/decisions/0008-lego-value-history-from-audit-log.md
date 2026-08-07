# 0008 — No valuation-history table for LEGO

## Context

M9 states that `current_value_eur` is a single, manually maintained field on
`LegoSetModel` with a `value_updated_at` stamp — no valuation history, no
sealed/used/parts-out bands, no valuation engine, no automatic price refresh. The
natural engineering instinct is to add a `lego_valuations` table "because it is
cheap". It is not cheap: it implies a refresh job, a provider, a band model and a
chart, none of which the household asked for.

## Decision

Keep the single field. Its change history is recoverable from `audit_logs`, which
already records the `before`/`after` snapshot of every mutation:

```sql
SELECT created_at,
       before ->> 'current_value_eur' AS antes,
       after  ->> 'current_value_eur' AS depois
FROM audit_logs
WHERE table_name = 'lego_set_models' AND record_id = '<uuid>'
  AND before ->> 'current_value_eur' IS DISTINCT FROM after ->> 'current_value_eur'
ORDER BY created_at;
```

Staleness is **surfaced, not hidden**: `value_is_stale` and `value_age_days` are
computed on read against a configurable threshold (default 180 days) and shown in the
UI as a warning badge, an "oldest value" line on the overview, and an amber tint on
the value column. The number is still used in totals — never silently zeroed.

## Consequences

- The overview deliberately has **no historical time series**. There is no snapshot
  table to draw one from, and inventing one from audit rows would imply a precision
  the data does not have.
- A sealed copy and a battered used copy of the same set are valued identically. This
  is the accepted trade-off at household scale; the mitigation is to enter the value
  you would actually get.
- If valuation history is ever genuinely needed, `audit_logs` already contains it —
  the migration is a read model, not a data backfill.
