"""Tests for the pure threshold-alerting logic.

Asserts the alerter fires on a forced breach and stays quiet on normal values.
"""

import pytest

from streampulse.alerting import evaluate_thresholds
from streampulse.metrics import CONVERSION_RATE, EVENTS_PER_MINUTE


THRESHOLDS = {
    EVENTS_PER_MINUTE: {"op": "gt", "threshold": 300},
    CONVERSION_RATE: {"op": "lt", "threshold": 0.02},
}


def _metric_row(metric, value, window_start=1000.0):
    return {
        "window_start": window_start,
        "window_end": window_start + 60.0,
        "metric": metric,
        "value": value,
    }


def test_quiet_on_normal_values():
    rows = [
        _metric_row(EVENTS_PER_MINUTE, 60.0),     # below 300 -> ok
        _metric_row(CONVERSION_RATE, 0.066667),   # above 0.02 -> ok
    ]
    alerts = evaluate_thresholds(rows, THRESHOLDS)
    assert alerts == []


def test_fires_on_events_per_minute_breach():
    rows = [_metric_row(EVENTS_PER_MINUTE, 720.0, window_start=2000.0)]
    alerts = evaluate_thresholds(rows, THRESHOLDS)
    assert len(alerts) == 1
    a = alerts[0]
    assert a["metric"] == EVENTS_PER_MINUTE
    assert a["value"] == 720.0
    assert a["threshold"] == 300.0
    assert a["ts"] == 2060.0  # window_end
    assert "720" in a["message"]
    assert ">" in a["message"]


def test_fires_on_low_conversion_breach():
    rows = [_metric_row(CONVERSION_RATE, 0.0, window_start=3000.0)]
    alerts = evaluate_thresholds(rows, THRESHOLDS)
    assert len(alerts) == 1
    a = alerts[0]
    assert a["metric"] == CONVERSION_RATE
    assert a["value"] == 0.0
    assert a["threshold"] == 0.02
    assert "<" in a["message"]


def test_boundary_is_not_a_breach_for_strict_ops():
    # value exactly equal to threshold must NOT fire for gt / lt.
    rows = [
        _metric_row(EVENTS_PER_MINUTE, 300.0),
        _metric_row(CONVERSION_RATE, 0.02),
    ]
    assert evaluate_thresholds(rows, THRESHOLDS) == []


def test_multiple_breaches_preserve_order():
    rows = [
        _metric_row(EVENTS_PER_MINUTE, 500.0, window_start=10.0),
        _metric_row(CONVERSION_RATE, 0.066667, window_start=10.0),   # ok
        _metric_row(EVENTS_PER_MINUTE, 50.0, window_start=70.0),     # ok
        _metric_row(CONVERSION_RATE, 0.001, window_start=70.0),
    ]
    alerts = evaluate_thresholds(rows, THRESHOLDS)
    assert [a["metric"] for a in alerts] == [EVENTS_PER_MINUTE, CONVERSION_RATE]
    assert [a["ts"] for a in alerts] == [70.0, 130.0]


def test_ge_and_le_ops():
    th = {
        EVENTS_PER_MINUTE: {"op": "ge", "threshold": 100},
        CONVERSION_RATE: {"op": "le", "threshold": 0.05},
    }
    rows = [
        _metric_row(EVENTS_PER_MINUTE, 100.0),   # ge -> fires
        _metric_row(CONVERSION_RATE, 0.05),      # le -> fires
    ]
    alerts = evaluate_thresholds(rows, th)
    assert len(alerts) == 2


def test_unconfigured_metric_ignored():
    rows = [_metric_row("some_other_metric", 9999.0)]
    assert evaluate_thresholds(rows, THRESHOLDS) == []


def test_unknown_op_raises():
    bad = {EVENTS_PER_MINUTE: {"op": "between", "threshold": 1}}
    with pytest.raises(ValueError):
        evaluate_thresholds([_metric_row(EVENTS_PER_MINUTE, 5.0)], bad)
