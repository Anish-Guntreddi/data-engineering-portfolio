"""Host-pure tests for freshness_check (pass + fail fixtures).

``now`` is injected so the test is deterministic and never touches the clock.
"""

from datetime import datetime, timedelta, timezone

import pandas as pd

from dataguard.checks.freshness_check import freshness_check

NOW = datetime(2026, 6, 14, 12, 0, 0, tzinfo=timezone.utc)


def test_freshness_passes_when_recent():
    df = pd.DataFrame(
        {"created_at": [NOW - timedelta(hours=2), NOW - timedelta(hours=5)]}
    )
    result = freshness_check(
        df, {"table": "orders", "column": "created_at", "now": NOW, "max_age_hours": 24}
    )
    assert result.passed is True
    assert result.score == 1.0


def test_freshness_fails_when_stale():
    df = pd.DataFrame(
        {"created_at": [NOW - timedelta(hours=30), NOW - timedelta(hours=40)]}
    )
    result = freshness_check(
        df, {"table": "orders", "column": "created_at", "now": NOW, "max_age_hours": 24}
    )
    assert result.passed is False
    # newest is 30h old; decay = 1 - (30-24)/24 = 0.75
    assert abs(result.score - 0.75) < 1e-9


def test_freshness_score_decays_linearly():
    df = pd.DataFrame({"created_at": [NOW - timedelta(hours=36)]})
    result = freshness_check(
        df, {"table": "orders", "column": "created_at", "now": NOW, "max_age_hours": 24}
    )
    # 36h = 1.5x SLA -> score exactly 0.5
    assert abs(result.score - 0.5) < 1e-9


def test_freshness_is_deterministic_pure():
    """Same inputs -> identical result every time (no hidden clock)."""
    df = pd.DataFrame({"created_at": [NOW - timedelta(hours=1)]})
    cfg = {"table": "orders", "column": "created_at", "now": NOW, "max_age_hours": 24}
    a = freshness_check(df, cfg)
    b = freshness_check(df, cfg)
    assert a.passed == b.passed and a.score == b.score and a.detail == b.detail


def test_freshness_missing_column_fails():
    df = pd.DataFrame({"other": [1]})
    result = freshness_check(
        df, {"table": "orders", "column": "created_at", "now": NOW, "max_age_hours": 24}
    )
    assert result.passed is False
    assert result.score == 0.0
