# Database

PostgreSQL 16, one database per deployment, migrated with Alembic. Everything runs
inside containers — there is no `psql` on the host.

## Opening a shell

```bash
make shell-db        # psql inside the db container
```

Or use the containerised GUI that ships with the dev stack:

```bash
make dev             # then open http://localhost:8081
# System: PostgreSQL · Server: db · User/Password/Database from .env
```

Ad-hoc query without an interactive shell:

```bash
docker compose exec -T db psql -U finmanager -d finmanager \
  -c "SELECT ownership_status, count(*) FROM lego_set_instances GROUP BY 1;"
```

## Conventions

| Rule | Why |
|---|---|
| **UUID v7** primary keys, generated in Python (`app/core/ids.py`) | Time-sortable without a sequence, safe to expose |
| **`NUMERIC(10,2)`** for every `_eur` column | Money is decimal; floats and minor-unit integers are both banned |
| **`is_deleted` + `deleted_at`** soft delete | Financial history is voided, never destroyed |
| **`created_at` / `updated_at`** with `timestamptz` | Store UTC; business dates keep their local calendar date |
| Evolving public enums as `VARCHAR` + `CHECK` | Adding a value is a one-line migration, not a type rewrite |
| Naming convention on every constraint (`app/models/base.py`) | Alembic autogenerate produces stable, reviewable diffs |

### Adding or changing a `VARCHAR`+`CHECK` enum value

Why these are plain `VARCHAR` + `CHECK` instead of a Postgres `ENUM`, or a
lookup table managed through its own screen, is explained in
[ADR-0003](decisions/0003-varchar-check-over-postgres-enum.md) — short version:
none of these values need attributes of their own (an ordering, a colour), so
a lookup table would be solving a problem this app doesn't have. The
allow-list is intentionally duplicated across layers, each rejecting a bad
value on its own; keep every copy in sync by hand — there is no single place
that generates the rest.

Checklist, per enum column (`build_state`/`condition`/`acquisition_source`/…):

1. **`app/models/<module>.py`** — the module-level tuple (e.g. `BUILD_STATES`)
   and the named `CheckConstraint` on the table.
2. **`app/schemas/<module>.py`** — the matching Pydantic `Literal` type.
3. **`app/services/<module>_export.py`** (if the module has one) — the PT
   label dict (`BUILD_STATE_PT`, …). Anything a bulk importer reverses for
   spreadsheet labels reads from here, so this is often the only place a
   label needs to change.
4. **`apps/web/src/features/<module>/constants.ts`** — the label / badge
   variant map the UI renders from.
5. **`apps/web/src/api/schema.d.ts`** — the hand-edited literal union(s) for
   that field (several sites per field is normal). A real `make types-gen`
   regenerates this properly once the backend is rebuilt; hand-edit only as a
   stopgap (see `docs/debugging.md` if `types-gen` can't reach a running API).
6. **An Alembic migration** — `op.drop_constraint` + `op.create_check_constraint`
   for the `CHECK`. If you're **removing** a value rather than just adding
   one, the migration must also **data-migrate existing rows away from it in
   the same `upgrade()`**, before narrowing the constraint — narrowing first
   rejects the very rows you're trying to fix. Write the `downgrade()` too,
   even when it's lossy (document what it can't recover, in a one-line
   comment, rather than pretending it round-trips).
7. Seed data / fixtures (`app/seed/__init__.py`, integration test fixtures)
   using a removed value.

Adding a brand-new value (nothing removed) only ever needs steps 1–5 plus a
constraint-widening migration — no data migration, since no existing row can
already hold a value that didn't exist yet. See
`20260902_0900-d3a7f6c2e814_lego_acquisition_source_gains_fs.py` for that
smaller case, and `20260903_0900-b2d4e8f61a37_lego_sealed_moves_to_condition.py`
for a value moving from one enum to another (the harder, data-migrating case).

## Schema map

### Shared core (`app/models/core.py`) — brief §1a

| Table | Purpose |
|---|---|
| `merchants` | Global reference data (`RETAIL`/`BANK`/`INSURER`/…), validated Portuguese NIF |
| `categories` | Hierarchy with `parent.domain == child.domain` and `level==1 ⇔ parent_id IS NULL`; grocery is 3-tier and seeded from the pt-PT taxonomy |
| `tags` | Household-scoped cross-cutting labels |
| `documents` | Content-addressed attachments; `storage_path` is outside any web root |
| `links` | **Polymorphic** reconciliation edges — no real FKs; compensated by `(from_type, from_id)` / `(to_type, to_id)` indexes and an app-level type allow-list |
| `review_tasks` | Backs the shared Review Queue |
| `audit_logs` | Every financial mutation and lifecycle change; the sole source of historical state |
| `settings` | Confidence thresholds and provider opt-ins, scoped `GLOBAL`/`HOUSEHOLD`/`ENTITY`/`MODULE` |
| `import_batches`, `processing_jobs` | Ingestion bookkeeping; `processing_jobs.idempotency_key` is unique so retries never double-apply |

### Household (M7, `app/models/household.py`)

`households` · `users` · `household_members` · `entities` · `sessions` — five tables,
three roles, no per-entity read isolation. `users.is_dependent = true` implies
`password_hash IS NULL`, enforced by a `CHECK`.

### LEGO (M9, `app/models/lego.py`)

Three tables, deliberately:

- `lego_set_models` — catalog identity plus the single hand-maintained
  `current_value_eur` / `value_updated_at`. A **partial unique index** enforces one
  set number per entity while the row is alive and has a number, so soft-deleted rows
  and MOCs do not collide.
- `lego_set_instances` — one row per physical copy; there is no `quantity`.
  `acquisition_transaction_id` is a plain UUID column, not an FK — see
  [ADR 0005](decisions/0005-defer-transaction-fk.md).
- `lego_storage_locations` — flat `area` + `container`, household-level
  reference data rather than entity-scoped (see
  [ADR 0046](decisions/0046-storage-locations-are-shared-not-entity-scoped.md)),
  unique on `(area, container)`, `capacity_pct` constrained to 0–100.

There is **no** valuation-history table, no image table and no external-listing
table. Value history is recoverable from `audit_logs`; images reuse `documents`;
marketplace links are built client-side from a template.

### Supermarket & receipts (M1, `app/models/supermarket.py` + `app/models/products.py`)

- `merchant_parser_profiles` — how one merchant's layout is read. A partial
  unique index, `uq_merchant_parser_profiles_generic` (`merchant_id`, where
  `merchant_id IS NULL AND is_deleted = false`), keeps the generic fallback
  single and undeletable — see [ADR 0016](decisions/0016-per-merchant-parsers-over-one-configurable-parser.md).
- `supermarket_receipts` — one payment transaction at one merchant. Two partial unique
  indexes prevent duplicates rather than merely detecting them: `uq_supermarket_receipts_entity_atcud`
  (`entity_id, atcud_code`, where `atcud_code IS NOT NULL AND is_deleted = false`)
  makes the fiscal document identity itself impossible to duplicate (see
  [ADR 0017](decisions/0017-fiscal-qr-is-the-highest-confidence-anchor.md)), and
  `uq_supermarket_receipts_entity_document` (`entity_id, document_id`, same `is_deleted`
  guard) stops one uploaded file from creating two receipts.
- `supermarket_receipt_items` — one row per printed line, or one appended Fs article. Two
  `CHECK` constraints enforce [ADR 0015](decisions/0015-fs-articles-are-appended-not-flagged.md)
  at the database level rather than in application code: `fs_pays_nothing`
  (`is_fs = false OR paid_price_eur = 0`) and `fs_has_no_document_fields`
  (`is_fs = false OR (line_no IS NULL AND merchant_section IS NULL AND
  iva_class_raw IS NULL)`) — nothing the *document* supplied can exist on a row
  the document never had. `master_product_id` was a plain nullable column with
  no FK in M1a; migration `baf648f645a8` (M1b) adds the deferred foreign key to
  `master_products.id` now that the table exists.
- `master_products` — canonical product identity, household-level reference
  data rather than entity-scoped (see [ADR 0019](decisions/0019-the-product-catalogue-is-shared-not-entity-scoped.md)).
  A partial unique index, `uq_master_products_canonical_name_brand`
  (`canonical_name, brand`, where `is_deleted = false`), stops two live products
  answering to the same name and brand. `category_id` is the deepest assigned
  category at any level, with `category_l1_id`/`_l2_id`/`_l3_id` maintained
  alongside it (see [ADR 0020](decisions/0020-deepest-assigned-category-plus-maintained-ancestors.md)).
  A `CHECK` constrains `category_status` to `AUTO`/`VALIDATED`/`MANUAL`, and
  another constrains `category_confidence` to `0`–`1`.
- `product_aliases` — learned merchant vocabulary. `UNIQUE (merchant_id,
  description_norm)` (`uq_product_aliases_merchant_description`) — one alias
  per merchant per normalised description — and a `CHECK` constrains
  `confidence` to `0`–`1`.
- `product_price_history` (M1c, `app/models/prices.py`) — one row per price
  observation, append-only (see
  [ADR 0022](decisions/0022-price-history-is-append-only-and-stores-no-quotient.md)).
  Indexed on `(master_product_id, merchant_id, observed_on)` for the €/kg and
  shrinkflation queries. The index on `source_receipt_item_id` is deliberately
  **not** unique: the table has no `UPDATE` path for a correction, so a review
  edit made after the observation was first frozen appends a new row beside
  the old one rather than replacing it, and idempotency instead comes from
  `record_observations()` skipping a row whose date, prices and weight are all
  unchanged. A `CHECK` constrains `weight_kg` to `NULL` or strictly positive.
  `list_price_eur`/`paid_price_eur` carry the notional value in both columns
  on an Fs observation, never `0.00` (see
  [ADR 0023](decisions/0023-fs-observations-carry-the-notional-value-in-both-price-columns.md)).
  There is no €/kg column and no shrinkflation-flag column: both are derived
  at query time from `list_price_eur`/`paid_price_eur` and `weight_kg`.

## Migrations

```bash
make revision M="add lego wishlist"   # autogenerate against the live schema
make migrate                          # upgrade head
make downgrade                        # roll back one revision
```

Migrations are **additive and reversible**. Every one has a real `downgrade()`.
`docker-entrypoint.sh` runs `alembic upgrade head` before the API starts, so a fresh
`docker compose up` always lands on a migrated schema.

Autogenerate needs the models imported — `alembic/env.py` imports `app.models`,
which re-exports every model, so a new table only needs to be added to
`app/models/__init__.py`.

## Performance notes

The indexes that matter today:

- `ix_lego_set_instances_entity_status (entity_id, ownership_status, is_deleted)` —
  the shape of every collection listing and KPI aggregate.
- `ix_lego_set_instances_model_id` — copy grouping and `owned_copies_count`.
- `ix_audit_logs_record (table_name, record_id, created_at)` — reconstructing an
  object's history.
- `ix_supermarket_receipts_entity_purchase_date_id (entity_id, purchase_date, id)` — the shape
  of every receipt list and dashboard query.
- `ix_supermarket_receipt_items_receipt_id_line_no`, `ix_supermarket_receipt_items_master_product_id` —
  category spend joins through the product, which is a small table.
- `ix_master_products_category_l1_id_l2_id_l3_id` — spend grouped by any level
  without a recursive join (see ADR-0020).
- `ix_product_price_history_product_merchant_observed` — the €/kg series and the
  shrinkflation window. `is_fs` lives on the row itself, so the `fs` filter never
  forces a join back to `supermarket_receipt_items`.

### What has actually been measured

Measured with `EXPLAIN (ANALYZE, BUFFERS)` after `ANALYZE`, against **one year of
real household data** — 276 receipts, 2,406 lines, 1,494 products, 2,386 price
observations, produced by importing the real 2025 spreadsheet:

| Query | Execution time |
| :--- | ---: |
| Receipt list, one entity, newest 25 | 0.25 ms |
| Line-level explorer, newest 50 across all invoices | 2.24 ms |
| Category spend grouped by L1 | 2.21 ms |
| Price observations in the 12-month shrinkflation window | 0.47 ms |

At this size the planner prefers sequential scans over the indexes above, which is
correct — the tables fit comfortably in a few pages, and an index lookup would cost
more than reading them. The indexes are there for the shape the data takes later.

**The NFR is <800 ms p95 over ten years of data, and that has not been measured.**
Doing so needs a synthetic ten-year seed that does not exist yet. What is recorded
above is the honest one-year figure; treat the ten-year claim as open until a
production-scale seed exists to run it against.

When the ledger arrives, validate the reconciliation queries the same way rather
than assuming.
