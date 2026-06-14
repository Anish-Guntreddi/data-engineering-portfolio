"""Freshness check: assert the newest row is within an SLA of ``now``.

``now`` is INJECTED via config so the function is pure and deterministic — it
never calls ``datetime.now()`` itself. Pure function — pandas only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

import pandas as pd

from dataguard.checks.base import CheckResult, Severity


def freshness_check(data: pd.DataFrame, config: Dict[str, Any]) -> CheckResult:
    """Fail when ``now - max(timestamp_col)`` exceeds the SLA.

    config keys
    -----------
    table:        table name (for reporting).
    column:       timestamp column to inspect.
    now:          reference time (``datetime`` or ISO string). REQUIRED — the
                  caller injects it so tests are deterministic.
    max_age_hours: SLA in hours (default ``24``).
    severity:     optional severity (default ``warning``).

    score: ``1.0`` when fresh, decaying linearly to ``0.0`` at twice the SLA.
    """
    table = config.get("table", "")
    column = config["column"]
    max_age_hours = float(config.get("max_age_hours", 24.0))
    severity = config.get("severity", Severity.WARNING)

    now_raw = config["now"]  # KeyError on purpose if caller forgot to inject.
    now = pd.to_datetime(now_raw)

    if column not in data.columns:
        return CheckResult(
            check="freshness_check",
            table=table,
            column=column,
            passed=False,
            score=0.0,
            detail=f"Column '{column}' not found in table '{table}'.",
            severity=severity,
        )

    ts = pd.to_datetime(data[column], errors="coerce").dropna()
    if len(ts) == 0:
        return CheckResult(
            check="freshness_check",
            table=table,
            column=column,
            passed=False,
            score=0.0,
            detail=f"No parseable timestamps in '{column}'.",
            severity=severity,
        )

    newest = ts.max()
    age_hours = (now - newest).total_seconds() / 3600.0
    passed = age_hours <= max_age_hours

    # Linear decay: full score within SLA, 0 once we hit 2x the SLA.
    if age_hours <= max_age_hours:
        score = 1.0
    elif age_hours >= 2.0 * max_age_hours:
        score = 0.0
    else:
        span = max_age_hours  # from SLA -> 2*SLA
        score = 1.0 - (age_hours - max_age_hours) / span

    detail = (
        f"newest={newest.isoformat()} now={now.isoformat()} "
        f"age_hours={age_hours:.2f} sla_hours={max_age_hours:.2f}"
    )

    return CheckResult(
        check="freshness_check",
        table=table,
        column=column,
        passed=passed,
        score=score,
        detail=detail,
        severity=severity,
    )
