# 0061 — Every default is a button, not just a script

## Context

ADR-0057 gave the grocery taxonomy an on-demand loader: a button in the empty
category tree, calling `POST /categories/defaults/load`, safe to press more
than once. ADR-0060 then added a second default — the household's own product
catalogue — but only through `make seed`, the all-or-nothing script that also
creates the household, the demo LEGO collection and a synthetic receipt.

That left the supermarket module with three different kinds of default data
and one way to load any of them without a script: categories had a button;
products and invoices did not. A household that only wanted its own real
catalogue, without the demo LEGO sets or the synthetic receipt, had no route to
it except reading `app.seed.main()` and calling the right function by hand.

## Decision

**Every default the supermarket module ships is loaded the same way categories
already are**: a small, idempotent, Writer-only endpoint, triggered by a button
in the screen that is empty, calling the same function `make seed`/`./fm demo`
calls. Three defaults, three buttons:

| Default | Endpoint | Button lives in |
|---|---|---|
| Grocery taxonomy | `POST /categories/defaults/load` (ADR-0057, unchanged) | Categorias tab, empty tree |
| Product catalogue | `POST /master-products/defaults/load` | Produtos tab, empty catalogue |
| Real invoices | `POST /supermarket/defaults/load` | Faturas tab, empty list (no filters applied) |

The product and invoice loaders live in one new module,
`app/services/supermarket/defaults.py`, which owns the two file paths
(`PRODUCTS_FILE`, `INVOICES_DIR`) and the two loading functions. `app/seed`
imports both rather than duplicating them — `app.seed.INVOICES_DIR` is kept as
a re-export because the parser tests and `regenerate_golden.py` already import
it from there (ADR-0027) and that contract does not change.

Loading products **ensures the taxonomy first**. A category path the bulk
importer cannot resolve is an *error* on that row
(`"Categoria não encontrada."`), not a silent skip — so a household that
presses "carregar produtos" before ever pressing "carregar categorias" would
otherwise watch almost every row fail instead of importing uncategorised.
`ensure_categories()` is additive and idempotent (ADR-0057), so calling it a
second time from a different button costs nothing.

Invoices are deduplicated **by content hash per entity**
(`create_from_upload`'s existing contract), keyed
`defaults:invoices:{entity_id}:{filename}` — not by a shared "seed" key —
so two different entities in the same household each get their own copy of
the same eleven invoices, and pressing the button twice for one entity ingests
nothing twice.

`make seed` / `./fm demo` remain the one-shot script for a full demo
installation — settings, reference data, taxonomy, catalogue, tags, the
synthetic receipt, the real invoices, the LEGO collection — and now call
exactly the same three functions the buttons do. `./fm seed` is kept as the
existing name; `./fm demo` is a plain alias, because "load everything for a
demo" reads better than "seed" to someone who has never used this command
before.

## Consequences

- Fixed a real bug surfaced by testing this: `purge_products()` deleted
  `MasterProduct` rows without first deleting their `ProductPriceHistory` rows,
  which have a `NOT NULL` foreign key with no `ON DELETE` rule — purging a
  catalogue that had ever recorded a price observation raised a raw
  `IntegrityError`. Price history has no "unlinked" state the way a receipt
  line does (`master_product_id` cannot be `NULL`), so it is deleted outright
  alongside the product, not orphaned.
- Pressing "carregar produtos" implicitly loads the taxonomy too. That is a
  deliberate asymmetry: the categories button stays available on its own for a
  household that wants only the taxonomy, but the products button does not
  make a household discover the ordering dependency by watching an import
  fail.
- The three buttons and the one-shot script are now, permanently, the same
  code path. A future default (say, merchants or parser profiles beyond what
  boot already ensures) should be added to `defaults.py` and wired into both
  places, not bolted onto `app/seed` alone.
