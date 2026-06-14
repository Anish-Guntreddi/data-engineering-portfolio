"""Exact golden-value tests for the pure tumbling-window logic.

These run on the host (no Docker, no kafka). Golden constants were derived by
actually running the pure generator + windowing on the host.
"""

import math

from streampulse.events import generate_batch
from streampulse.windowing import tumbling_windows, window_bounds


def test_window_bounds_alignment():
    assert window_bounds(100.0, 60) == (60.0, 120.0)
    assert window_bounds(159.999, 60) == (120.0, 180.0)
    assert window_bounds(160.0, 60) == (120.0, 180.0)
    assert window_bounds(180.0, 60) == (180.0, 240.0)


def test_small_known_batch_exact_counts():
    """A hand-checkable batch mixing epoch floats and an ISO timestamp."""
    events = [
        {"event_id": "a", "event_type": "page_view", "event_ts": 100.0,
         "user_id": "u1", "session_id": "s1"},
        {"event_id": "b", "event_type": "purchase", "event_ts": 100.5,
         "user_id": "u1", "session_id": "s1"},
        {"event_id": "c", "event_type": "page_view", "event_ts": 159.999,
         "user_id": "u2", "session_id": "s2"},
        {"event_id": "d", "event_type": "page_view", "event_ts": 160.0,
         "user_id": "u3", "session_id": "s3"},
        # ISO-8601 with trailing Z -> epoch 180.0
        {"event_id": "e", "event_type": "session_start",
         "event_ts": "1970-01-01T00:03:00Z", "user_id": "u3", "session_id": "s3"},
        {"event_id": "f", "event_type": "purchase", "event_ts": 215.0,
         "user_id": "u4", "session_id": "s4"},
    ]
    windows = tumbling_windows(events, 60)

    assert len(windows) == 3

    w0, w1, w2 = windows
    # Window [60,120): page_view a + purchase b
    assert (w0["window_start"], w0["window_end"]) == (60.0, 120.0)
    assert w0["total"] == 2
    assert w0["counts"]["page_view"] == 1
    assert w0["counts"]["purchase"] == 1
    assert w0["counts"]["session_start"] == 0
    assert w0["counts"]["add_to_cart"] == 0

    # Window [120,180): page_view c (159.999) + page_view d (160.0)
    assert (w1["window_start"], w1["window_end"]) == (120.0, 180.0)
    assert w1["total"] == 2
    assert w1["counts"]["page_view"] == 2
    assert w1["counts"]["purchase"] == 0

    # Window [180,240): session_start e (ISO 180) + purchase f (215)
    assert (w2["window_start"], w2["window_end"]) == (180.0, 240.0)
    assert w2["total"] == 2
    assert w2["counts"]["session_start"] == 1
    assert w2["counts"]["purchase"] == 1
    assert w2["counts"]["page_view"] == 0


def test_deterministic_batch_golden_windows():
    """seed=7, n=120, aligned start -> exactly two full 60s windows.

    Golden constants baked from running the pure logic on the host.
    """
    start = 1_700_000_040.0  # divisible by 60
    batch = generate_batch(seed=7, n=120, start_ts=start, step_seconds=1.0)
    assert len(batch) == 120

    windows = tumbling_windows(batch, 60)
    assert len(windows) == 2

    w0, w1 = windows
    assert (w0["window_start"], w0["window_end"]) == (1_700_000_040.0, 1_700_000_100.0)
    assert w0["total"] == 60
    assert w0["counts"] == {
        "page_view": 30,
        "session_start": 18,
        "add_to_cart": 10,
        "purchase": 2,
    }

    assert (w1["window_start"], w1["window_end"]) == (1_700_000_100.0, 1_700_000_160.0)
    assert w1["total"] == 60
    assert w1["counts"] == {
        "page_view": 35,
        "session_start": 19,
        "add_to_cart": 4,
        "purchase": 2,
    }

    # Totals across windows must equal the batch size.
    assert sum(w["total"] for w in windows) == 120


def test_batch_is_deterministic():
    a = generate_batch(seed=7, n=50)
    b = generate_batch(seed=7, n=50)
    assert a == b
    # Different seed -> different stream of types (extremely likely).
    c = generate_batch(seed=8, n=50)
    assert [e["event_type"] for e in a] != [e["event_type"] for e in c]


def test_windows_sorted_and_no_empty():
    batch = generate_batch(seed=7, n=200, start_ts=0.0, step_seconds=1.0)
    windows = tumbling_windows(batch, 60)
    starts = [w["window_start"] for w in windows]
    assert starts == sorted(starts)
    assert all(w["total"] > 0 for w in windows)
    assert all(not math.isnan(w["window_start"]) for w in windows)
