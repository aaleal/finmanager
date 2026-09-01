# 0035 — Confirming a category is a statement about the product

## Context

The review pane has a button, *«Confirmar categorias sugeridas»*, whose tooltip
says it confirms **per product, not per line**. That reads as a contradiction: a
button on an invoice that does not act on that invoice's lines looks like the
wrong button in the wrong place.

## Decision

It stays, and it stays per product, because a category is not a property of a
line. A line inherits its category by resolving to a `MasterProduct`, and the
category lives on that product and nowhere else (Decision #34). There is no
per-line category to confirm — confirming one would have nothing to write to.

The consequence is the point of the feature: **the backlog shrinks as the
catalogue matures instead of growing with every shop.** Confirm *Polpa de tomate
Guloso → Mercearia › Conservas* once and every past line and every future line
that resolves to that product is settled, on every invoice, forever. Were it
per line, the same product would be re-confirmed on every receipt for as long as
the household kept buying it — the work would never end, and it would grow with
the shopping, not shrink with the curation.

The button is a **bulk** affordance, not a separate mechanism: it promotes every
`AUTO` product on the receipt in front of you, which is the set a human has just
finished looking at. The same promotion is available one product at a time in
the catalogue.

## Consequences

- The grid marks each line with the state of its product's category — `!` for no
  product at all, `?` for a category nobody confirmed, `✓` once it is settled —
  so the button's effect is visible before and after pressing it.
- A receipt where every product is already `VALIDATED` or `MANUAL` gets nothing
  from the button, and that is correct: there is nothing left to confirm.
- `MANUAL` and `VALIDATED` are deliberately distinct. Both mean a human decided,
  but one chose the category outright and the other approved a machine's
  proposal. Collapsing them would lose the record of what the classifier got
  right, which is the only measure of whether it is improving.
