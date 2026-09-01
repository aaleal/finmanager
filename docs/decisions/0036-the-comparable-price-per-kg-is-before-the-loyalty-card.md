# 0036 — The comparable €/kg is the one before the loyalty card

## Context

`arithmetic.price_per_kg` produces three readings, and the review grid can lead
with one:

| Reading | Numerator |
|---|---|
| `price_per_kg_pvp_eur` | shelf price |
| `price_per_kg_promo_eur` | shelf price minus the line's own promotion |
| `price_per_kg_final_eur` | also minus this line's share of the invoice discount |

ADR-0031 chose `final` — what was actually paid. Living with it showed the flaw:
the invoice-level discount is a **loyalty-card credit**, spread across every line
by proration. It is a fact about the household's card balance that day, not
about the product. Two identical purchases a week apart get different €/kg for
reasons that have nothing to do with the price of the thing.

## Decision

The grid leads with `price_per_kg_promo_eur` — shelf price net of the line's own
promotion, which *is* a property of the product on that day — and shows
`price_per_kg_final_eur` beneath it, small, only when the two differ.

The same reversal applies to the `Total` column, whose leading figure is already
`PVP − promoção` with the paid amount underneath.

## Consequences

- Comparing a product across dates and merchants is now comparing like with
  like. A card discount no longer makes a product look cheaper than it was.
- What was actually spent is never hidden — it is one line down, and it remains
  the figure the price history freezes (ADR-0022 stores both, so no analysis
  loses anything either way).
- This supersedes the choice in ADR-0031, not its reasoning: that ADR argued the
  grid should answer "what did this cost me", and it still does, in the second
  line. What changed is which of the two questions leads.
