# Supermarket products feature — quick context

Purpose: fast orientation for anyone (human or agent) picking up work on the
supermarket product catalogue without re-deriving the model from scratch. See
`docs/decisions/` (ADR numbers referenced below) for the full reasoning.

## The model in one paragraph

`MasterProduct` IS the product AND the SKU. Identity = `(canonical_name, brand)`
(partial unique index, `is_deleted=false`). `Category` L1/L2/L3 is a TAXONOMY —
`Category` L3 is NOT the product. The cut/format live inside `canonical_name`,
so «Amêndoa Laminada» and «Amêndoa Palitada» are already two products filed
under the same L3. Ancestors are denormalised on the product
(`category_l1_id/l2_id/l3_id`, ADR-0020). Catalogue is household-wide, never
entity-scoped (ADR-0019).

## Three rules that must not be regressed

1. **Quantity/pack size is NOT identity** (ADR-0015/0030). `pack_variants` is a
   JSONB list keyed by unique weight, matched by value at the gram. Making
   weight part of the SKU silently zeroes `shrinkflation()` forever — it reads
   weight variation *within* a product.
2. **Cut is NOT identity either** (ADR-0058). `presentation` is a queryable
   duplicate of what the name already says. Proof it can't be otherwise:
   `catalogue._candidates()` selects only `canonical_name` + `brand`, so the
   resolver can never see `presentation`; with only «Amêndoa» in the catalogue
   both cut lines score an identical 0.75.
3. **An unfilled attribute is "por indicar", never an error** (ADR-0035/0059).

## Where things are

| What | Path |
|---|---|
| Model | `apps/api/app/models/products.py` |
| Product CRUD, bulk import, categories | `apps/api/app/services/supermarket/products_service.py` |
| Attribute vocabulary (enforced) | `apps/api/app/services/supermarket/attributes.py` + `app/data/supermarket-product-attributes.pt-PT.json` |
| Resolver (line -> product) | `.../catalogue.py` (fuzzy, AUTO 0.78 / review 0.70) |
| Category classifier | `.../classify.py` (`0.65*product + 0.35*section`) |
| Analytics | `.../prices_service.py` (`category_spend(dimension=…)`, `dietary_spend`) |
| On-demand defaults (products/invoices) | `apps/api/app/services/supermarket/defaults.py` |
| Routers | `app/api/routers/{products,prices,supermarket}.py` |
| Frontend | `apps/web/src/features/supermarket/` (`product-attributes.tsx` is the shared field block) |
| Seed script | `apps/api/app/seed/__init__.py` (`./fm demo` / `./fm seed`) |
| Seed builder (workbook -> catalogue) | `dev/build-product-seed.py` |

## Attributes shipped (Fase 1+2)

`is_own_brand` (manual bool), `conservation` (VARCHAR+CHECK, closed set),
`presentation` (VARCHAR, no CHECK — service-layer dictionary),
`dietary_attributes` (JSONB + GIN). Migration `b7d3e91c4a58`.
Vocabulary served at `GET /api/master-products/attributes` — registered BEFORE
`/{product_id}` (a static-vs-`/{id}` route collision gives a 422, not a 404).

## Defaults are buttons, not just a script (ADR-0061)

Three on-demand loaders, all in `app/services/supermarket/defaults.py`, each
idempotent, each also called by `make seed` / `./fm demo`:

- **Categories** — `POST /categories/defaults/load` (ADR-0057, pre-existing).
- **Products** — `POST /master-products/defaults/load` — reads `PRODUCTS_FILE`
  (`app/data/supermarket-products.pt-PT.xlsx`, optional, gitignored), calls
  `ensure_categories()` first (otherwise most rows fail category resolution),
  then the real bulk importer.
- **Invoices** — `POST /supermarket/defaults/load` — ingests `INVOICES_DIR`
  (`app/seed/data/invoices`, the 11 real *talões*, ADR-0027, publicly tracked)
  via `create_from_upload`, deduplicated by content hash per entity.

Frontend buttons: empty-state in `ProductsPanel` (products), `ReceiptsTable`'s
`emptyAction` prop wired in `supermercado.tsx` (invoices) — both gated on "no
filters applied", mirroring `CategoriesPanel`'s existing pattern.
`app.seed.INVOICES_DIR` / `PRODUCTS_FILE` are re-exports from `defaults.py`
(tests import `from app.seed import INVOICES_DIR`, kept working).
`./fm demo` / `make demo` is an alias for `./fm seed` (the full one-shot loader).

Bug found and fixed along the way: `purge_products()` didn't delete
`ProductPriceHistory` rows before deleting `MasterProduct` → raw
`IntegrityError` (the FK is `NOT NULL`, no `ondelete`). Fixed by deleting price
history rows for the purged ids too, before deleting the products.

## Still open

- Price series **above** a product (one curve per L3, all cuts together) does
  not exist. `price_history()` takes a scalar `master_product_id`; there is no
  cross-product series anywhere. New endpoint, not a `GROUP BY`.
- Fase 3 (per-N3 attribute template / EAV) deferred. Material already exists:
  sheet `Categorias_Storage` in the household's `categorias-*.xlsx` has
  obrig./opcional attributes + synonyms per N3.
- Changing an attribute relabels ALL past price history (no snapshot on
  `ProductPriceHistory`). Documented in ADR-0058, not fixed.
- `reference_data.BRAND_AXIS_L2` still names "Pastilhas", gone from the v2 taxonomy.

## Environment gotchas

- `podman exec ... python /tmp/x.py` needs `-e PYTHONPATH=/app`.
- `http_proxy` is set in this shell; use `curl --noproxy '*'` for localhost.
- Dev DB is normally empty (0 receipts) — panels look "missing" when they are
  only unpopulated. Run `./fm demo`.
- The test suite is run by the project owner, not by an agent, by convention.
