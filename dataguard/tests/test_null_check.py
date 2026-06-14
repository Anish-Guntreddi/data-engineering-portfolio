"""Host-pure tests for null_check (pass + fail fixtures)."""

import pandas as pd

from dataguard.checks.null_check import null_check


def test_null_check_passes_when_no_nulls():
    df = pd.DataFrame({"amount": [1.0, 2.0, 3.0, 4.0]})
    result = null_check(df, {"table": "orders", "column": "amount", "threshold": 0.0})
    assert result.passed is True
    assert result.score == 1.0
    assert result.check == "null_check"


def test_null_check_fails_when_nulls_exceed_threshold():
    # 2 of 4 are null -> null_fraction 0.5, threshold 0.1 -> fail
    df = pd.DataFrame({"amount": [1.0, None, 3.0, None]})
    result = null_check(df, {"table": "orders", "column": "amount", "threshold": 0.1})
    assert result.passed is False
    assert result.score == 0.5  # 1 - 0.5


def test_null_check_passes_under_threshold():
    # 1 of 10 null -> fraction 0.1, threshold 0.2 -> pass
    df = pd.DataFrame({"amount": [1.0] * 9 + [None]})
    result = null_check(df, {"table": "orders", "column": "amount", "threshold": 0.2})
    assert result.passed is True
    assert abs(result.score - 0.9) < 1e-9


def test_null_check_missing_column_fails():
    df = pd.DataFrame({"other": [1, 2]})
    result = null_check(df, {"table": "orders", "column": "amount", "threshold": 0.0})
    assert result.passed is False
    assert result.score == 0.0


def test_null_check_empty_table_passes():
    df = pd.DataFrame({"amount": pd.Series([], dtype="float64")})
    result = null_check(df, {"table": "orders", "column": "amount", "threshold": 0.0})
    assert result.passed is True
    assert result.score == 1.0
