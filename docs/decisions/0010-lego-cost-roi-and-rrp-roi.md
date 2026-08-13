# 0010 — Two readings of value: cost ROI and RRP ROI, never merged

## Context

A large part of the household's collection arrives as gifts, recorded with
`acquisition_cost_eur = 0.00`. M9 is explicit: ROI is `NULL` for a zero cost basis,
and the UI shows `—` rather than a fake percentage. That is arithmetically right and
practically useless — an entire shelf of sets shows a dash where the interesting
number lives.

M9.1 asks whether to add PVP (RRP) as a column, and whether to carry two ROIs.

## Decision

Two readings, one headline.

1. **Cost ROI stays the headline.** `roi_pct`, `appreciation_eur`, the overview KPI
   cards and every aggregate keep the M9 definition unchanged: current market value
   against what was actually paid, `NULL` when there is no cost basis. Sale figures
   still never enter it.
2. **RRP ROI is a second, derived reading on the set, not on the copy.**
   `LegoSetModelOut` gains `rrp_appreciation_eur` and `rrp_roi_pct`, computed on read
   from `rrp_eur` and `current_value_eur` with the same helpers. Nothing is persisted.
   It belongs to the set because RRP is a property of the catalog entry, not of a
   particular copy.
3. **They are never summed together.** There is no "total RRP ROI" KPI, and the two
   never share a column. The collection's headline performance is what the household
   paid versus what it holds.
4. **The grid degrades, it does not blank.** The ROI cell shows cost ROI. When cost
   ROI is `NULL` and an RRP figure exists, it shows the RRP reading tagged with a
   `PVP` badge and a tooltip saying why. A dash only remains when neither exists.
   `PVP` is also a plain column, so the raw number is always visible.

## Consequences

- Gifts stop being a wall of dashes without ever inflating the collection's reported
  return.
- The distinction is visible at the point of reading (badge + tooltip + separate
  detail rows), not buried in documentation.
- Both figures are exported side by side, so a spreadsheet can aggregate the RRP
  reading if the user ever wants to — the application deliberately does not.
- A set without `rrp_eur` (most MOCs, some older sets) simply has no second reading.
  Nothing is estimated.
