"""Quality scoring: aggregate ``CheckResult``s into a per-table score in [0, 100].

This module is PURE (no infra imports) and DETERMINISTIC: the same list of
``CheckResult`` objects always yields the same score.

Formula
-------
Each check contributes its continuous ``score`` (in ``[0, 1]``) weighted by the
severity weight of the check:

    info     -> weight 1
    warning  -> weight 2
    critical -> weight 3

The table score is the weighted mean of per-check scores, scaled to 0–100:

    table_score = 100 * ( sum(w_i * score_i) / sum(w_i) )

Using the continuous per-check score (rather than a binary pass/fail) means a
column that is 5% out-of-range is penalised proportionally less than one that is
80% out-of-range, while a critical check still dominates a merely-informational
one. An empty result list scores 100.0 (nothing known to be wrong).
"""

from __future__ import annotations

from typing import Dict, List

from dataguard.checks.base import CheckResult, Severity


def score_table(results: List[CheckResult]) -> float:
    """Weighted-mean quality score in ``[0, 100]`` for one table's checks."""
    if not results:
        return 100.0

    weighted_sum = 0.0
    weight_total = 0.0
    for r in results:
        w = Severity.WEIGHTS.get(r.severity, Severity.WEIGHTS[Severity.WARNING])
        weighted_sum += w * r.score
        weight_total += w

    if weight_total == 0.0:
        return 100.0

    return round(100.0 * (weighted_sum / weight_total), 4)


def score_all(results: List[CheckResult]) -> Dict[str, float]:
    """Group results by table and return ``{table: score}``.

    Deterministic: results are bucketed by table name and each bucket is scored
    with :func:`score_table`.
    """
    buckets: Dict[str, List[CheckResult]] = {}
    for r in results:
        buckets.setdefault(r.table, []).append(r)
    return {table: score_table(rs) for table, rs in buckets.items()}


def summarize(results: List[CheckResult]) -> Dict[str, object]:
    """A compact summary used by the API / runner logging.

    Returns counts and per-table scores. Deterministic for fixed input.
    """
    total = len(results)
    failed = sum(1 for r in results if not r.passed)
    by_table = score_all(results)
    return {
        "total_checks": total,
        "failed_checks": failed,
        "passed_checks": total - failed,
        "scores": by_table,
    }
