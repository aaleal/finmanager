# 0028 — The line grid shows the category, not the merchant's section heading

## Context

Both line grids — the review pane and the item explorer — carried a «Secção»
column holding `ReceiptItem.merchant_section`, the heading the merchant printed
above the line (`Mercearia Salgada`, `FRUTAS E VEGETAIS`, `--TUBERCULOS--`).

It is a genuinely useful field, but not to the reader. It is a **classification
signal** (Decision #27): it is fed to the classifier as a prior on a brand-new
product. To a human reviewing an invoice it answers a question nobody asked,
while the question they are actually there to answer — *is this line in the right
category?* — had no column at all.

## Decision

«Secção» is replaced by a single **«Categoria»** column showing the full
`L1 › L2 › L3` path of the resolved product. `merchant_section` continues to be
captured on every line and continues to feed the classifier; it is simply not a
column.

Three related grid rules ship with it:

- **Weight is always three decimals** (`0,302 kg`). A register scale prints three,
  and rounding to two silently moves the €/kg it divides into.
- **Quantity is an integer**, and renders as `—` for a product that is
  `sold_by_weight`: a *courgette* priced at the counter has no meaningful count,
  and the weight beside it is the field that means something. (It was previously
  formatted as EUR, so `1` read as `1,00 €`.)
- **Confidence is the `?` icon alone.** The percentage cost a column and said
  less than the `decision_reasons` behind it; the icon opens them. Uncertain
  lines keep a warning icon **and** label, never colour alone.

## Consequences

- The category is empty exactly when the line has not resolved to a
  `MasterProduct` — which is the truth, since a category lives on the product and
  nowhere else (Decision #34). The existing «por resolver» flag beside the product
  picker already says why, so the blank is explained rather than mysterious.
- `ReceiptItemOut` gained `category_path` and `sold_by_weight`, both derived on
  read from the resolved product. Nothing new is stored.
- Serialising a page of lines resolves each product once and memoizes each
  category path, so the added column is one extra query per page, not one per row.
- `merchant_section` remains visible in the review pane's «Porquê?» reasons where
  it influenced a classification, which is where it earns its place.
