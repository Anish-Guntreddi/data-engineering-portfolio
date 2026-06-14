# WarehouseLab — analytics engineering pipeline.
# One-command run: `make run` (seeds raw -> dbt build -> dbt test, all in Docker).
# Host unit tests: `make test` (project .venv, pure pandas/numpy logic).

SHELL := /bin/bash
COMPOSE := docker compose
VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.DEFAULT_GOAL := help
.PHONY: help up run test docs dagster dashboard down venv clean logs psql

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

up: ## Start postgres and wait until it is healthy
	@cp -n .env.example .env 2>/dev/null || true
	$(COMPOSE) up -d postgres
	@echo "Waiting for postgres to become healthy..."
	@for i in $$(seq 1 60); do \
		status=$$(docker inspect -f '{{.State.Health.Status}}' warehouselab-postgres 2>/dev/null || echo starting); \
		if [ "$$status" = "healthy" ]; then echo "postgres healthy"; exit 0; fi; \
		sleep 2; \
	done; echo "postgres did not become healthy" >&2; exit 1

run: ## ONE COMMAND: seed raw + dbt build + dbt test (empty -> populated marts)
	@cp -n .env.example .env 2>/dev/null || true
	$(COMPOSE) up -d postgres
	$(COMPOSE) run --rm pipeline

venv: ## Create host .venv with ONLY host-test deps (pytest numpy pandas pyyaml)
	@test -d $(VENV) || python3 -m venv $(VENV)
	$(PIP) install --quiet --upgrade pip
	$(PIP) install --quiet pytest numpy pandas pyyaml

test: venv ## Run host unit tests (generator determinism + golden values)
	$(PY) -m pytest tests/ -v

docs: ## Generate dbt docs inside the pipeline container
	@cp -n .env.example .env 2>/dev/null || true
	$(COMPOSE) up -d postgres
	$(COMPOSE) run --rm pipeline bash -lc \
		"bash /app/scripts/wait_for_postgres.sh && dbt deps --project-dir /app/warehouse_dbt --profiles-dir /app/warehouse_dbt && dbt docs generate --project-dir /app/warehouse_dbt --profiles-dir /app/warehouse_dbt"

dagster: ## Start the Dagster webserver + daemon (UI on :3333)
	@cp -n .env.example .env 2>/dev/null || true
	$(COMPOSE) --profile orchestration up -d
	@echo "Dagster UI: http://localhost:$${HOST_DAGSTER_PORT:-3333}"

dashboard: ## Start Metabase (UI on :3030)
	@cp -n .env.example .env 2>/dev/null || true
	$(COMPOSE) --profile dashboard up -d metabase
	@echo "Metabase UI: http://localhost:$${HOST_METABASE_PORT:-3030}"

logs: ## Tail pipeline / dagster logs
	$(COMPOSE) logs -f

psql: ## Open a psql shell against the warehouse DB
	$(COMPOSE) exec postgres psql -U postgres -d warehouse

down: ## Stop everything and remove volumes
	$(COMPOSE) --profile orchestration --profile dashboard down -v

clean: ## Remove host venv and dbt build artifacts
	rm -rf $(VENV) warehouse_dbt/target warehouse_dbt/dbt_packages warehouse_dbt/logs
