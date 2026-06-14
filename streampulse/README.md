# StreamPulse — Real-Time Event Analytics Pipeline

A small, fully reproducible streaming analytics pipeline:

```
producer ──▶ Redpanda (Kafka API, topic "events")
                 │
                 ▼
            processor ──▶ tumbling windows (pure) ──▶ metrics table (Postgres)
                                                          │
                                ┌─────────────────────────┴───────────────┐
                                ▼                                          ▼
                          alerter (poll metrics,                   Streamlit dashboard
                          evaluate thresholds,                     (live metrics + alerts)
                          write alerts table)
```

* **Broker:** Redpanda (Kafka-compatible, lighter to run locally).
* **Runtime client:** `confluent-kafka` (containerized only).
* **Store:** PostgreSQL (`metrics`, `alerts` tables).
* **Dashboard:** Streamlit, auto-refreshing.

The **core logic is pure** — `windowing.py`, `metrics.py`, `alerting.py`, and
`events.py` import only the Python standard library (no kafka / postgres), so
they unit-test on the host with no Docker. The processor/alerter import those
exact modules, so the code that is tested is the code that runs.

## Ports (see `../CONVENTIONS.md`)

| Service             | Host port | Notes                          |
|---------------------|-----------|--------------------------------|
| Redpanda (Kafka)    | 19092     | external listener              |
| Redpanda Console    | 8090      | web UI at http://localhost:8090 |
| PostgreSQL          | 5435      | db `streampulse`, user/pass `postgres`/`postgres` |
| Streamlit dashboard | 8502      | http://localhost:8502          |

## Quickstart (copy-paste)

```bash
cd streampulse
cp .env.example .env            # local, git-ignored

# 1) Host unit tests (pure logic) — no Docker needed
make test

# 2) Bring up the whole pipeline
make up

# 3) End-to-end verification (waits for windows + a forced breach, then asserts)
make e2e

# Open the dashboard:  http://localhost:8502
# Open the console:    http://localhost:8090

# Tear down
make down       # keep data volume
make clean      # also drop the postgres volume
```

`make test` creates a project-local `.venv` and installs only `pytest`, `numpy`,
`pandas`, `pyyaml` (these install cleanly on Python 3.14). The streaming runtime
(`confluent-kafka`, `psycopg2`, `streamlit`) is **never** installed on the host —
it runs inside `python:3.11-slim` containers.

## How it works

1. **producer** (`streampulse/producer/main.py`) emits deterministic synthetic
   events (`page_view`, `session_start`, `add_to_cart`, `purchase`) to the
   `events` topic using the pure `events.stream_events` generator. It injects a
   periodic **burst** (default every 50 events, 12x volume) so that
   `events_per_minute` reliably climbs above the alert threshold.
2. **processor** (`streampulse/processor/main.py`) consumes `events`, folds them
   into in-memory **tumbling windows** via the pure `windowing` module, computes
   `events_per_minute` and `conversion_rate` via the pure `metrics` module, and
   UPSERTs the rows into the `metrics` table every few seconds.
3. **alerter** (`streampulse/alerter/main.py`) polls recent `metrics` rows and
   runs the pure `alerting.evaluate_thresholds`. On a breach it writes an
   `alerts` row (deduped on `(ts, metric)`).
4. **dashboard** (`streampulse/dashboard/app.py`) reads both tables and renders
   live charts + an alerts table, auto-refreshing every 5s.

### Metrics

* `events_per_minute = total_events / (window_seconds / 60)`
* `conversion_rate = purchases / page_views` (defined as `0.0` when there are no
  page views).

### Default alert thresholds

* `events_per_minute > 300` → alert (`EPM_MAX`)
* `conversion_rate < 0.02` → alert (`CONV_MIN`)

All tunables live in `.env` (see `.env.example`).

## Verification gates

These four gates terminate the build loop (per `CONVENTIONS.md`):

1. **Exact windowed aggregates (host unit tests).** `tests/test_windowing.py`
   feeds a known deterministic batch (`generate_batch(seed=7, n=120, …)`) and
   asserts exact per-type counts per window, e.g. window 0 =
   `{page_view:30, session_start:18, add_to_cart:10, purchase:2}`.
   `tests/test_metrics.py` asserts the exact conversion-rate math
   (`2/30` and `2/35`). Run with `make test` (18 tests).
2. **Metrics table populated within the window.** `make e2e` waits one window,
   then `scripts/e2e_check.py` asserts the `metrics` table has rows for recent
   windows (the processor consumed events and wrote aggregates).
3. **Alert fires on a forced breach.** The producer's burst pushes
   `events_per_minute` above `EPM_MAX`; the alerter writes an `alerts` row; the
   e2e check asserts at least one alert row exists.
4. **`docker compose up` brings the pipeline up.** `make up` builds and starts
   redpanda, console, postgres, producer, processor, alerter, and dashboard with
   healthchecked `depends_on`.

Golden values are baked from actually running the pure generator/logic on the
host; the RNG is seeded (`seed=7`) so they are known by construction.

## Project layout

```
streampulse/
  README.md  docker-compose.yml  .env.example  Makefile  Dockerfile
  requirements.txt        # container runtime deps
  requirements-dev.txt    # host .venv test deps (pure)
  streampulse/
    __init__.py
    windowing.py   # PURE tumbling-window aggregation
    metrics.py     # PURE events_per_minute / conversion_rate
    alerting.py    # PURE evaluate_thresholds
    events.py      # event schema + deterministic + streaming generators
    db.py          # postgres schema + helpers (psycopg2 imported lazily)
    producer/main.py   # emit events -> 'events' topic (confluent-kafka)
    processor/main.py  # consume -> tumbling windows -> metrics table
    alerter/main.py    # poll metrics -> evaluate -> alerts table
    dashboard/app.py   # Streamlit live dashboard
  scripts/e2e_check.py
  tests/
    test_windowing.py  test_metrics.py  test_alerting.py
```

## Troubleshooting

* **`make e2e` fails on the alert gate:** the burst needs at least one full
  window. Increase `E2E_WAIT` (e.g. `make e2e E2E_WAIT=150`) or lower `EPM_MAX`
  in `.env`.
* **Port already in use:** override the host port in `.env`
  (`DASHBOARD_PORT`, `POSTGRES_PORT`, `REDPANDA_PORT`, `REDPANDA_CONSOLE_PORT`).
* **Connect to Postgres directly:**
  `psql postgresql://postgres:postgres@localhost:5435/streampulse`.
