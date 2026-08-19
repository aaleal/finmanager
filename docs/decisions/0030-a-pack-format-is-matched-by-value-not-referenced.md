# 0030 — A pack format is matched by value, not referenced

## Context

Decision #15 says a 500 g and a 1 kg bag of the same coffee are **one** product;
what varies is the weight, and that is what makes €/kg comparable across them.
`MasterProduct.pack_variants` holds those formats as a JSONB list.

Once the review grid started asking *«is the 500 g this line printed already a
format of this product?»*, the obvious next step was to give each format an
identity — a `product_pack_variants` table and a `receipt_items.pack_variant_id`
foreign key — so a line could point at the format it means.

## Decision

No table, no foreign key. `pack_variants` stays a JSONB list on the product and
a line finds its format **by value**, comparing `weight_listed_kg` against the
product's weights after both sides round to the gram
(`products_service.round_to_the_gram`, `WEIGHT_QUANTUM = 0.001`).

Three properties make that work:

1. **Weights are unique per product.** `sanitize_pack_variants` refuses a
   repeated weight, so "which format is this line?" always has exactly one
   answer and needs no reference to disambiguate it.
2. **Both sides pass through the same funnel.** A `500G` token parsed off a till
   and a `0,5` typed by hand quantize to the same `Decimal`, so they compare as
   equals.
3. **The line keeps its own weight.** `weight_listed_kg` is the frozen fact of
   what was bought; `pack_variants` is the catalogue of what the product ships
   in. Editing a format never rewrites the past.

The format is only ever a **vocabulary for validation and standardisation** —
nothing groups, filters or charts by it. A table would have bought referential
integrity for a dimension nobody queries.

## Consequences

- Weights are stored as **strings** inside the JSONB. JSON has no decimal type,
  and the engine has no custom `json_serializer`, so a `Decimal` written there
  raises `TypeError` and a JSON number would silently become an IEEE-754 float —
  intolerable for a figure that divides a price.
- Appending a format is `POST /master-products/{id}/pack-variants`, idempotent
  on the weight, rather than a read-modify-write of the whole list: the review
  pane can add the format it just read off a line without knowing the others,
  and two people reviewing at once cannot drop each other's work.
- A shrunk pack **joins** the list instead of replacing the old entry. 500 g →
  450 g is the shrinkflation signal; overwriting would erase the very thing the
  module exists to notice. The signal itself still comes from
  `product_price_history`, which freezes its own weight per observation
  (ADR-0022).
- `ReceiptItemOut.pack_weight_is_known` is `bool | None`, where `None` means the
  question does not apply — no product, no listed weight, or sold by weight,
  where the scale answers and no format exists.
- The cost is that decimal rigour inside the blob is hand-maintained rather than
  enforced by `NUMERIC`. Accepted deliberately: the alternative was a table for
  a dimension that is never a dimension.
