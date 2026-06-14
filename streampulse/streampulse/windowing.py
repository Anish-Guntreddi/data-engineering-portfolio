"""Tumbling-window aggregation.

PURE module: standard library only. NO kafka / postgres imports, so the
windowing logic is unit-tested on the host with exact golden counts.

A *tumbling window* is a fixed-size, non-overlapping bucket of time. Given a
``window_seconds`` of 60, an event at epoch ts is assigned to the window whose
start is ``floor(ts / 60) * 60`` and whose end is ``start + 60``.

``tumbling_windows`` returns an ordered list (ascending by window_start) of
``Window`` dicts, each shaped:

    {
        "window_start": float,          # inclusive epoch start
        "window_end":   float,          # exclusive epoch end
        "total":        int,            # total events in the window
        "counts": {                     # per-event-type counts
            "page_view": int,
            "session_start": int,
            "add_to_cart": int,
            "purchase": int,
        },
    }
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Iterable, List

from .events import EVENT_TYPES


def _coerce_ts(value) -> float:
    """Coerce an event timestamp to epoch seconds (float).

    Accepts an int/float epoch, or an ISO-8601 string (with optional trailing
    'Z'). Raises ValueError on anything else so bad data fails loudly.
    """
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    raise ValueError(f"Unsupported event_ts type: {type(value)!r}")


def window_bounds(ts: float, window_seconds: int) -> tuple[float, float]:
    """Return the (start, end) tumbling-window bounds for ``ts``."""
    if window_seconds <= 0:
        raise ValueError("window_seconds must be a positive integer")
    start = (int(ts) // window_seconds) * window_seconds
    return float(start), float(start + window_seconds)


def _empty_counts() -> Dict[str, int]:
    return {etype: 0 for etype in EVENT_TYPES}


def tumbling_windows(
    events: Iterable[Dict],
    window_seconds: int,
) -> List[Dict]:
    """Aggregate ``events`` into ordered tumbling windows.

    Each event must be a dict with ``event_ts`` (epoch seconds or ISO string)
    and ``event_type``. Event types outside ``EVENT_TYPES`` are still counted in
    ``total`` and tracked under their own key, so nothing is silently dropped.

    Windows with zero events are NOT emitted (only windows that actually contain
    events appear in the result). The result is sorted ascending by
    ``window_start``.
    """
    if window_seconds <= 0:
        raise ValueError("window_seconds must be a positive integer")

    buckets: Dict[float, Dict] = {}
    for ev in events:
        ts = _coerce_ts(ev["event_ts"])
        etype = ev["event_type"]
        start, end = window_bounds(ts, window_seconds)
        win = buckets.get(start)
        if win is None:
            win = {
                "window_start": start,
                "window_end": end,
                "total": 0,
                "counts": _empty_counts(),
            }
            buckets[start] = win
        win["total"] += 1
        if etype in win["counts"]:
            win["counts"][etype] += 1
        else:
            win["counts"][etype] = win["counts"].get(etype, 0) + 1

    return [buckets[k] for k in sorted(buckets.keys())]
