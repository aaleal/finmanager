# FinManager — every target runs inside a container. Nothing is installed on the host.
#
# Requires: Docker + Docker Compose (or Podman + podman-compose, auto-detected).

SHELL := /bin/bash
.DEFAULT_GOAL := help

# --- Container engine auto-detection -----------------------------------------
COMPOSE ?= $(shell \
	if docker compose version >/dev/null 2>&1; then echo "docker compose"; \
	elif command -v docker-compose >/dev/null 2>&1; then echo "docker-compose"; \
	elif command -v podman-compose >/dev/null 2>&1; then echo "podman-compose"; \
	else echo "docker compose"; fi)

DEV_COMPOSE := $(COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml
RUN_API     := $(DEV_COMPOSE) run --rm --no-deps api
EXEC_API    := $(DEV_COMPOSE) exec api
RUN_WEB     := $(DEV_COMPOSE) run --rm --no-deps web

# One-shot containers must use --no-deps: without it, compose re-reconciles db/redis
# against the *other* overlay's service definitions and tries to recreate containers
# that are already running. Start the dependencies explicitly instead.
DB_UP       := $(COMPOSE) up -d db redis

.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  Container engine: $(COMPOSE)"

# --- Bootstrap ---------------------------------------------------------------
.PHONY: env
env: ## Create .env from .env.example if missing
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example")

# --- Lifecycle ---------------------------------------------------------------
.PHONY: up
up: env ## Build and start the production-like stack (http://localhost:8080)
	$(COMPOSE) up --build -d
	@echo "FinManager is up on http://localhost:$${WEB_PORT:-8080}"

.PHONY: dev
dev: env ## Start the dev stack with hot reload (web 8080, api 8000, adminer 8081)
	$(DEV_COMPOSE) up --build -d
	@echo "Dev stack up:  web http://localhost:8080  |  api docs http://localhost:8000/api/docs  |  adminer http://localhost:8081"

.PHONY: down
down: ## Stop the stack (keeps data)
	$(DEV_COMPOSE) down

.PHONY: reset
reset: ## Stop the stack and DESTROY all volumes (database, redis, attachments)
	$(DEV_COMPOSE) down -v

.PHONY: logs
logs: ## Follow logs for all services (make logs S=api for one)
	$(DEV_COMPOSE) logs -f $(S)

.PHONY: ps
ps: ## Show container status
	$(DEV_COMPOSE) ps

# --- Database ----------------------------------------------------------------
.PHONY: migrate
migrate: ## Apply Alembic migrations (the API also does this on every boot)
	@$(DB_UP)
	$(RUN_API) alembic upgrade head

.PHONY: revision
revision: ## Autogenerate a migration: make revision M="add x"
	@$(DB_UP)
	$(RUN_API) alembic revision --autogenerate -m "$(M)"

.PHONY: downgrade
downgrade: ## Roll back one migration
	@$(DB_UP)
	$(RUN_API) alembic downgrade -1

.PHONY: seed
seed: ## Load the deterministic Portuguese demo dataset
	@$(DB_UP)
	$(RUN_API) python -m app.seed

.PHONY: shell-db
shell-db: ## Open psql inside the database container
	$(DEV_COMPOSE) exec db psql -U $${POSTGRES_USER:-finmanager} -d $${POSTGRES_DB:-finmanager}

.PHONY: shell-api
shell-api: ## Open a shell inside the api container
	$(DEV_COMPOSE) exec api bash

# --- Quality gate ------------------------------------------------------------
.PHONY: check
check: lint types test ## Full gate: lint + types + tests, both apps

.PHONY: lint
lint: ## Lint both apps
	$(RUN_API) ruff check app tests
	$(RUN_API) ruff format --check app tests
	$(RUN_WEB) npm run lint

.PHONY: format
format: ## Auto-format both apps
	$(RUN_API) ruff format app tests
	$(RUN_API) ruff check --fix app tests
	$(RUN_WEB) npm run format

.PHONY: types
types: ## Type-check both apps
	$(RUN_API) mypy app
	$(RUN_WEB) npm run typecheck

.PHONY: test
test: test-api test-web ## Run all tests

.PHONY: test-api
test-api: ## Run the backend suite (unit + integration) inside the container
	@$(DB_UP)
	$(RUN_API) pytest -q

.PHONY: test-web
test-web: ## Run the frontend suite
	$(RUN_WEB) npm run test

# --- Contracts ---------------------------------------------------------------
.PHONY: types-gen
types-gen: ## Regenerate the frontend API types from the OpenAPI schema
	mkdir -p apps/web/src/api
	$(RUN_API) python -m app.openapi_export > apps/web/openapi.json
	$(RUN_WEB) npx --yes openapi-typescript /app/openapi.json -o /app/src/api/schema.d.ts
