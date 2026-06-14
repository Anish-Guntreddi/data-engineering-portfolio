"""Orchestrates a full data-quality run.

Flow:
  1. Load expectations from ``expectations/*.yml`` (config.py).
  2. For each table, pull it from Postgres (db.py) into a DataFrame.
  3. Run each configured check (pure functions in checks/).
  4. Score each table (scoring.py).
  5. Persist every CheckResult + the table score to ``dq_results``.

This module imports ``db`` (infra), so it is containerized. The checks it calls
remain pure.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

import pandas as pd

from dataguard import db
from dataguard.checks.base import CheckResult, Severity
from dataguard.checks.drift import drift_check
from dataguard.checks.freshness_check import freshness_check
from dataguard.checks.null_check import null_check
from dataguard.checks.range_check import range_check
from dataguard.checks.schema_check import schema_check
from dataguard.config import load_expectations
from dataguard.scoring import score_table

# Dispatch table mapping a check "type" string to its pure implementation.
CHECK_DISPATCH = {
    "schema_check": schema_check,
    "null_check": null_check,
    "range_check": range_check,
    "freshness_check": freshness_check,
    "drift_check": drift_check,
}

# Safe identifiers we are allowed to read as whole tables.
_READABLE_TABLES = frozenset({"orders_clean", "orders_drifted"})


def _load_table(table: str) -> pd.DataFrame:
    """Read an allowlisted demo table into a DataFrame via a parameter-free query."""
    if table not in _READABLE_TABLES:
        raise ValueError(f"Refusing to read non-allowlisted table: {table!r}")
    # Static, allowlisted SELECT — no interpolation of user input.
    queries = {
        "orders_clean": "SELECT * FROM orders_clean",
        "orders_drifted": "SELECT * FROM orders_drifted",
    }
    return db.query_df(queries[table])


def _resolve_baseline(check_cfg: Dict[str, Any]) -> List[float]:
    """Resolve a drift baseline.

    Supports two forms in the expectation file:
      * ``baseline_table``: read that table and use ``baseline_column`` values.
      * ``baseline``: an inline list of numbers.
    Defaults to the clean orders amount distribution.
    """
    if "baseline" in check_cfg and check_cfg["baseline"]:
        return [float(x) for x in check_cfg["baseline"]]

    baseline_table = check_cfg.get("baseline_table", "orders_clean")
    baseline_column = check_cfg.get("baseline_column", check_cfg.get("column"))
    df = _load_table(baseline_table)
    series = pd.to_numeric(df[baseline_column], errors="coerce").dropna()
    return series.astype(float).tolist()


def _build_config(table: str, expectation: Dict[str, Any], check_cfg: Dict[str, Any],
                  now: datetime) -> Dict[str, Any]:
    """Merge table-level + check-level settings into a single check config dict."""
    cfg: Dict[str, Any] = dict(check_cfg)
    cfg["table"] = table
    cfg.pop("type", None)

    ctype = check_cfg["type"]
    if ctype == "schema_check":
        # Pull the schema map from the expectation file.
        cfg.setdefault("columns", expectation.get("schema", {}))
    if ctype == "freshness_check":
        cfg["now"] = now
        cfg.setdefault("column", expectation.get("timestamp_column", "created_at"))
    if ctype == "drift_check":
        cfg["baseline"] = _resolve_baseline(check_cfg)
    return cfg


def run_checks_for_table(table: str, expectation: Dict[str, Any],
                         now: datetime) -> List[CheckResult]:
    """Run every configured check for one table and return the results."""
    df = _load_table(table)
    results: List[CheckResult] = []
    for check_cfg in expectation.get("checks", []):
        ctype = check_cfg.get("type")
        fn = CHECK_DISPATCH.get(ctype)
        if fn is None:
            results.append(
                CheckResult(
                    check=str(ctype),
                    table=table,
                    column=check_cfg.get("column", ""),
                    passed=False,
                    score=0.0,
                    detail=f"Unknown check type: {ctype!r}",
                    severity=Severity.WARNING,
                )
            )
            continue
        cfg = _build_config(table, expectation, check_cfg, now)
        results.append(fn(df, cfg))
    return results


def _persist(run_id: str, run_ts: datetime, table: str, table_score: float,
             results: List[CheckResult]) -> None:
    """Insert all results for one table into ``dq_results``."""
    rows = [
        (
            run_id,
            run_ts,
            r.table,
            r.column,
            r.check,
            bool(r.passed),
            float(r.score),
            r.severity,
            r.detail,
            float(table_score),
        )
        for r in results
    ]
    db.insert_dq_results(rows)


def run(now: datetime | None = None) -> Dict[str, Any]:
    """Execute a full run across all expectation files and persist results.

    Returns a summary dict ``{run_id, scores, total_checks, failed_checks}``.
    """
    if now is None:
        # The only place a wall-clock time enters the system. Pure checks still
        # receive it injected, so they remain deterministic in tests.
        now = datetime.now(timezone.utc)

    run_id = uuid.uuid4().hex
    run_ts = now

    db.ensure_results_table()

    expectations = load_expectations()
    all_scores: Dict[str, float] = {}
    total = 0
    failed = 0

    for expectation in expectations:
        table = expectation["table"]
        results = run_checks_for_table(table, expectation, now)
        table_score = score_table(results)
        all_scores[table] = table_score
        _persist(run_id, run_ts, table, table_score, results)
        total += len(results)
        failed += sum(1 for r in results if not r.passed)

    return {
        "run_id": run_id,
        "run_ts": run_ts.isoformat(),
        "scores": all_scores,
        "total_checks": total,
        "failed_checks": failed,
    }


if __name__ == "__main__":
    # Use the deterministic reference time from the seeder so a fresh demo run
    # produces stable freshness results.
    from dataguard.seed.seed import REFERENCE_NOW

    use_now = REFERENCE_NOW
    if os.environ.get("DATAGUARD_USE_WALLCLOCK") == "1":
        use_now = datetime.now(timezone.utc)
    summary = run(now=use_now)
    print("DataGuard run complete:")
    print(f"  run_id={summary['run_id']}")
    for tbl, score in sorted(summary["scores"].items()):
        print(f"  {tbl}: quality_score={score}")
    print(f"  total_checks={summary['total_checks']} "
          f"failed_checks={summary['failed_checks']}")
