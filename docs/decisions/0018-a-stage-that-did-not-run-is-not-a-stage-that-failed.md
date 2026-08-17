# 0018 — A stage that did not run is not a stage that failed

## Context

The confidence engine (`app/services/receipts/confidence.py`) weights product
match at 0.30 of the combined score. In this slice `MasterProduct` does not
exist yet, so `product_match` has nothing to report. Scoring it `0` would
report a false negative on every single receipt this slice ships — the module
would look broken on the one thing it was built to demonstrate.

## Decision

A signal of `None` means *the stage did not run*: its weight is redistributed
over the stages that did run (`WEIGHTS` renormalised over whichever of
`merchant_match`, `ocr_text`, `arithmetic`, `product_match` are present), and the
omission is recorded as a `*_unavailable` decision reason (`product_match_unavailable`,
`arithmetic_unavailable`). A signal of `0` means *the stage ran and found
nothing*, which is a genuine failure and is scored as one.

## Consequences

- Today a clean digital PDF — good OCR text, matched merchant, reconciled
  arithmetic, no product signal — auto-accepts on the three stages that did
  run. Once the catalogue ships, an **empty** catalogue starts scoring
  `product_match = 0` and those same receipts move to review. That is not a
  regression; it is the module's Decision #39 (the fix for a thin catalogue is
  data, not thresholds) working as designed, and an integration test names the
  change of behaviour explicitly so it reads as expected rather than alarming.
- The auto-accept rate is displayed as an observed trend, captioned «observada,
  não uma meta» — it is never a target to hit, and this ADR is why it can drop
  the day a real feature ships without anyone chasing the number back up.
