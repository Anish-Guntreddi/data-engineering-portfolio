# WarehouseLab — End-to-End Analytics Engineering Pipeline

A self-contained, deterministic analytics-engineering stack:

```
deterministic generator  ->  Postgres (raw)  ->  dbt (staging -> marts)  ->  Dagster / Metabase
```

- **PostgreSQL 16** — warehouse (host port **5433**, db `warehouse`).
- **dbt-postgres** — `raw.*` sources → `staging` views → `marts` tables, with
  schema tests (`not_null`, `unique`, `relationships`, `accepted_values`,
  `accepted_range`) **and** two singular *golden-value* tests.
- **Dagster (dagster-dbt)** — orchestrates `seed_raw` → dbt assets, with a daily
  schedule. UI on host port **3333**.
- **Metabase** (optional) — BI dashboard on host port **3030**.

Everything that needs dbt/Dagster runs inside `python:3.11-slim` containers. The
host is only used to run the pure-logic unit tests.

---

## Quickstart (clean clone → populated marts, one command)

```bash
git clone <this-repo> && cd warehouselab
cp .env.example .env          # local, non-secret creds (postgres/postgres)
make run                      # postgres up + seed raw + dbt build + dbt test
```

`make run`:
1. starts Postgres (host `5433`) and waits for it to be healthy,
2. builds the pipeline image (dbt-postgres + dagster + dagster-dbt + psycopg2),
3. runs the deterministic generator load into `raw.users/events/orders`,
4. `dbt deps` then `dbt build` (runs every model **and** every test).

The container exits **0** only if all models materialise and all tests pass.

### Explore the data

```bash
make psql
# inside psql:
select * from marts.fct_daily_active_users order by date limit 5;
select * from marts.fct_revenue_by_day where date = '2024-01-11';
```

### Optional: orchestration UI and dashboard

```bash
make dagster     # Dagster UI  -> http://localhost:3333  (asset graph + schedule)
make dashboard   # Metabase    -> http://localhost:3030  (connect to the warehouse db)
make down        # stop everything and drop volumes
```

---

## Architecture

### Data flow

| Layer    | Object                                   | Grain / meaning                         |
|----------|------------------------------------------|-----------------------------------------|
| raw      | `raw.users`, `raw.events`, `raw.orders`  | generator output, loaded by psycopg2    |
| staging  | `stg_users`, `stg_events`, `stg_orders`  | typed/cleaned views, derived dates      |
| marts    | `fct_daily_active_users`                 | distinct active users per day           |
|          | `fct_revenue_by_day`                     | completed-order revenue + count per day |
|          | `dim_users`                              | user dim + lifetime activity/revenue    |

`fct_daily_active_users(date, dau)` — DAU = distinct users with ≥1 event that day.
`fct_revenue_by_day(date, revenue, n_orders)` — only `status='completed'` orders.

### Determinism & golden values

`generator/generate.py` is a **pure** function (`numpy`/`pandas` only) seeded with
`seed=42`. As a result, for the **golden date `2024-01-11`** the metrics are known
by construction and baked in three places that must agree:

| value          | golden       |
|----------------|--------------|
| `golden_date`  | `2024-01-11` |
| `golden_dau`   | `57`         |
| `golden_revenue` | `1175.29`  |
| `golden_n_orders` | `35`      |

These are baked into `tests/test_generator.py`, `warehouse_dbt/dbt_project.yml`
(`vars:`), and consumed by the dbt singular tests
`tests/assert_dau_golden.sql` / `tests/assert_revenue_golden.sql`.
Re-derive any time with:

```bash
make venv
.venv/bin/python -m generator.generate    # prints the golden JSON
```

### Orchestration (Dagster)

`orchestration/definitions.py` exposes a `Definitions` object:
- `seed_raw` asset — runs the generator load into `raw.*`,
- dbt assets — loaded from the dbt manifest; the `raw.*` sources are mapped onto
  the `seed_raw` asset key, so the DAG is `seed_raw → staging → marts`,
- `materialize_all` job + `daily_refresh` schedule (`0 6 * * *`, UTC).

---

## Verification gates

All four gates are reproducible from a clean clone.

### Gate 1 — Host unit tests (determinism + golden values)

```bash
make test
```
Runs `tests/test_generator.py` in the project `.venv` (pure pandas/numpy):
asserts the generator is deterministic across two calls, that DAU/revenue/order
count for the golden date equal the golden constants, and that event/order
category values stay within their accepted sets. **Expected: all tests pass.**

### Gate 2 — Empty → populated marts via `dbt build`

```bash
make run
```
From an empty database, seeds `raw.*` and runs `dbt build`. **Expected:** marts
`fct_daily_active_users`, `fct_revenue_by_day`, `dim_users` are populated and the
container exits `0`.

### Gate 3 — `dbt test` all green, incl. golden singular tests

`dbt build` (inside Gate 2) runs every schema test plus the two singular golden
tests. To run only the tests against an already-built warehouse:

```bash
docker compose run --rm pipeline bash -lc \
  "bash /app/scripts/wait_for_postgres.sh && \
   dbt deps  --project-dir /app/warehouse_dbt --profiles-dir /app/warehouse_dbt && \
   dbt test  --project-dir /app/warehouse_dbt --profiles-dir /app/warehouse_dbt"
```
**Expected:** `assert_dau_golden` and `assert_revenue_golden` return 0 rows
(PASS), and all `not_null`/`unique`/`relationships`/`accepted_values` tests pass.

### Gate 4 — `dbt docs generate` succeeds

```bash
make docs
```
**Expected:** dbt compiles the project and writes `target/catalog.json` /
`target/manifest.json` without error.

---

## Layout

```
warehouselab/
  generator/        generate.py (PURE), load.py (psycopg2), schema.sql
  warehouse_dbt/    dbt_project.yml, profiles.yml, packages.yml, models/, tests/, macros/
  orchestration/    definitions.py (Dagster Definitions + dbt assets + schedule)
  scripts/          run_pipeline.sh (the one command), wait_for_postgres.sh
  tests/            test_generator.py (host unit tests)
  Dockerfile        python:3.11-slim runtime for pipeline + dagster services
  docker-compose.yml, Makefile, .env.example, requirements.txt
```

## Make targets

| target          | what it does                                                |
|-----------------|-------------------------------------------------------------|
| `make up`       | start Postgres and wait until healthy                       |
| `make run`      | **one command**: seed raw + `dbt build` + `dbt test`        |
| `make test`     | host unit tests (`.venv`: determinism + golden values)      |
| `make docs`     | `dbt docs generate` in the pipeline container               |
| `make dagster`  | start Dagster webserver + daemon (orchestration profile)    |
| `make dashboard`| start Metabase (dashboard profile)                          |
| `make down`     | stop everything, drop volumes                               |
| `make psql`     | psql shell into the warehouse DB                            |
| `make clean`    | remove `.venv` and dbt build artifacts                      |
