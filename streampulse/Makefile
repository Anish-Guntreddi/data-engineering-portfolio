# StreamPulse — Makefile
# Targets follow CONVENTIONS.md: up, e2e, test, down (+ helpers).

SHELL := /bin/bash
COMPOSE ?= docker compose
VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

# Seconds to let tumbling windows populate + a burst breach to fire before
# running the e2e assertions. Default window is 60s, so wait > 1 window.
E2E_WAIT ?= 90

.PHONY: help
help:
	@echo "StreamPulse targets:"
	@echo "  make venv   - create host .venv and install pure test deps"
	@echo "  make test   - run host unit tests (windowing/metrics/alerting)"
	@echo "  make up      - build + start the whole stack (detached)"
	@echo "  make e2e     - up, wait for windows + forced breach, run e2e_check"
	@echo "  make logs    - tail service logs"
	@echo "  make ps      - show service status"
	@echo "  make down    - stop and remove the stack (keeps volume)"
	@echo "  make clean   - down + remove the postgres volume"

# ---- Host unit tests (pure logic only) ----
$(VENV):
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-dev.txt

.PHONY: venv
venv: $(VENV)

.PHONY: test
test: venv
	$(PY) -m pytest tests/ -q

# ---- Containerized stack ----
# producer/processor/alerter/dashboard all share one image (streampulse-app).
# Build it ONCE via a single service, otherwise parallel builds race on the
# shared tag ("image already exists") under the containerd image store.
.PHONY: build
build:
	$(COMPOSE) build producer

.PHONY: up
up: build
	$(COMPOSE) up -d
	@echo "StreamPulse is up."
	@echo "  Dashboard : http://localhost:$${DASHBOARD_PORT:-8502}"
	@echo "  Console   : http://localhost:$${REDPANDA_CONSOLE_PORT:-8090}"
	@echo "  Postgres  : localhost:$${POSTGRES_PORT:-5435} (db streampulse)"

.PHONY: e2e
e2e: up
	@echo "Waiting $(E2E_WAIT)s for windows to populate and a breach to fire..."
	@sleep $(E2E_WAIT)
	@echo "Running e2e verification inside a container..."
	$(COMPOSE) run --rm --no-deps \
	  -e WINDOW_SECONDS=$${WINDOW_SECONDS:-60} \
	  -e LOOKBACK_WINDOWS=30 \
	  -e WAIT_SECONDS=120 \
	  -e PGHOST=$${PGHOST:-postgres} \
	  -e PGPORT=$${PGPORT:-5432} \
	  -e PGDATABASE=$${PGDATABASE:-streampulse} \
	  -e PGUSER=$${PGUSER:-postgres} \
	  -e PGPASSWORD=$${PGPASSWORD:-postgres} \
	  processor python /app/scripts/e2e_check.py

.PHONY: logs
logs:
	$(COMPOSE) logs -f --tail=100

.PHONY: ps
ps:
	$(COMPOSE) ps

.PHONY: down
down:
	$(COMPOSE) down

.PHONY: clean
clean:
	$(COMPOSE) down -v
