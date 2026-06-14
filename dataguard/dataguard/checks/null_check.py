"""Null check: assert the null fraction of a column is <= a threshold.

Pure function — pandas only.
"""

from __future__ import annotations

from typing import Any, Dict

import pandas as pd

from dataguard.checks.base import CheckResult, Severity


def null_check(data: pd.DataFrame, config: Dict[str, Any]) -> CheckResult:
    """Fail when the fraction of nulls in ``column`` exceeds ``threshold``.

    config keys
    -----------
    table:     table name (for reporting).
    column:    column to inspect.
    threshold: max allowed null fraction in ``[0, 1]`` (default ``0.0``).
    severity:  optional severity (default ``warning``).

    score = ``1 - null_fraction`` (1.0 means no nulls).
    """
    table = config.get("table", "")
    column = config["column"]
    threshold = float(config.get("threshold", 0.0))
    severity = config.get("severity", Severity.WARNING)

    if column not in data.columns:
        return CheckResult(
            check="null_check",
            table=table,
            column=column,
            passed=False,
            score=0.0,
            detail=f"Column '{column}' not found in table '{table}'.",
            severity=severity,
        )

    n = len(data)
    if n == 0:
        # An empty table has no nulls; treat as a pass but flag it in detail.
        return CheckResult(
            check="null_check",
            table=table,
            column=column,
            passed=True,
            score=1.0,
            detail=f"Table '{table}' is empty; null fraction is 0/0.",
            severity=severity,
        )

    null_count = int(data[column].isna().sum())
    null_fraction = null_count / n
    passed = null_fraction <= threshold
    score = 1.0 - null_fraction

    detail = (
        f"null_fraction={null_fraction:.4f} ({null_count}/{n}) "
        f"threshold={threshold:.4f}"
    )

    return CheckResult(
        check="null_check",
        table=table,
        column=column,
        passed=passed,
        score=score,
        detail=detail,
        severity=severity,
    )
