"""Host-pure tests for schema_check (pass + fail fixtures)."""

import pandas as pd

from dataguard.checks.schema_check import schema_check


def _df():
    return pd.DataFrame(
        {
            "id": pd.Series([1, 2, 3], dtype="int64"),
            "amount": pd.Series([1.0, 2.0, 3.0], dtype="float64"),
            "status": pd.Series(["a", "b", "c"], dtype="object"),
        }
    )


def test_schema_check_passes_when_all_present_and_typed():
    result = schema_check(
        _df(),
        {"table": "orders", "columns": {"id": "int", "amount": "float", "status": "string"}},
    )
    assert result.passed is True
    assert result.score == 1.0


def test_schema_check_fails_on_missing_column():
    result = schema_check(
        _df(),
        {"table": "orders", "columns": {"id": "int", "amount": "float", "missing": "string"}},
    )
    assert result.passed is False
    # 2 of 3 expected columns present & typed
    assert abs(result.score - (2 / 3)) < 1e-9


def test_schema_check_fails_on_type_mismatch():
    # 'amount' is float, but we expect int -> mismatch
    result = schema_check(
        _df(),
        {"table": "orders", "columns": {"id": "int", "amount": "int", "status": "string"}},
    )
    assert result.passed is False
    assert abs(result.score - (2 / 3)) < 1e-9


def test_schema_check_accepts_list_of_columns():
    result = schema_check(_df(), {"table": "orders", "columns": ["id", "amount"]})
    assert result.passed is True
    assert result.score == 1.0


def test_schema_check_no_columns_is_noop_pass():
    result = schema_check(_df(), {"table": "orders", "columns": []})
    assert result.passed is True
    assert result.score == 1.0
