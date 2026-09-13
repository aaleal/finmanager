# 0058 — A cut is an axis of the product, not a second identity

## Context

Two lines off the same *talão* — `Amendoa laminada 200g` and
`Amendoa palitada 200g` — are obviously not the same article, and the question
came up whether the household's model can tell them apart, and whether the new
`presentation` attribute is what does it.

There are two "Amêndoa" in the model and conflating them is the whole source of
the confusion. `Category` level 3 (`Amêndoas`, under `Aperitivos › Frutos secos`)
is a **taxonomy node**. `MasterProduct.canonical_name` is a **product**. Nothing
requires — or wants — a single `MasterProduct` called "Amêndoa" that both lines
resolve to.

So the two designs on the table were:

- **A** — the name carries the cut: `«Amêndoa Laminada»` and `«Amêndoa Palitada»`
  are two products, both filed under the same L3, and `presentation` is a
  structured annotation beside the name.
- **B** — the name is the genus: one product `«Amêndoa»`, with `presentation`
  doing the distinguishing, and therefore part of the identity key.

Design B was measured against the real resolver before being rejected:

| catalogue | `Amendoa laminada 200g` | `Amendoa palitada 200g` |
| --- | --- | --- |
| A — name carries the cut | «Amendoa Laminada» **0.93 → AUTO** | «Amendoa Palitada» **0.93 → AUTO** |
| B — name is the genus | «Amendoa» 0.75 → REVIEW | «Amendoa» 0.75 → REVIEW |

Under B the two lines produce the *identical* score against the *identical*
candidate. `catalogue._candidates()` loads only `canonical_name` and `brand`, so
the matcher never sees `presentation` — the words "laminada" and "palitada" stop
being signal and become noise. B is also already refused by the code:
`create_product` answers `409: Já existe um produto com este nome e marca.`

## Decision

Design A. `presentation` and `conservation` are **columns on `MasterProduct`,
outside its identity key**, which stays `(canonical_name, brand)` as ADR-0015 and
ADR-0030 left it.

They are deliberately redundant with the name. The name is free text — «Amêndoa
Laminada», «AMEND. LAM.», «Amendoa laminada 200g» are one thing and no database
groups them. The column is the controlled-vocabulary version of what the name
already says, and it is the only one a `GROUP BY` can reach.

That redundancy is what buys both views at once: spend and €/kg aggregated over
the L3 «Amêndoas» (every cut together), and the same figures decomposed by
`GROUP BY presentation` (laminada apart from palitada) — which matters because a
cut carries its own processing cost, so averaging the two produces a €/kg that
describes no purchase anyone made.

`conservation` keeps a CHECK constraint; `presentation` deliberately does not.
See ADR-0059.

## Consequences

- **No data migration.** Cuts were already separate `MasterProduct` rows, because
  the cut has always lived inside `canonical_name`. Annotating them is a backlog,
  not a merge — which is why the bulk import grew the columns too.
- `pack_variants` could never have expressed this anyway: `sanitize_pack_variants`
  refuses a repeated weight, so two 200 g cuts of one product raise
  `ValidationError` by construction.
- `shrinkflation()` is untouched. It groups by `(master_product_id, merchant_id)`
  and reads variation in `weight_kg` *within* a product; keeping quantity and cut
  out of the identity is exactly what keeps that signal alive.
- **Changing an attribute rewrites the past.** `ProductPriceHistory` snapshots
  weight, prices and `is_fs`, but no product attribute — so a series is always
  labelled by the product's *current* cut. Correcting a misfiled product
  retroactively relabels its whole history, which is right for a correction and
  indistinguishable from a product that genuinely changed. Only worth knowing if
  a price series shows an unexplained break.
- Aggregating a price *series* across the products of one L3 is still not
  possible: `price_history()` takes a single `master_product_id` and there is no
  cross-product series anywhere. That is a separate feature, not a `GROUP BY`.
