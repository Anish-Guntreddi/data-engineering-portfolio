<div align="center">

# Green Gates — Data Engineering Portfolio

**Three production-shaped data systems. Each runs from a clean clone with one command and proves itself with green verification gates.**

[**▶ Live showcase site**](https://anish-guntreddi.github.io/data-engineering-portfolio/) · [WarehouseLab](warehouselab/) · [StreamPulse](streampulse/) · [DataGuard](dataguard/)

`PostgreSQL` · `dbt` · `Dagster` · `Redpanda / Kafka` · `FastAPI` · `Streamlit` · `Metabase` · `Docker Compose` · `Python`

</div>

---

## Why this portfolio

This is the **boring, critical reliability work** that production data teams live on — not a dashboard slapped on a toy dataset. Three projects each prove a different mode of data engineering, all sharing a Postgres-centered local stack:

| # | Project | Mode | What it proves |
|---|---------|------|----------------|
| 01 | **[WarehouseLab](warehouselab/)** | Batch ELT | SQL modeling, dbt tests, orchestration, lineage |
| 02 | **[StreamPulse](streampulse/)** | Real-time streaming | Event-driven architecture, windowed aggregation, alerting |
| 03 | **[DataGuard](dataguard/)** | Data quality | Schema/null/range/freshness checks, drift detection, contracts |

Every pipeline is **reproducible by construction**: it seeds its own deterministic synthetic data and runs end-to-end from an empty state. "Done" is not a vibe — it is a set of **automated verification gates** (golden-value assertions, dbt tests, exact windowed aggregates, dual-direction drift checks) that must turn green.

---

## The systems

### 01 · WarehouseLab — orchestrated, tested ELT
Raw events → analytics-ready marts. A deterministic generator lands raw events in Postgres; **dbt** cleans and types them into staging, then computes business marts (daily active users, revenue by day, a user dimension). **Dagster** runs the DAG on a daily schedule; **Metabase** reads the marts.

**Gates:** `make run` goes empty → populated marts · `dbt test` all green · a golden-value test asserts seeded DAU for a date equals the expected number · `dbt docs generate` builds lineage clean.

```bash
cd warehouselab && make run      # empty → seeded → dbt build + test
```

### 02 · StreamPulse — real-time event analytics
A producer streams synthetic events into a **Redpanda** topic. A stream processor maintains tumbling windows (events/min, conversion rate per 5-min window) and writes them to a metrics store; a live dashboard renders them; an alerter fires on threshold breach. The windowing logic is pure and unit-tested to **exact** aggregates.

**Gates:** unit tests assert exact aggregates on a known batch · an integration run populates metrics within the window · an alert fires on a forced breach · `docker compose up` brings the pipeline up.

```bash
cd streampulse && make test      # exact windowed-aggregate unit tests
cd streampulse && make e2e       # full streaming pipeline + assertions
```

### 03 · DataGuard — data-quality monitoring
A pluggable engine runs checks — schema, null, range, freshness, and distribution **drift (PSI + KS)** — against Postgres tables, rolling results into a deterministic per-table quality score. A **FastAPI** service serves results; a **Streamlit** dashboard shows scores, failing checks, and trends. Every check is a pure, tested function.

**Gates:** each check type covered with pass + fail fixtures · drift flags a shifted distribution and passes a stable one · the quality score is deterministic for fixed inputs · the dashboard renders against seeded results.

```bash
cd dataguard && make test        # per-check + drift + scoring unit tests
cd dataguard && make demo        # seed tables, run checks, serve API + dashboard
```

---

## Repository layout

```
.
├── warehouselab/      # 01 · dbt + Dagster + Postgres + Metabase
├── streampulse/       # 02 · Redpanda + stream processor + Postgres + Streamlit
├── dataguard/         # 03 · check engine + FastAPI + Streamlit + Postgres
├── docs/              # the GitHub Pages showcase site (Green Gates)
├── CONVENTIONS.md     # shared ports, credentials, and build conventions
├── VERIFICATION.md    # what was verified, golden values, and how to reproduce
└── Makefile           # top-level: run a project's unit tests from the root
```

Each project is **self-contained**: its own `docker-compose.yml`, `Makefile`, `.env.example`, `requirements.txt`, `README.md`, and tests. Heavy runtimes (dbt, Dagster, Kafka clients) are containerized so a clean clone runs identically anywhere — the host's Python version is never required to *run* a pipeline.

---

## Quickstart

```bash
git clone https://github.com/Anish-Guntreddi/data-engineering-portfolio.git
cd data-engineering-portfolio

# Pure-Python unit tests (no Docker needed) for any project:
make test-streampulse        # or test-dataguard / test-warehouselab

# Full end-to-end runs (need Docker):
cd warehouselab && make run
cd ../streampulse && make e2e
cd ../dataguard  && make demo
```

> **Prerequisites:** Docker + Docker Compose for the end-to-end runs. Python 3.11+ on the host only for the pure-logic unit tests. See [`CONVENTIONS.md`](CONVENTIONS.md) for the port map (no collisions between projects).

---

## The build method — why the loop converges

These projects were built with a tight, gate-driven loop. An agent told to "loop until done" without a green signal will confidently produce broken code; this repo converges because every project has three things baked in:

1. **Tight v1 scope** — explicit out-of-scope lists keep each project finishable.
2. **A verification harness** — deterministic generators + golden values + unit tests.
3. **The gates decide done** — review/QA read those gates; green = ship.

Build one project at a time, let the gates declare it done, then move on.

---

<div align="center">

**[Explore the live showcase →](https://anish-guntreddi.github.io/data-engineering-portfolio/)**

Anish Guntreddi · [GitHub](https://github.com/Anish-Guntreddi) · MIT Licensed

</div>
