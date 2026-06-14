"""Range check: assert values fall within ``[min, max]``.

The check passes when the fraction of in-range (non-null) values is >= a
threshold. Pure function — pandas only.
"""

from __future__ import annotations

from typing import Any, Dict

import pandas as pd

from dataguard.checks.base import CheckResult, Severity


def range_check(data: pd.DataFrame, config: Dict[str, Any]) -> CheckResult:
    """Fail when too many values fall outside ``[min, max]``.

    config keys
    -----------
    table:     table name (for reporting).
    column:    numeric column to inspect.
    min:       inclusive lower bound (optional; ``-inf`` if omitted).
    max:       inclusive upper bound (optional; ``+inf`` if omitted).
    threshold: minimum required fraction of in-range values in ``[0, 1]``
               (default ``1.0`` — everything must be in range).
    severity:  optional severity (default ``warning``).

    Nulls are ignored when computing the in-range fraction (use ``null_check``
    for null coverage). score = in-range fraction.
    """
    table = config.get("table", "")
    column = config["column"]
    lo = config.get("min", None)
    hi = config.get("max", None)
    threshold = float(config.get("threshold", 1.0))
    severity = config.get("severity", Severity.WARNING)

    lo = float("-inf") if lo is None else float(lo)
    hi = float("inf") if hi is None else float(hi)

    if column not in data.columns:
        return CheckResult(
            check="range_check",
            table=table,
            column=column,
            passed=False,
            score=0.0,
            detail=f"Column '{column}' not found in table '{table}'.",
            severity=severity,
        )

    series = pd.to_numeric(data[column], errors="coerce").dropna()
    n = len(series)
    if n == 0:
        return CheckResult(
            check="range_check",
            table=table,
            column=column,
            passed=True,
            score=1.0,
            detail=f"No non-null numeric values in '{column}'; nothing to range-check.",
            severity=severity,
        )

    in_range = ((series >= lo) & (series <= hi)).sum()
    in_range_fraction = int(in_range) / n
    passed = in_range_fraction >= threshold
    score = in_range_fraction

    detail = (
        f"in_range_fraction={in_range_fraction:.4f} ({int(in_range)}/{n}) "
        f"bounds=[{lo}, {hi}] threshold={threshold:.4f}"
    )

    return CheckResult(
        check="range_check",
        table=table,
        column=column,
        passed=passed,
        score=score,
        detail=detail,
        severity=severity,
    )
