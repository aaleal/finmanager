# 0057 — The grocery taxonomy loads on demand, not at boot

## Context

ADR-0029 moved the grocery taxonomy out of the seed and into
`app.services.reference_data.ensure_categories()`, run from every API boot
alongside the merchants and the parser profiles. That solved the "clean
database cannot file a product" problem, but it also means the ~500-node
taxonomy is silently (re)written into every installation's database on every
restart, whether the household wants exactly that taxonomy or not. The
taxonomy is data a household may reasonably want to start from empty and
build up from the shipped file at its own pace, not have imposed on first
boot.

## Decision

`ensure_categories()` is no longer called from `ensure_all()`. Merchants and
parser profiles still are — nothing changes for them, they remain true
boot-time reference data.

The taxonomy itself still ships with the release, unchanged, as the
human-editable `apps/api/app/data/supermarket-categories.pt-PT.json`. Loading
it into the database is now an explicit action:

- A new endpoint, `POST /api/categories/defaults/load`
  (`load_default_categories` in `app/api/routers/products.py`), calls
  `reference_data.ensure_categories()` on request. It is additive and
  re-run-safe, the same contract `ensure_categories()` always had.
- The categories tab (`CategoriesPanel`, `apps/web/src/features/supermarket/categories-panel.tsx`)
  shows this action in its empty state: when the GROCERY tree has zero nodes,
  the household sees "Pretende fazer loading das categorias por defeito?"
  with a button that calls the endpoint above, instead of the table simply
  never being empty.
- `make seed` still loads the taxonomy, explicitly, as its own step (not
  through `ensure_all()`) — the demo dataset ships with categorised products,
  a real installation does not until asked.

## Consequences

- A fresh installation now has a genuinely empty categories table until the
  household presses "Carregar categorias por defeito" — first-run setup
  (ADR-0011) does not implicitly decide this for them.
- The taxonomy file is still where a human edits it to change what "default"
  means for their installation; nothing about that file or its lookup path
  changed.
- Boot no longer touches the `categories` table at all; one less write path
  to reason about when diagnosing what changed a household's taxonomy.
- Existing installations that already loaded the taxonomy under ADR-0029 are
  unaffected — the rows are already there, and `ensure_categories()` is still
  additive-only if pressed again after editing the JSON file for a new
  release.
