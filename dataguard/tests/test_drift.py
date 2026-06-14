"""Host-pure tests for drift detection (PSI primary, KS secondary).

Both directions are asserted: PSI/KS must FLAG a deliberately shifted
distribution and must PASS a stable one. PSI and KS are implemented by hand with
numpy (no scipy), so these run on the host.
"""

import numpy as np
import pandas as pd

from dataguard.checks.drift import (
    drift_check,
    ks_statistic,
    psi,
    psi_from_arrays,
)
from dataguard.seed.seed import (
    baseline_amounts,
    generate_orders_clean,
    generate_orders_drifted,
)


# --------------------------------------------------------------------------- #
# psi() on count vectors
# --------------------------------------------------------------------------- #
def test_psi_zero_for_identical_distributions():
    counts = [10, 20, 30, 40]
    assert psi(counts, counts) == 0.0


def test_psi_positive_for_shifted_counts():
    expected = [40, 30, 20, 10]
    actual = [10, 20, 30, 40]  # mass moved to the other end
    value = psi(expected, actual)
    assert value > 0.2  # clearly flagged


def test_psi_raises_on_shape_mismatch():
    try:
        psi([1, 2, 3], [1, 2])
    except ValueError:
        return
    raise AssertionError("expected ValueError on shape mismatch")


# --------------------------------------------------------------------------- #
# psi_from_arrays() on raw samples
# --------------------------------------------------------------------------- #
def test_psi_from_arrays_stable_is_small():
    rng = np.random.default_rng(0)
    base = rng.normal(100, 10, 5000)
    same = rng.normal(100, 10, 5000)
    value = psi_from_arrays(base, same, bins=10)
    assert value < 0.1  # no significant shift


def test_psi_from_arrays_shifted_is_large():
    rng = np.random.default_rng(0)
    base = rng.normal(100, 10, 5000)
    shifted = rng.normal(160, 10, 5000)  # mean pushed up
    value = psi_from_arrays(base, shifted, bins=10)
    assert value > 0.25  # significant shift


# --------------------------------------------------------------------------- #
# ks_statistic()
# --------------------------------------------------------------------------- #
def test_ks_zero_for_identical_arrays():
    a = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    assert ks_statistic(a, a) == 0.0


def test_ks_large_for_disjoint_arrays():
    a = np.arange(0, 100, dtype=float)
    b = np.arange(1000, 1100, dtype=float)
    assert abs(ks_statistic(a, b) - 1.0) < 1e-9  # completely separated


def test_ks_behaves_directionally():
    rng = np.random.default_rng(1)
    base = rng.normal(0, 1, 4000)
    same = rng.normal(0, 1, 4000)
    shifted = rng.normal(3, 1, 4000)
    ks_stable = ks_statistic(base, same)
    ks_shift = ks_statistic(base, shifted)
    assert ks_stable < 0.1
    assert ks_shift > 0.5
    assert ks_shift > ks_stable


# --------------------------------------------------------------------------- #
# drift_check() — both directions on the actual seeded demo data
# --------------------------------------------------------------------------- #
def test_drift_check_passes_on_stable_seeded_data():
    base = baseline_amounts()
    clean = generate_orders_clean()
    result = drift_check(
        clean,
        {
            "table": "orders_clean",
            "column": "amount",
            "baseline": base.tolist(),
            "bins": 10,
            "threshold": 0.2,
        },
    )
    assert result.passed is True
    # Identical distribution -> PSI 0 -> perfect score.
    assert result.score == 1.0
    assert "PSI=0.0000" in result.detail


def test_drift_check_flags_shifted_seeded_data():
    base = baseline_amounts()
    drifted = generate_orders_drifted()
    result = drift_check(
        drifted,
        {
            "table": "orders_drifted",
            "column": "amount",
            "baseline": base.tolist(),
            "bins": 10,
            "threshold": 0.2,
        },
    )
    assert result.passed is False
    assert result.score < 0.2  # heavily drifted
    assert "PSI=" in result.detail


def test_drift_golden_psi_values():
    """Golden constants derived by running the pure generator on the host."""
    base = baseline_amounts()
    clean_vals = generate_orders_clean()["amount"].to_numpy(dtype=float)
    drift_vals = (
        pd.to_numeric(generate_orders_drifted()["amount"], errors="coerce")
        .dropna()
        .to_numpy(dtype=float)
    )

    psi_stable = psi_from_arrays(base, clean_vals, bins=10)
    psi_shift = psi_from_arrays(base, drift_vals, bins=10)
    ks_stable = ks_statistic(base, clean_vals)
    ks_shift = ks_statistic(base, drift_vals)

    assert psi_stable == 0.0
    assert abs(psi_shift - 4.991095) < 1e-4
    assert ks_stable == 0.0
    assert abs(ks_shift - 0.837217) < 1e-4
