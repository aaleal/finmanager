# 0060 — Source material is private, seed data is derived and hand-editable

## Context

Three folders were quietly doing different jobs and one of them was doing the
wrong one:

- `00.prompts/seed/` held the household's **original material** — the
  `GestaoCasa` workbook with five years of shopping, the taxonomy workbook, the
  LEGO inventory, the original invoice PDFs. Personal, and useful only as a
  source to derive from.
- `apps/api/app/data/` holds **reference data that ships with the release**
  (ADR-0029): the grocery taxonomy and the attribute vocabulary.
- `apps/api/app/seed/data/` holds the **demo fixtures** `make seed` ingests, and
  the parser tests read the invoices from here (ADR-0027).

Two problems. First, `00.prompts/seed/` was **tracked**, so the household's real
shopping, real invoices and real LEGO inventory were pushed to a remote — the
`.gitignore` rules covering it had no effect, because ignore rules do nothing
for files already in the index. Second, there was no way to say *"this is the
catalogue my installation should start with"*: the only route into the product
catalogue was a human driving the bulk import dialog.

## Decision

**Source material is never tracked.** `00.prompts/seed/` is the household's own
archive: originals, kept locally, read by nothing at runtime. It is the place to
drop a new export and the place to look when asking "where did this come from?".

**Seed data is derived from it, by a committed script.** `dev/build-product-seed.py`
turns the year sheets into `supermarket-products.pt-PT.xlsx`. The script is in
git; its input and output are not. Anyone can see *how* the catalogue was built
without seeing *what* this household buys.

**Derived seed data is a plain workbook, edited by hand.** It lands in
`apps/api/app/data/` beside the other reference data and `make seed` loads it
through `seed_products()` — which calls the very same
`preview_product_import` / `commit_product_import` the UI's bulk import calls.
A row the seed accepts is a row the dialog would accept; there is no private
writer that could drift from the real contract.

The file is **optional**. Absent, the step reports itself skipped and the seed
continues, so a clone with no household data still seeds cleanly.

One category level per column (`Cat1`, `Cat2`, `Cat3`), not a single
`L1 › L2 › L3` cell. The importer reads both, but only one of them can be fixed
in Excel without editing a string by hand.

## Consequences

- The grocery taxonomy shipped in
  `apps/api/app/data/supermarket-categories.pt-PT.json` was regenerated from the
  household's current taxonomy workbook: **v1.0.0 (27/170/623) → v2.0.0
  (28/133/383)**. It is a restructure, not a respelling — `Laticinios` became
  `Laticínios & Ovos`, `Saúde & Higiene` became `Higiene & Beleza`. Because
  `ensure_categories()` matches on `code_en` and is additive, an existing
  database keeps its old nodes and gains the new ones side by side; a household
  that wants only the new tree purges the taxonomy first (ADR-0053's pattern).
- `reference_data.BRAND_AXIS_L2` still names `Pastilhas`, which is no longer an
  L2 in the new tree. Harmless — the flag simply never applies — but it is now
  dead configuration.
- Untracking `00.prompts/seed/` removes it from the working tree's index only.
  **The files remain in history**, which is a separate problem with a separate
  and destructive remedy.
- `apps/api/app/seed/data/` stays tracked on purpose. ADR-0027 put the eleven
  real invoices there precisely so the demo and the parser tests could not
  drift, and untracking them breaks `make seed` and the integration suite on a
  fresh clone. That trade — privacy against a working demo — is deliberately
  left where ADR-0027 left it.
