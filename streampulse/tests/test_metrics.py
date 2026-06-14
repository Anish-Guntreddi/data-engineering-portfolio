"""Exact tests for the pure metric computations.

Golden constants derived from running the pure generator + windowing + metrics
on the host.
"""

import math

from streampulse.events import generate_batch
from streampulse.metrics import (
    CONVERSION_RATE,
    EVENTS_PER_MINUTE,
    compute_metrics,
    conversion_rate,
    events_per_minute,
)
from streampulse.windowing import tumbling_windows


def _window(total, page_view=0, purchase=0, session_start=0, add_to_cart=0):
    return {
        "window_start": 0.0,
        "window_end": 60.0,
        "total": total,
        "counts": {
            "page_view": page_view,
            "session_start": session_start,
            "add_to_cart": add_to_cart,
            "purchase": purchase,
        },
    }


def test_events_per_minute_scaling():
    # 60s window: rate == total.
    assert events_per_minute(_window(120), 60) == 120.0
    # 30s window: rate == total * 2.
    assert events_per_minute(_window(50), 30) == 100.0
    # 120s window: rate == total / 2.
    assert events_per_minute(_window(100), 120) == 50.0


def test_conversion_rate_math():
    # 10 purchases / 100 page_views = 0.10 exactly.
    assert conversion_rate(_window(110, page_view=100, purchase=10)) == 0.10
    # 1 / 4 = 0.25.
    assert conversion_rate(_window(5, page_view=4, purchase=1)) == 0.25


def test_conversion_rate_zero_page_views_is_zero():
    assert conversion_rate(_window(3, page_view=0, purchase=2)) == 0.0
    assert conversion_rate(_window(0)) == 0.0


def test_compute_metrics_golden_rows():
    """seed=7, n=120, aligned start -> two windows, exact metric values."""
    start = 1_700_000_040.0
    batch = generate_batch(seed=7, n=120, start_ts=start, step_seconds=1.0)
    windows = tumbling_windows(batch, 60)
    rows = compute_metrics(windows, 60)

    # Two windows x two metrics = 4 rows.
    assert len(rows) == 4

    # Index by (window_start, metric) for exact assertions.
    by_key = {(r["window_start"], r["metric"]): r["value"] for r in rows}

    assert by_key[(1_700_000_040.0, EVENTS_PER_MINUTE)] == 60.0
    assert by_key[(1_700_000_100.0, EVENTS_PER_MINUTE)] == 60.0

    # Window 0: 2 purchases / 30 page_views = 0.0666...
    assert math.isclose(
        by_key[(1_700_000_040.0, CONVERSION_RATE)], 2 / 30, rel_tol=0, abs_tol=1e-12
    )
    # Window 1: 2 purchases / 35 page_views = 0.0571...
    assert math.isclose(
        by_key[(1_700_000_100.0, CONVERSION_RATE)], 2 / 35, rel_tol=0, abs_tol=1e-12
    )


def test_compute_metrics_row_order_deterministic():
    start = 1_700_000_040.0
    batch = generate_batch(seed=7, n=120, start_ts=start, step_seconds=1.0)
    windows = tumbling_windows(batch, 60)
    rows = compute_metrics(windows, 60)
    # Ordered by window_start, then events_per_minute before conversion_rate.
    seq = [(r["window_start"], r["metric"]) for r in rows]
    assert seq == [
        (1_700_000_040.0, EVENTS_PER_MINUTE),
        (1_700_000_040.0, CONVERSION_RATE),
        (1_700_000_100.0, EVENTS_PER_MINUTE),
        (1_700_000_100.0, CONVERSION_RATE),
    ]
