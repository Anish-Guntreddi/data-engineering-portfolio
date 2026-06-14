"""Metric computation from windowed aggregates.

PURE module: standard library only. NO infra imports.

Given the ordered windows produced by ``windowing.tumbling_windows`` this module
computes per-window metric rows. Each row is shaped to match the ``metrics``
postgres table:

    {
        "window_start": float,   # epoch seconds (inclusive)
        "window_end":   float,   # epoch seconds (exclusive)
        "metric":       str,     # "events_per_minute" | "conversion_rate"
        "value":        float,
    }

Definitions
-----------
events_per_minute
    total events in the window scaled to a per-minute rate:
    ``total / (window_seconds / 60)``. For a 60s window this is just ``total``.

conversion_rate
    purchases divided by page_views in the window. If there are no page_views
    the rate is defined as 0.0 (no traffic -> no conversion to report). The
    value is in the range [0, +inf) but realistically << 1.
"""

from __future__ import annotations

from typing import Dict, List

EVENTS_PER_MINUTE = "events_per_minute"
CONVERSION_RATE = "conversion_rate"


def events_per_minute(window: Dict, window_seconds: int) -> float:
    """Per-minute event rate for a single window."""
    if window_seconds <= 0:
        raise ValueError("window_seconds must be a positive integer")
    minutes = window_seconds / 60.0
    return float(window["total"]) / minutes


def conversion_rate(window: Dict) -> float:
    """purchases / page_views for a single window (0.0 if no page_views)."""
    counts = window.get("counts", {})
    page_views = counts.get("page_view", 0)
    purchases = counts.get("purchase", 0)
    if page_views == 0:
        return 0.0
    return float(purchases) / float(page_views)


def compute_metrics(windows: List[Dict], window_seconds: int) -> List[Dict]:
    """Compute metric rows for every window.

    Produces two rows per window (events_per_minute and conversion_rate),
    ordered by window_start then metric name, so output is deterministic.
    """
    rows: List[Dict] = []
    for win in sorted(windows, key=lambda w: w["window_start"]):
        rows.append(
            {
                "window_start": win["window_start"],
                "window_end": win["window_end"],
                "metric": EVENTS_PER_MINUTE,
                "value": events_per_minute(win, window_seconds),
            }
        )
        rows.append(
            {
                "window_start": win["window_start"],
                "window_end": win["window_end"],
                "metric": CONVERSION_RATE,
                "value": conversion_rate(win),
            }
        )
    return rows
