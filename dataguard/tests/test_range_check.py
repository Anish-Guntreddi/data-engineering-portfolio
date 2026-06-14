"""Host-pure tests for range_check (pass + fail fixtures)."""

import pandas as pd

from dataguard.checks.range_check import range_check


def test_range_check_passes_all_in_range():
    df = pd.DataFrame({"amount": [10, 20, 30, 40]})
    result = range_check(
        df, {"table": "orders", "column": "amount", "min": 0, "max": 100, "threshold": 1.0}
    )
    assert result.passed is True
    assert result.score == 1.0


def test_range_check_fails_with_out_of_range():
    # 2 of 4 out of range (-5 and 500) -> in_range fraction 0.5, threshold 1.0 -> fail
    df = pd.DataFrame({"amount": [-5, 20, 30, 500]})
    result = range_check(
        df, {"table": "orders", "column": "amount", "min": 0, "max": 100, "threshold": 1.0}
    )
    assert result.passed is False
    assert result.score == 0.5


def test_range_check_passes_under_threshold():
    # 1 of 10 out of range -> 0.9 in range, threshold 0.8 -> pass
    df = pd.DataFrame({"amount": [10] * 9 + [-1]})
    result = range_check(
        df, {"table": "orders", "column": "amount", "min": 0, "max": 100, "threshold": 0.8}
    )
    assert result.passed is True
    assert abs(result.score - 0.9) < 1e-9


def test_range_check_ignores_nulls():
    # nulls are dropped; remaining 3 all in range -> pass
    df = pd.DataFrame({"amount": [10, None, 30, None]})
    result = range_check(
        df, {"table": "orders", "column": "amount", "min": 0, "max": 100, "threshold": 1.0}
    )
    assert result.passed is True
    assert result.score == 1.0


def test_range_check_open_bounds():
    df = pd.DataFrame({"amount": [-1000, 0, 5000]})
    # only a min bound; everything >= 0 except -1000 -> 2/3 in range
    result = range_check(
        df, {"table": "orders", "column": "amount", "min": 0, "threshold": 1.0}
    )
    assert result.passed is False
    assert abs(result.score - (2 / 3)) < 1e-9
