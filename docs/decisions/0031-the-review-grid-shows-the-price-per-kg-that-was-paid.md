# 0031 — The review grid shows the €/kg that was paid

> **Superseded by [ADR-0036](0036-the-comparable-price-per-kg-is-before-the-loyalty-card.md).**
> The grid now leads with the promo-adjusted reading; the paid one moved to the
> second line. The reasoning below still holds for *why both are kept*.

## Context

`arithmetic.price_per_kg` computes three readings of the same line:

| Reading | Numerator |
|---|---|
| `price_per_kg_pvp_eur` | the shelf price |
| `price_per_kg_promo_eur` | shelf price minus the line's own promotion |
| `price_per_kg_final_eur` | `paid_price_eur` — promotion **and** the line's share of the invoice-level discount |

The invoice-level discount is not printed per line: it is a single figure on the
*talão* that `recompute()` prorates across every printed line. So the third
reading contains a number the paper never attributed to that article.

That raises a fair question — should a €/kg trend be built on a price that
includes a discount the shopper did not choose per product?

## Decision

The review grid shows **one** column, and it is `price_per_kg_final_eur`: what
the household actually paid, invoice discount and all. The shelf reading is on
the cell's `title`, not in a second column.

The multi-reading question is already answered one layer down and is not
re-answered here: `product_price_history` stores `list_price_eur` **and**
`paid_price_eur` on every observation (ADR-0022), so any analysis can pick its
own basis. The grid is a review surface, not an analysis surface.

## Consequences

- "What did this cost me per kilo?" is answered by the number on screen without
  arithmetic in the reader's head, which is what a review pass needs.
- Comparing shelf prices across merchants stays possible, because the list price
  was frozen alongside the paid one at observation time. Nothing was discarded —
  only one of the two was chosen for a dense grid.
- An Fs article has no paid price, so its "final" reading is its notional worth;
  dividing `0,00` by a weight would drag every trend towards zero (ADR-0023).
- The invoice discount is edited on the **receipt**, never on the line. The
  per-line `invoice_allocated_discount_eur` is a proration recomputed on every
  edit, so a value typed into it would be overwritten by the next save; the grid
  therefore renders it as muted secondary text under the editable promotion
  rather than as an editable field of its own.
