# DataGuard — Data Quality Monitoring & Validation System

DataGuard validates Postgres tables against declarative **expectations**
(`expectations/*.yml`), computes a per-table **quality score** in `[0, 100]`,
and renders results in a Streamlit dashboard backed by a FastAPI service.

It ships two deterministic demo tables so you can see **passing and failing**
checks immediately:

| Table            | Story                                                                 |
|------------------|-----------------------------------------------------------------------|
| `orders_clean`   | well-behaved — every check passes                                     |
| `orders_drifted` | injected nulls, out-of-range values, a **shifted distribution**, and stale timestamps — several checks fail |

## Checks

All checks are **pure** `(<pandas DataFrame>, <config dict>) -> CheckResult`
functions that import **no infrastructure libraries** — so the whole core
unit-tests on the host without Docker.

| Check              | What it asserts                                                        |
|--------------------|-----------------------------------------------------------------------|
| `schema_check`     | expected columns are present (and, if given, correctly typed)         |
| `null_check`       | null fraction of a column `<=` threshold                              |
| `range_check`      | fraction of values within `[min, max]` `>=` threshold                 |
| `freshness_check`  | `max(timestamp) ` is within an SLA of an **injected** `now`           |
| `drift_check`      | distribution vs. a stored baseline — **PSI** (primary), **KS** (secondary) |

### Drift: PSI and KS (implemented by hand, numpy only — no scipy)

* **PSI (Population Stability Index)** — *primary* signal. Per-bin proportion
  comparison: `PSI = Σ (aᵢ − eᵢ)·ln(aᵢ / eᵢ)` over quantile bins of the
  baseline. Rule of thumb: `< 0.10` stable, `0.10–0.25` moderate, `>= 0.25`
  significant. **Drift is flagged when `PSI > threshold` (default `0.2`).**
* **KS (Kolmogorov–Smirnov)** — *secondary* signal. The statistic
  `D = max|F_baseline(x) − F_current(x)|` over the empirical CDFs (statistic
  only, no p-value, so no scipy is required).

On the seeded data the drift check **flags `orders_drifted`** (PSI ≈ 4.99, far
above `0.2`) and **passes `orders_clean`** (PSI = 0.0 against its own baseline).

### Quality score (deterministic)

Each check contributes its continuous `score ∈ [0, 1]` weighted by severity
(`info=1`, `warning=2`, `critical=3`):

```
table_score = 100 × ( Σ wᵢ·scoreᵢ ) / ( Σ wᵢ )
```

The same `CheckResult` list always produces the same score. (Golden example:
the fixed list in `tests/test_scoring.py` scores **75.0** by construction.)

---

## Quickstart (copy-paste reproducible)

### 1. Host unit tests (no Docker — pure logic)

```bash
cd dataguard
make test          # creates .venv (pytest/numpy/pandas/pyyaml) and runs pytest
```

Expected: **38 passed**.

### 2. Full demo stack (Docker)

```bash
cd dataguard
cp .env.example .env          # optional; defaults already match CONVENTIONS
make demo                     # postgres + seed + run checks, then api + dashboard
```

Then open:

* API health:  <http://localhost:8201/health>
* Scores:      <http://localhost:8201/scores>
* Results:     <http://localhost:8201/results>
* Trends:      <http://localhost:8201/trends>
* Dashboard:   <http://localhost:8501>

Tear down (removes the Postgres volume):

```bash
make down
```

### Ports & credentials (per monorepo `CONVENTIONS.md`)

| Component  | Port | Notes                          |
|------------|------|--------------------------------|
| Postgres   | 5434 | db `dataguard`, `postgres/postgres` |
| FastAPI    | 8201 | `/health /tables /results /scores /trends` |
| Streamlit  | 8501 | dashboard                      |

---

## API

| Method & path         | Returns                                                   |
|-----------------------|-----------------------------------------------------------|
| `GET /health`         | `{status, db}` — liveness + DB connectivity               |
| `GET /tables`         | user tables in the database                               |
| `GET /results?run_id=`| raw check results (latest run if `run_id` omitted)        |
| `GET /scores?run_id=` | one quality score per table for the latest (or given) run |
| `GET /trends`         | per-run, per-table score history (for the trend chart)    |

---

## Project layout

```
dataguard/
  dataguard/
    checks/           # PURE: base, schema, null, range, freshness, drift (PSI+KS)
    scoring.py        # PURE: deterministic weighted-pass-rate aggregator
    config.py         # PURE: loads expectations/*.yml (pyyaml only)
    db.py             # infra: psycopg2 access (parameterized / sql.Identifier)
    runner.py         # infra: load -> read -> check -> score -> persist
    api/main.py       # FastAPI surface over dq_results
    dashboard/app.py  # Streamlit dashboard (reads API, falls back to DB)
    seed/seed.py      # PURE generators + thin Postgres seeder (fixed seed=1337)
  expectations/       # orders.yml (clean), users.yml (drifted)
  tests/              # host-pure tests, one per check type + drift + scoring
  Dockerfile docker-compose.yml Makefile requirements*.txt .env.example
```

The pure core (`checks/`, `scoring.py`, `config.py`, `seed/seed.py` generators)
imports **only** numpy / pandas / pyyaml. `db.py`, `runner.py`, `api/`,
`dashboard/` are the only modules that touch infrastructure, and they run inside
`python:3.11-slim` containers — the host's Python 3.14 is never required to run
the pipeline.

---

## Determinism

* Synthetic data uses a **fixed seed** (`SEED = 1337`) and a **fixed reference
  time** (`REFERENCE_NOW = 2026-06-14T12:00:00Z`), so golden values are known by
  construction.
* `freshness_check` never calls `datetime.now()` — `now` is **injected** via
  config — so it is fully deterministic in tests.
* Golden constants baked into the tests (derived by running the pure generators
  on the host):

  | Quantity                                   | Golden value |
  |--------------------------------------------|--------------|
  | PSI `orders_clean` vs baseline (stable)    | `0.000000`   |
  | PSI `orders_drifted` vs baseline (shifted) | `4.991095`   |
  | KS `orders_clean` vs baseline (stable)     | `0.000000`   |
  | KS `orders_drifted` vs baseline (shifted)  | `0.837217`   |
  | Quality score of fixed CheckResult list    | `75.0`       |

---

## Verification gates

These are the loop terminators for DataGuard (per `CONVENTIONS.md`):

1. **Each check type has pass + fail fixtures.** `tests/test_null_check.py`,
   `test_range_check.py`, `test_schema_check.py`, `test_freshness_check.py` each
   assert both a passing and a failing case.
2. **Drift flags a shift and passes a stable distribution.**
   `tests/test_drift.py` asserts **both directions** for PSI and KS, on the
   actual seeded `orders_clean` (PSI 0.0, pass) and `orders_drifted`
   (PSI 4.99, fail), plus golden PSI/KS constants.
3. **The quality score is deterministic for fixed inputs.**
   `tests/test_scoring.py` asserts a fixed `CheckResult` list scores exactly
   `75.0`, twice, plus severity-weighting behaviour.
4. **The dashboard renders against seeded results.** `make demo` seeds both
   tables, runs all checks, persists to `dq_results`, and brings up the API +
   Streamlit dashboard, which shows per-table scores, failing checks, and a
   trend line.

Run the unit gates:

```bash
make test     # -> 38 passed
```
