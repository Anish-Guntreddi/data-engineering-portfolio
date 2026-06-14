# DataGuard — one-command run targets.
#
#   make venv   create host .venv (pytest/numpy/pandas/pyyaml) for unit tests
#   make test   run host unit tests (pure logic; no Docker)
#   make up     build images + start postgres, api, dashboard
#   make demo   up + seed demo tables + run all checks (leaves api/dashboard up)
#   make seed   seed/run checks only (assumes stack is up)
#   make logs   tail compose logs
#   make down   stop and remove containers + volume
#   make clean  remove the host .venv

SHELL := /bin/bash
VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

# Prefer a host interpreter that can build the venv. Python 3.14 is fine for the
# minimal host test deps.
HOST_PYTHON ?= python3

COMPOSE := docker compose

.PHONY: help
help:
	@grep -E '^#   make' Makefile | sed 's/^#   //'

# --------------------------------------------------------------------------- #
# Host unit tests (no Docker)
# --------------------------------------------------------------------------- #
.PHONY: venv
venv:
	$(HOST_PYTHON) -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PIP) install -r requirements-test.txt

.PHONY: test
test: venv
	PYTHONPATH=. $(PY) -m pytest tests/ -q

# --------------------------------------------------------------------------- #
# Containerized stack
# --------------------------------------------------------------------------- #
.PHONY: up
up:
	$(COMPOSE) up -d --build postgres api dashboard

.PHONY: seed
seed:
	$(COMPOSE) run --rm runner

# Full demo: bring the stack up, seed + run checks to completion, leave the api
# and dashboard running so the dashboard renders against seeded results.
.PHONY: demo
demo:
	$(COMPOSE) up -d --build postgres
	$(COMPOSE) run --rm runner
	$(COMPOSE) up -d --build api dashboard
	@echo ""
	@echo "DataGuard is up:"
	@echo "  API:       http://localhost:$${DATAGUARD_API_PORT:-8201}/health"
	@echo "  Dashboard: http://localhost:$${DATAGUARD_DASHBOARD_PORT:-8501}"

.PHONY: logs
logs:
	$(COMPOSE) logs -f --tail=100

.PHONY: down
down:
	$(COMPOSE) down -v

.PHONY: clean
clean:
	rm -rf $(VENV)
