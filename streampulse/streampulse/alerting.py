"""Threshold-based alerting.

PURE module: standard library only. NO infra imports.

``evaluate_thresholds`` takes metric rows (the same dict shape produced by
``metrics.compute_metrics`` or read back from the ``metrics`` postgres table) and
a threshold config, and returns a list of ``Alert`` dicts for every row that
breaches its rule.

Threshold config shape::

    {
        "events_per_minute": {"op": "gt", "threshold": 300},
        "conversion_rate":   {"op": "lt", "threshold": 0.02},
    }

``op`` is one of: gt, ge, lt, le. A row breaches when ``value <op> threshold``
is True. Metrics without an entry in the config are ignored.

Each returned Alert is shaped to match the ``alerts`` postgres table::

    {
        "ts":        float,   # window_end of the breaching row (epoch seconds)
        "metric":    str,
        "value":     float,
        "threshold": float,
        "message":   str,
    }
"""

from __future__ import annotations

from typing import Dict, List

_OPS = {
    "gt": lambda v, t: v > t,
    "ge": lambda v, t: v >= t,
    "lt": lambda v, t: v < t,
    "le": lambda v, t: v <= t,
}

_OP_SYMBOL = {"gt": ">", "ge": ">=", "lt": "<", "le": "<="}


def _format_message(metric: str, value: float, op: str, threshold: float) -> str:
    sym = _OP_SYMBOL[op]
    return f"{metric}={value:.4f} breached threshold ({sym} {threshold})"


def evaluate_thresholds(
    metric_rows: List[Dict],
    thresholds: Dict[str, Dict],
) -> List[Dict]:
    """Return alerts for every metric row that breaches its threshold rule.

    Pure and deterministic: input order is preserved in the output. Rows whose
    metric has no configured rule are skipped. Unknown ops raise ValueError so
    misconfiguration fails loudly.
    """
    alerts: List[Dict] = []
    for row in metric_rows:
        metric = row["metric"]
        rule = thresholds.get(metric)
        if rule is None:
            continue
        op = rule["op"]
        threshold = float(rule["threshold"])
        if op not in _OPS:
            raise ValueError(f"Unknown threshold op: {op!r}")
        value = float(row["value"])
        if _OPS[op](value, threshold):
            ts = float(row.get("window_end", row.get("window_start", 0.0)))
            alerts.append(
                {
                    "ts": ts,
                    "metric": metric,
                    "value": value,
                    "threshold": threshold,
                    "message": _format_message(metric, value, op, threshold),
                }
            )
    return alerts
