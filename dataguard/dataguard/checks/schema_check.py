"""Schema check: assert expected columns (and optionally dtypes) are present.

Pure function — pandas only.
"""

from __future__ import annotations

from typing import Any, Dict

import pandas as pd

from dataguard.checks.base import CheckResult, Severity


# Map of "logical type" -> a predicate over a pandas Series dtype. We keep this
# deliberately small and explicit so behaviour is obvious and deterministic.
def _matches_type(series: pd.Series, expected: str) -> bool:
    expected = (expected or "").lower()
    dtype = series.dtype
    if expected in ("", "any"):
        return True
    if expected in ("int", "integer", "bigint"):
        return pd.api.types.is_integer_dtype(dtype)
    if expected in ("float", "double", "numeric", "decimal"):
        return pd.api.types.is_float_dtype(dtype) or pd.api.types.is_integer_dtype(dtype)
    if expected in ("number",):
        return pd.api.types.is_numeric_dtype(dtype)
    if expected in ("str", "string", "text", "varchar", "object"):
        return pd.api.types.is_object_dtype(dtype) or pd.api.types.is_string_dtype(dtype)
    if expected in ("bool", "boolean"):
        return pd.api.types.is_bool_dtype(dtype)
    if expected in ("datetime", "timestamp", "date"):
        return pd.api.types.is_datetime64_any_dtype(dtype)
    # Unknown expected type: do not fail the build on it, just accept.
    return True


def schema_check(data: pd.DataFrame, config: Dict[str, Any]) -> CheckResult:
    """Verify that every expected column exists (and, if given, has a matching type).

    config keys
    -----------
    table:    table name (for reporting).
    columns:  list of expected column names, OR a dict ``{name: type}``.
    severity: optional severity override (default ``critical`` — a wrong schema
              is usually a hard failure).

    The score is the fraction of expected columns that are present AND typed
    correctly, in ``[0, 1]``.
    """
    table = config.get("table", "")
    severity = config.get("severity", Severity.CRITICAL)
    expected = config.get("columns", [])

    if isinstance(expected, dict):
        expected_types: Dict[str, str] = dict(expected)
        expected_cols = list(expected.keys())
    else:
        expected_cols = list(expected)
        expected_types = {c: "any" for c in expected_cols}

    if not expected_cols:
        return CheckResult(
            check="schema_check",
            table=table,
            column="",
            passed=True,
            score=1.0,
            detail="No expected columns configured; schema check is a no-op.",
            severity=severity,
        )

    present = [c for c in expected_cols if c in data.columns]
    missing = [c for c in expected_cols if c not in data.columns]

    type_mismatches = []
    for c in present:
        if not _matches_type(data[c], expected_types.get(c, "any")):
            type_mismatches.append(
                f"{c} (expected {expected_types.get(c)}, got {data[c].dtype})"
            )

    ok_count = len(present) - len(type_mismatches)
    score = ok_count / len(expected_cols)
    passed = (len(missing) == 0) and (len(type_mismatches) == 0)

    parts = [f"{ok_count}/{len(expected_cols)} expected columns present & typed"]
    if missing:
        parts.append(f"missing={missing}")
    if type_mismatches:
        parts.append(f"type_mismatch={type_mismatches}")
    detail = "; ".join(parts)

    return CheckResult(
        check="schema_check",
        table=table,
        column="",
        passed=passed,
        score=score,
        detail=detail,
        severity=severity,
    )
