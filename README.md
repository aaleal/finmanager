# FinManager

Self-hosted, privacy-first household finance platform for a Portuguese household
(**pt-PT**, **EUR**, `Europe/Lisbon`). Everything runs on your own hardware — a
Synology DS920+ or any machine with Docker — and nothing leaves the LAN unless you
explicitly switch on an external provider.

The product exists to **automate**: data arrives from messy sources (receipt photos,
bank exports, utility PDFs), the system parses, categorises and reconciles it,
auto-accepts what it is confident about and routes only the uncertain remainder to a
human **Review Queue**. Every automated decision is explainable and reversible.

## What is built today

| Phase | Module | Status |
|---|---|---|
| 0 | Foundation — shared core domain, auth, RBAC, entities, audit log, Review Queue shell | ✅ shipped |
| 0 | **M7** Household & user management | ✅ shipped |
| 1 | **M9** LEGO Collection Catalog | ✅ shipped |
| 2 | M2 Banking ledger | ⏳ next |
| 3 | **M1** Supermarket & Receipt Processing | ✅ shipped (M1a/M1b/M1c — ingest, review, catalogue, prices & loyalty) |
| 4 | M3–M5 Health, Utilities, Vehicles | ⏳ |
| 5 | M6 Assets & net worth | ⏳ |
| 6 | M8 Dashboards & PWA polish | ⏳ |

The navigation shows the pending modules greyed out, so the shape of the finished
product is visible from day one.

## Prerequisites

**Docker and Docker Compose. Nothing else.** No Python, Node, Postgres or Redis is
ever installed on the host — every command below runs inside a container.

> Podman works too: the `Makefile` auto-detects `docker compose`, `docker-compose`
> and `podman-compose`, in that order.

## Start the stack

```bash
cp .env.example .env          # then edit SECRET_KEY and POSTGRES_PASSWORD
docker compose up -d          # that's genuinely all it takes
```

The API container runs `alembic upgrade head` before starting, so a plain
`docker compose up -d` always lands on a fully migrated schema — there is no
separate migration step to remember. `make up` (or `./fm up`) does the same thing
and additionally creates `.env` for you if it is missing:

```bash
make up                       # = ensure .env + docker compose up --build -d
```

Open **http://localhost:8080**. A clean installation has no users and no default
password: the first screen asks you to name the household and create its owner,
signs you in, and then closes that route permanently
([ADR-0011](docs/decisions/0011-first-run-setup-over-seeded-credentials.md)).

```bash
make seed                     # optional: deterministic Portuguese demo data
```

The demo dataset is a **developer convenience**, not an installation step. It
creates no users: it attaches reference data and the LEGO collection to the
household and entity you just created, and refuses to run before you have. Set
images ship pre-downloaded in the repo, so seeding never touches the network.

It also loads the household's **eleven real invoices** — four Continente, four
Pingo Doce, two Lidl and one photographed Piquete *talão* — through the ordinary
upload path, so each arrives with its stored PDF, the parser profile that read
it, a visible confidence and a working «Reprocessar»
([ADR-0027](docs/decisions/0027-real-invoices-are-seed-data.md)). Alongside them
it seeds one hand-written receipt carrying an appended Fs article, a prorated
loyalty discount, a refund and a deposit return together, so the Fs arithmetic on
the Supermercado tabs is visible immediately, without importing anything.

Forgotten a password? An owner can set any member's from **Agregado**. If the
owner's own password is the one lost, there is no email recovery — use the host:

```bash
make passwd EMAIL=ana@exemplo.pt      # or: ./fm passwd ana@exemplo.pt
```

### Development stack (hot reload)

```bash
make dev
```

| Service | URL | Notes |
|---|---|---|
| Web app | http://localhost:8080 | Vite dev server, HMR |
| API docs | http://localhost:8000/api/docs | OpenAPI / Swagger UI |
| Adminer | http://localhost:8081 | Database GUI (server `db`) |

In production (`make up`) the web container **is** Caddy: it serves the built SPA and
reverse-proxies `/api/*` to the API container, so only port 8080 is exposed.

## Everyday commands

```bash
make help                 # list every target
make check                # lint + types + tests, both apps — the only quality gate
make logs S=api           # follow one service's logs
make migrate              # apply Alembic migrations
make revision M="add x"   # autogenerate a migration
make shell-db             # psql inside the database container
make shell-api            # bash inside the API container
make down                 # stop the stack, keep the data
make reset                # stop the stack and DESTROY all volumes
```

No `make` on the host? `./fm` is a shell task runner with the same targets:
`./fm up`, `./fm dev`, `./fm check`, `./fm seed`, `./fm logs api`, `./fm reset`, …

## Repository layout

```
apps/api/     FastAPI · SQLAlchemy 2.0 · Alembic · Pydantic v2 · Celery
apps/web/     React 18 · TypeScript · Vite · TailwindCSS · TanStack Query/Table · Recharts
docs/         architecture, database, debugging, testing + ADRs
00.prompts/   the build brief and per-module specifications
```

## Receipt parsing runs entirely on your own hardware

M1a's ingestion pipeline — extraction, OCR, the fiscal QR reader and merchant
matching — is **local by default**: it needs no subscription and no network, and
a Continente or Lidl PDF reconciles to the cent with none. The OS packages
behind it (`apps/api/Dockerfile`) are `tesseract-ocr`, `tesseract-ocr-por` and
`libzbar0`. `make seed` now also creates the household's merchant NIFs and the
five parser profiles, and the reconciliation tolerance is a `Setting`
(`receipts.arithmetic_tolerance_eur`, default `0.02`) rather than a constant.

M1b's «Importar folha» tab, under **Supermercado**, migrates a household's own
years-old `SUPERMARKET_YYYY` spreadsheet into the same `Receipt`/`ReceiptItem`
model a scanned *talão* produces: it snaps each Fs row's nudged timestamp back
onto its invoice, recomputes the invoice-level discount rather than trusting a
column the sheet only filled in by hand, and scores every imported receipt like
a parsed one, so a group that does not reconcile lands in the Review Queue
rather than being written as fact ([ADR-0021](docs/decisions/0021-the-legacy-sheet-is-validated-not-trusted.md)).

M1c closes the module with money over time: the «Preços», «Despesa» and
«Fidelização» tabs chart €/kg trends and shrinkflation alerts, spend by
category over both what was paid and what was worth having, and loyalty
totals grouped by scheme and card. Every observation is appended, never
rewritten — a correction made during review sits beside the price it
supersedes rather than replacing it
([ADR-0022](docs/decisions/0022-price-history-is-append-only-and-stores-no-quotient.md)).
The review pane can also link a receipt to the bank transaction that paid for
it: the link is wired end to end today through a `LedgerProvider` seam, and
is waiting on the Banking module (M2) for a real ledger to search.

## Principles worth knowing before you touch the code

- **Money is `Decimal` EUR, `NUMERIC(10,2)`.** Never a float, never minor units.
  There is exactly one formatting surface on each side: `app/core/money.py` and
  `src/lib/format.ts`.
- **Nothing financial is hard-deleted.** Rows are soft-deleted and every mutation
  writes an `AuditLog` row — that log is the sole source of historical truth.
- **Entity is attribution, not permission.** Every record carries an `entity_id`;
  every household member reads everything. Roles (`OWNER`/`MEMBER`/`VIEWER`) govern
  write power only.
- **External providers are off by default.** Brickset is contacted only when a user
  presses «Procurar», and only if it has been switched on in *Definições*.
- **Attachments never touch a web root.** They are magic-byte validated, stored
  content-addressed under `STORAGE_ROOT`, and served only through a signed,
  time-limited URL.
- **Code and schema are English; the UI is pt-PT** and i18n-ready.

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — service topology, request flow, auth.
- [`docs/capabilities.md`](docs/capabilities.md) — what already exists and where. **Read this before starting any module.**
- [`docs/database.md`](docs/database.md) — schema map, migrations, how to open a shell.
- [`docs/debugging.md`](docs/debugging.md) — logs, debuggers, Celery/Redis, audit trails.
- [`docs/testing.md`](docs/testing.md) — what is tested and why.
- [`docs/decisions/`](docs/decisions/) — one ADR per non-obvious decision.

## Reset everything

```bash
make reset && make up
```

You land back on the first-run setup screen. Run `make seed` afterwards if you
want the demo data again.
