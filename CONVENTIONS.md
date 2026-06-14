# Shared build conventions

This monorepo holds three independent data-engineering projects. They share a
Postgres-centered local stack and a common philosophy: **every pipeline runs
from a clean clone with one command, seeds its own deterministic data, and is
verified by automated gates** (unit tests + golden values + a reproducible run).

## Port allocation (avoid collisions; all overridable via each project's `.env`)

| Project       | Postgres | App / API | Dashboard | Extra                    |
|---------------|----------|-----------|-----------|--------------------------|
| WarehouseLab  | 5433     | 3333 (Dagster) | 3030 (Metabase) | —                  |
| DataGuard     | 5434     | 8201 (FastAPI) | 8501 (Streamlit) | —                |
| StreamPulse   | 5435     | —         | 8502 (Streamlit) | 19092 (Redpanda/Kafka), 8090 (Console) |

## Postgres credentials (local only, non-secret)

- user: `postgres`
- password: `postgres`
- databases: `warehouse`, `dataguard`, `streampulse` respectively

## Conventions every project follows

- **Containerized runtimes.** dbt/Dagster run in `python:3.11-slim` containers
  (the host's Python 3.14 is never required to run a project). Pure-Python unit
  tests may run on the host.
- **Deterministic generators.** Synthetic data uses a fixed seed so golden
  values are known by construction.
- **Pure, testable core logic.** Windowing, drift, scoring, and check functions
  are pure `(input, config) -> result` functions with NO infra imports, so they
  unit-test without Docker.
- **One-command run.** Each project has a `Makefile` with at least:
  `make up`, `make run`/`make e2e`/`make demo`, `make test`, `make down`.
- **Self-documenting.** Each project has a `README.md` with a copy-paste
  reproducible run and an explicit "Verification gates" section.
- **`.env.example`** committed; real `.env` git-ignored.

## Verification gates (the loop terminators)

- **WarehouseLab** — `make run` goes empty → populated marts; `dbt test` all
  green; a golden-value test asserts seeded DAU for a date equals the expected
  number; `dbt docs generate` succeeds.
- **StreamPulse** — unit tests assert exact windowed aggregates on a known
  batch; an integration run populates the metrics table within the window; an
  alert fires on a forced threshold breach; `docker compose up` brings the
  pipeline up.
- **DataGuard** — unit tests cover each check type (pass + fail fixtures); drift
  flags a shifted distribution and passes a stable one; the quality score is
  deterministic for fixed inputs; the dashboard renders against seeded results.
