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
| 3 | M1 Receipts & OCR | ⏳ |
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
make seed                     # deterministic Portuguese demo data
```

Open **http://localhost:8080** and sign in with the bootstrap account printed by
`make seed` (`owner@finmanager.local` / `finmanager` by default — change it).

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
- [`docs/database.md`](docs/database.md) — schema map, migrations, how to open a shell.
- [`docs/debugging.md`](docs/debugging.md) — logs, debuggers, Celery/Redis, audit trails.
- [`docs/testing.md`](docs/testing.md) — what is tested and why.
- [`docs/decisions/`](docs/decisions/) — one ADR per non-obvious decision.

## Reset everything

```bash
make reset && make up && make seed
```