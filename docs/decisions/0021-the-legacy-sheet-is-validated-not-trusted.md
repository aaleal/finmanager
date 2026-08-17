# 0021 — The legacy sheet is validated, not trusted

## Context

FR-1.19. The `SUPERMARKET_YYYY` sheet is flat, has no `Receipt` parent, derives
its own invoice total with a `SUMIF`, and was maintained by hand for years.

## Decision

Three rules.

1. Snap each Fs row's timestamp back onto the nearest non-Fs timestamp within
   2 s, then group by `(merchant, timestamp)` — never by `Preço Fatura`, which
   on a nudged Fs row sums only itself.
2. Recompute `PromoGlob` deterministically from the receipt-level residual and
   spread it by largest remainder, rather than trusting a column filled on
   8 % of rows.
3. Score every imported receipt like a parsed one. A group that does not
   reconcile becomes `NEEDS_REVIEW` with a reason, and every other anomaly is
   reported as an exception rather than repaired.

## Consequences

Measured against the real 2,429-row 2025 sheet:

| Run | Groups | Reconciling | Only-Fs |
| :-- | --: | --: | --: |
| Whole sheet (`include_non_grocery=true`) | 288 | 281 | 6 |
| Grocery only (the default) | 272 | 265 | 4 |

- The snap window is what keeps Fs articles attached to their invoice: 425 Fs
  rows (419 `F` + 6 lowercase `f`), of which 418 snap back onto their invoice
  (401 at exactly +1 s, 17 at +0 s). A regression above roughly 6 only-Fs
  groups means the window or the grouping key has broken, not that the sheet
  changed.
- The importer reconciles one group more than the sheet's own `Price_Final`
  column does (281 against 280), because the invoice-level credit is
  recomputed and spread by largest remainder, which makes the sum exact by
  construction whenever the residual is non-negative. The groups that still
  fail have a *negative* residual — genuine holes in the sheet, such as one
  Continente group claiming €41,99 against a single €3,74 line — and they
  land in `NEEDS_REVIEW` with a reason rather than being forced to reconcile.
- A handful of Fs rows carry no price at all; they are reported as
  `fs_row_without_value` exceptions rather than written as meaningless
  articles.
- A re-run **updates**, it does not duplicate.
- Skipping non-grocery merchants (IKEA, Leroy, Wells, Normal, Action, El Corte
  Inglés — 58 rows on the whole sheet) is a *reported* decision, not a silent
  one, and widening the scope later is a re-run, not a migration.
