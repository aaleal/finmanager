# 0063 — A look-alike is a pair, and «not the same» is an answer

## Context

Three products were created by hand — «Batata Frita Azeite» under *Mercadona*,
*Continente* and *Lidl* — and the catalogue immediately raised **«Produtos a
fundir»** over all three, offering only one action per row: merge. There was no
way to say they were distinct, and merging is not cheap — `merge_products` moves
every `SupermarketReceiptItem` and `ProductAlias` onto the survivor and soft-
deletes the source.

The detector was grouping on `normalize_description(canonical_name)` and
discarding the brand it had just selected. That contradicts the identity rule
twice over:

- The identity key is `(canonical_name, brand)` (ADR-0015/0030), and ADR-0058
  restates that the brand stays *outside* the name precisely because it is
  already half of the key.
- `uq_master_products_canonical_name_brand` makes a true duplicate of the pair
  impossible, so **a group whose members have different brands can never be a
  duplicate**. Every such warning was a false positive by construction, and the
  only offered exit destroyed a legitimate row.

Two designs were considered for the missing "no" answer: dismissing the shared
*name*, or dismissing the *set of products*. Dismissing the name is one row and
one lookup, but it silences the question permanently — a genuine misspelling
created next month inherits an answer given about a different pair.

## Decision

- `merge_candidates` groups on the **identity key itself**, `(name, brand)` both
  normalized. What survives is the case worth flagging: one brand, two spellings
  the unique index does not catch — «Batata Frita Azeite» beside «BATATA-FRITA
  AZEITE».
- A group can be **dismissed**: `POST /master-products/merge-candidates/dismiss`
  records the group in `product_merge_dismissals` and it stops being listed.
  Nothing is written to the products themselves.
- The dismissal is keyed by the **exact set of product ids**, sorted, with a
  unique index on the array. A fourth look-alike joining the group produces a
  different set, so the question is asked again rather than inherited.
- The group now carries `presentation` and `conservation` per row, so the human
  answering can see what the shared name is hiding.

## Consequences

- **No data migration and no backfill.** The change is to what is *listed*;
  existing products are untouched. Groups already merged by hand stay merged —
  that is a reassignment of receipt lines, not a flag.
- `product_merge_dismissals` has **no foreign key** to `master_products`. A
  member that is later merged away leaves a row that can never match again, and
  nothing prunes it. The alternative — cascading — would silently re-raise a
  question already answered about the surviving pair.
- Dismissals are household-level reference data like the catalogue itself
  (ADR-0019), not entity-scoped: the answer "these are different products" is
  true for whoever shops.
- `merge_candidate_count` feeds the status panel, so a dismissed group also
  stops counting as pending work — which is the point. The counter can now
  reach zero.
- The detector no longer catches a product filed under the wrong brand (say a
  `NULL` brand beside the same name with a brand filled in). That is a
  completeness problem, not a duplicate, and belongs to the attribute backlog
  ADR-0059 describes.
