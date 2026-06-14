"""Distribution drift detection.

Two statistics, both implemented BY HAND with numpy (no scipy):

* **PSI** (Population Stability Index) — the PRIMARY signal. It compares the
  share of mass falling in each of a fixed set of bins between a baseline and a
  current sample. Interpretation (industry-standard rule of thumb):

      PSI < 0.10            -> no significant shift
      0.10 <= PSI < 0.25    -> moderate shift (watch)
      PSI >= 0.25           -> significant shift (investigate)

  We flag drift when ``PSI > threshold`` (default ``0.2``).

* **KS statistic** (Kolmogorov–Smirnov) — the SECONDARY signal. It is the
  maximum absolute difference between the two empirical CDFs. We compute only
  the statistic D (not the p-value), so no scipy is required.

``drift_check`` glues these onto the ``(data, config) -> CheckResult`` contract.
Pure module — numpy/pandas only, NO infra imports.
"""

from __future__ import annotations

from typing import Any, Dict, Sequence

import numpy as np
import pandas as pd

from dataguard.checks.base import CheckResult, Severity


def psi(
    expected_counts: Sequence[float],
    actual_counts: Sequence[float],
    bins: int = 10,
) -> float:
    """Population Stability Index from two count vectors.

    Parameters
    ----------
    expected_counts, actual_counts:
        Per-bin counts (or proportions) for the baseline and the current
        sample. They are normalised to proportions internally, so raw counts
        are fine and the two vectors need not sum to the same total.
    bins:
        Retained for API symmetry / documentation. The number of bins is
        actually defined by the length of the input vectors; ``bins`` is used
        only when the vectors are empty (degenerate guard).

    Returns
    -------
    float
        The PSI value, ``sum((a_i - e_i) * ln(a_i / e_i))`` over bins, where
        ``e_i`` and ``a_i`` are the baseline / current proportions. Empty or
        zero bins are floored with a small epsilon so the log is finite.
    """
    e = np.asarray(expected_counts, dtype=float)
    a = np.asarray(actual_counts, dtype=float)

    if e.shape != a.shape:
        raise ValueError(
            f"expected_counts and actual_counts must have the same shape; "
            f"got {e.shape} and {a.shape}"
        )
    if e.size == 0:
        return 0.0

    e_sum = e.sum()
    a_sum = a.sum()
    if e_sum <= 0 or a_sum <= 0:
        return 0.0

    e_prop = e / e_sum
    a_prop = a / a_sum

    # Floor proportions so empty bins don't blow up the logarithm. 1e-6 is a
    # widely used PSI epsilon.
    eps = 1e-6
    e_prop = np.clip(e_prop, eps, None)
    a_prop = np.clip(a_prop, eps, None)

    psi_terms = (a_prop - e_prop) * np.log(a_prop / e_prop)
    return float(np.sum(psi_terms))


def _bin_edges(baseline: np.ndarray, bins: int) -> np.ndarray:
    """Quantile-based bin edges derived from the baseline, deduped & padded.

    Quantile binning keeps roughly equal mass per bin on the baseline, which is
    the standard way to build a PSI binning. Edges are widened slightly at the
    extremes so out-of-range current values still land in the end bins.
    """
    qs = np.linspace(0.0, 1.0, bins + 1)
    edges = np.quantile(baseline, qs)
    edges = np.unique(edges)  # collapse duplicate edges (constant regions)
    if edges.size < 2:
        # Degenerate baseline (all one value): build a tiny window around it.
        v = float(baseline[0]) if baseline.size else 0.0
        edges = np.array([v - 0.5, v + 0.5])
    # Open the outer edges so anything outside still gets counted.
    edges = edges.astype(float)
    edges[0] = -np.inf
    edges[-1] = np.inf
    return edges


def psi_from_arrays(
    baseline: Sequence[float],
    current: Sequence[float],
    bins: int = 10,
) -> float:
    """Convenience: compute PSI directly from two raw numeric arrays.

    Bins are derived from ``baseline`` quantiles; both arrays are histogrammed
    on those same edges and handed to :func:`psi`.
    """
    b = np.asarray(baseline, dtype=float)
    b = b[~np.isnan(b)]
    c = np.asarray(current, dtype=float)
    c = c[~np.isnan(c)]
    if b.size == 0 or c.size == 0:
        return 0.0

    edges = _bin_edges(b, bins)
    e_counts, _ = np.histogram(b, bins=edges)
    a_counts, _ = np.histogram(c, bins=edges)
    return psi(e_counts, a_counts, bins=bins)


def ks_statistic(baseline_array: Sequence[float], current_array: Sequence[float]) -> float:
    """Two-sample Kolmogorov–Smirnov statistic D (no p-value, no scipy).

    D = max over x of ``|F_baseline(x) - F_current(x)|`` where F are the
    empirical CDFs. Implemented by merging the sorted samples and tracking the
    running CDFs.
    """
    b = np.asarray(baseline_array, dtype=float)
    b = np.sort(b[~np.isnan(b)])
    c = np.asarray(current_array, dtype=float)
    c = np.sort(c[~np.isnan(c)])

    n_b = b.size
    n_c = c.size
    if n_b == 0 or n_c == 0:
        return 0.0

    # Evaluate both empirical CDFs at every observed point. searchsorted with
    # side="right" gives the count of sample points <= x, i.e. the CDF * n.
    all_points = np.concatenate([b, c])
    cdf_b = np.searchsorted(b, all_points, side="right") / n_b
    cdf_c = np.searchsorted(c, all_points, side="right") / n_c
    return float(np.max(np.abs(cdf_b - cdf_c)))


def drift_check(data: pd.DataFrame, config: Dict[str, Any]) -> CheckResult:
    """Compare a column against a stored baseline distribution.

    config keys
    -----------
    table:     table name (for reporting).
    column:    numeric column to inspect.
    baseline:  baseline numeric array (the reference distribution).
    bins:      number of PSI bins (default ``10``).
    threshold: PSI value above which we flag drift (default ``0.2``).
    severity:  optional severity (default ``warning``).

    The CheckResult carries the PSI in ``score`` indirectly: we report a quality
    ``score`` of ``1.0`` when stable and decaying as PSI grows, and embed both
    PSI and KS in ``detail``.
    """
    table = config.get("table", "")
    column = config["column"]
    baseline = config.get("baseline", [])
    bins = int(config.get("bins", 10))
    threshold = float(config.get("threshold", 0.2))
    severity = config.get("severity", Severity.WARNING)

    if column not in data.columns:
        return CheckResult(
            check="drift_check",
            table=table,
            column=column,
            passed=False,
            score=0.0,
            detail=f"Column '{column}' not found in table '{table}'.",
            severity=severity,
        )

    current = pd.to_numeric(data[column], errors="coerce").to_numpy(dtype=float)
    baseline_arr = np.asarray(baseline, dtype=float)

    if baseline_arr.size == 0 or np.all(np.isnan(current)):
        return CheckResult(
            check="drift_check",
            table=table,
            column=column,
            passed=True,
            score=1.0,
            detail="No baseline or no current data; drift check skipped.",
            severity=severity,
        )

    psi_value = psi_from_arrays(baseline_arr, current, bins=bins)
    ks_value = ks_statistic(baseline_arr, current)

    passed = psi_value <= threshold

    # Map PSI -> quality score. PSI of 0 -> 1.0; PSI at threshold -> ~0.8;
    # higher PSI keeps decaying but is clamped to [0, 1] by CheckResult.
    score = float(max(0.0, 1.0 - psi_value))

    detail = (
        f"PSI={psi_value:.4f} (threshold={threshold:.4f}) "
        f"KS={ks_value:.4f} bins={bins} "
        f"n_baseline={baseline_arr.size} n_current={int(np.sum(~np.isnan(current)))}"
    )

    return CheckResult(
        check="drift_check",
        table=table,
        column=column,
        passed=passed,
        score=score,
        detail=detail,
        severity=severity,
    )
