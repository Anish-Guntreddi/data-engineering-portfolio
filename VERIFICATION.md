# Verification status

This records exactly what was verified for each project and how to reproduce it.
The guiding principle of this portfolio is that **the gates decide done** — every
project was driven to a green verification signal.

## Summary — all gates green ✅

| Layer | WarehouseLab | StreamPulse | DataGuard | How |
|-------|:---:|:---:|:---:|-----|
| Host unit tests (pure logic gates) | ✅ 12/12 | ✅ 18/18 | ✅ 41/41 | `make test` (no Docker) |
| `docker compose config` valid | ✅ | ✅ | ✅ | client-side render with `.env` |
| Runtime image builds | ✅ | ✅ | ✅ | `docker build` |
| **Containerized runtime e2e** | **✅ PASS** | **✅ PASS** | **✅ PASS** | `make run` / `make e2e` / `make demo` |

**71/71 host unit tests pass** and **all three full runtime e2e runs pass** against real
Postgres / dbt / Redpanda in Docker. Everything below is observed output, not intent.

---

## WarehouseLab — `make run` (real Postgres + dbt)

```
[load] loaded users=500 events=5691 orders=1135
[load] golden date=2024-01-11 dau=57 revenue=1175.29 n_orders=35
51 of 70 PASS assert_dau_golden ......................... [PASS]
56 of 70 PASS assert_revenue_golden ..................... [PASS]
Done. PASS=70 WARN=0 ERROR=0 SKIP=0 TOTAL=70
[pipeline] SUCCESS: marts populated and all dbt tests passed
```

- ✅ empty → populated marts (`fct_daily_active_users`, `fct_revenue_by_day`, `dim_users`)
- ✅ `dbt build` — **70/70** model + data tests pass
- ✅ golden-value: `assert_dau_golden` (DAU=57) **and** `assert_revenue_golden` (1175.29) pass
- ✅ `dbt docs generate` — `catalog.json` + `manifest.json` written (lineage builds clean)

## StreamPulse — `make e2e` (Redpanda + windowed processor + alerter)

```
[e2e] recent_metrics=4 alerts=4 (metrics_ok=True alerts_ok=True)
  Gate 1 — recent metrics populated : PASS (recent rows=4)
  Gate 2 — alert fired on breach     : PASS (alert rows=4)
E2E PASSED
```

- ✅ exact windowed aggregates (host tests, 18/18)
- ✅ integration run populates the metrics table within the window (recent rows = 4)
- ✅ alert fires on a forced threshold breach (alert rows = 4)
- ✅ `docker compose up` brings the whole pipeline up (redpanda, postgres, producer,
  processor, alerter, dashboard)

> Build note: the four app services share one image (`streampulse-app`). The Makefile
> builds it **once** (`compose build producer`) before `up`, because parallel builds of
> the same tag race under the containerd image store — fixed in `streampulse/Makefile`.

## DataGuard — `make demo` (check engine + FastAPI + Streamlit)

```
GET /health   -> {"status":"ok","db":true}
GET /tables   -> ["dq_results","orders_clean","orders_drifted"]
GET /scores   -> orders_clean=100.0, orders_drifted=64.0471
dashboard :8501 -> HTTP 200
```

Per-check results for the drifted table (all deterministic, seed=1337):

| check | result | detail |
|-------|--------|--------|
| drift_check | FAIL | PSI=4.9911 (>0.2), KS=0.8372 |
| freshness_check | FAIL | age 240h > SLA |
| null_check | FAIL (0.92) | null_fraction 0.0800 |
| range_check (amount) | FAIL (0.92) | 92.28% in [0,10000] |
| range_check (quantity) | PASS | 100% in [1,10] |
| schema_check | PASS | 5/5 columns present & typed |

- ✅ each check type covered with pass + fail fixtures (host tests, 41/41)
- ✅ drift flags the shifted distribution (PSI 4.99) and passes the stable one (PSI 0.0)
- ✅ the quality score is deterministic for fixed inputs
- ✅ the dashboard renders against seeded results (HTTP 200, real scores served)

> Golden-value note: the host **DB-free** integration test asserts `orders_drifted=59.0471`
> from an in-memory fixture where `amount` is read as `object` dtype (so `schema_check`
> fails). Against **real Postgres**, `amount` is a proper numeric column, so `schema_check`
> correctly **passes** (the table's defect is in *values/freshness*, not schema), giving the
> real end-to-end score **64.0471**. Both are deterministic; 64.0471 is the true e2e value.

---

## Host unit tests (no Docker)

```bash
cd warehouselab && make test     # 12 passed — generator determinism + golden DAU/revenue
cd streampulse  && make test     # 18 passed — exact tumbling-window aggregates, conversion, alerting
cd dataguard    && make test     # 41 passed — each check pass/fail, PSI+KS both directions, scoring
```

## Reproducing the full e2e (Docker)

```bash
cd warehouselab && cp -n .env.example .env && make run    # + make docs for the lineage gate
cd streampulse  && cp -n .env.example .env && make e2e
cd dataguard    && cp -n .env.example .env && make demo    # then curl :8201/scores ; open :8501
```

> On a busy machine, override the published host ports in each project's `.env` (the
> container-internal ports never change). See `CONVENTIONS.md` for the port map.
>
> All three e2e runs in this repo were executed on a disk-constrained host (≈400 GB used
> by other projects); they pass once Docker has a few GB of free space.
