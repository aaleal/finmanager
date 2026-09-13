# `data/` — the household's own files

Everything here is **yours**, not the product's: it is mounted into the API at
`/var/lib/finmanager/defaults`, never committed, and never baked into the image.
Replacing a file is dropping a newer one in — no rebuild, no migration, no code
change. Every path is optional; one that is missing means "nothing to load yet",
never an error.

The API only ever *reads* these (the mount is `:ro`). What ends up in the
database is a copy, so editing a file afterwards changes nothing already loaded —
press the corresponding button again, or run `./fm seed`.

```
data/
  supermarket/
    products.xlsx      # the catalogue — built by dev/build-product-seed.py
    categories.xlsx    # your edit of the taxonomy, on top of the shipped one
    invoices/          # real talões (.pdf/.jpg/.jpeg/.png), ingested as uploads
  lego/
    inventory.json     # the collection
    images/<set>/box.jpg, alt1.jpg…   # fetched by dev/download-lego-images.py
```

## Loading it

| File | Button | Command |
| --- | --- | --- |
| `supermarket/categories.xlsx` | Categorias › «Carregar categorias por defeito» | `./fm seed` |
| `supermarket/products.xlsx` | Produtos › «Carregar produtos por defeito» | `./fm seed` |
| `supermarket/invoices/` | Talões › «Carregar faturas por defeito» | `./fm seed` |
| `lego/` | Coleção › «Importar em lote» | `./fm seed` |

All of them are additive and safe to run twice: products dedupe on
(name, brand), invoices on content hash per entity, categories on `code_en`,
LEGO sets on set number per entity.

## What is *not* here

- **Reference data** — the grocery taxonomy this release ships, the product
  attribute vocabulary, the merchants and parser profiles. Same for every
  install, so it is packaged: `apps/api/app/data/` and
  `app/services/reference_data.py` (ADR-0029).
- **Demo data** — the invented LEGO sets and the one hand-written receipt that
  make the screens legible before you have loaded anything. Committed, in
  `apps/api/app/demo/data/`.
