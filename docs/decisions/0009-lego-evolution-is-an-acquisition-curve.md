# 0009 — The LEGO evolution chart is an acquisition curve, not a price history

## Context

M9.1 asks for a line chart on the LEGO overview showing, over time, the number of
sets owned, the money spent and the current market value.

Two of those three are real history. The third is not:

- **Copies** and **cost** are recoverable exactly, from `LegoSetInstance.acquisition_date`
  and `acquisition_cost_eur`. Nothing new has to be stored.
- **Market value** is not. [0008](0008-lego-value-history-from-audit-log.md) keeps a
  single hand-maintained `current_value_eur` per set with no snapshot table, and M9
  states plainly that the overview has no time series "because there is no snapshot
  table to draw one from, by design".

Drawing a market-value line would therefore mean either reconstructing it from
`audit_logs` — a sparse, irregular series of manual edits that would look like a
price history without being one — or adding the valuation table that 0008 refused.

## Decision

Ship the chart, and make the third line say what it actually is.

`GET /lego/overview` returns `timeline: TimelinePoint[]`, one point per month in
which something was acquired, carrying **cumulative** values:

| Field | Meaning |
| :--- | :--- |
| `copies` | copies owned up to and including that month — real history |
| `cost_eur` | Σ acquisition cost up to that month — real history |
| `value_eur` | **today's** market value of everything acquired up to that month |

`value_eur` is drawn as a **dashed** line and the card states in words that it is a
"valor de hoje", not a quote from that month. The two solid lines are the honest
ones.

Copies without an `acquisition_date` cannot be placed on the axis and are **never
guessed into a bucket**; they are counted in `copies_without_date` and the count is
shown under the chart. `SOLD`/`GIFTED` copies stay out, like every other M9 KPI.

## Consequences

- No new table, no snapshot job, no backfill. The chart is a projection of data the
  module already had.
- The value line answers the question the user actually asked — "is the collection
  worth more than it cost?" — over time, without pretending to know what a set was
  worth in 2019.
- The shape of the value line changes retroactively whenever a set's value is
  edited. That is correct for what it measures, and is why it is dashed and labelled.
- If a genuine price history is ever wanted, 0008 still holds: it is a snapshot table
  and a refresh job, and it should be argued for on its own merits.
