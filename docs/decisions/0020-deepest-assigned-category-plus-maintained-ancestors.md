# 0020 — Deepest assigned category, plus maintained ancestors

## Context

The taxonomy is nominally three-tier, but the household's own sheet fills L1
on 100 % of rows, L2 on 81.6 % and L3 on 52.9 %. Modelling only
`category_l3_id` would make an L2-only assignment look like a gap rather than
an answer it genuinely is. Three shapes were available: snapshot the full
`(l1, l2, l3)` triple on every row, derive ancestors on every read by walking
`parent_id`, or store the deepest assigned node and maintain the rest.

## Decision

One authoritative `category_id` — the deepest **assigned** node, at any level
— plus a maintained `category_l1_id` / `category_l2_id` / `category_l3_id`
trio, recomputed whenever a category is reparented or merged.

## Consequences

- "Spend by L2" is a single-table group-by with no recursive join, and it can
  never mix two taxonomies the way a per-row snapshot would silently drift
  into over time.
- A reparent rewrites thousands of *product* rows in one audited transaction,
  never the millions of receipt lines that reference them.
- Renaming a category costs nothing at all, because every row references it
  by id.
- The API field is `category_id`, not the `category_l3_id` the module sketch
  used, because the deepest assigned level is not always three.
