"""Host-pure tests for the deterministic quality scorer.

A fixed list of CheckResults must always yield the same score.
"""

from dataguard.checks.base import CheckResult, Severity
from dataguard.scoring import score_all, score_table, summarize


def _fixed_results():
    # weighted: 3*1.0 + 2*1.0 + 2*0.5 + 1*0.0 = 6.0 ; weights = 8 ; 100*6/8 = 75.0
    return [
        CheckResult("schema_check", "t", "", True, 1.0, "ok", Severity.CRITICAL),
        CheckResult("null_check", "t", "amount", True, 1.0, "ok", Severity.WARNING),
        CheckResult("range_check", "t", "amount", False, 0.5, "bad", Severity.WARNING),
        CheckResult("drift_check", "t", "amount", False, 0.0, "drift", Severity.INFO),
    ]


def test_score_table_is_deterministic_golden():
    results = _fixed_results()
    assert score_table(results) == 75.0
    # Run again to prove determinism.
    assert score_table(_fixed_results()) == 75.0


def test_score_all_passes_is_100():
    results = [
        CheckResult("a", "t", "", True, 1.0, "", Severity.WARNING),
        CheckResult("b", "t", "", True, 1.0, "", Severity.INFO),
    ]
    assert score_table(results) == 100.0


def test_score_all_fail_zero():
    results = [
        CheckResult("a", "t", "", False, 0.0, "", Severity.CRITICAL),
        CheckResult("b", "t", "", False, 0.0, "", Severity.WARNING),
    ]
    assert score_table(results) == 0.0


def test_empty_results_score_100():
    assert score_table([]) == 100.0


def test_score_all_groups_by_table():
    results = [
        CheckResult("a", "t1", "", True, 1.0, "", Severity.WARNING),
        CheckResult("b", "t2", "", False, 0.0, "", Severity.WARNING),
    ]
    grouped = score_all(results)
    assert grouped == {"t1": 100.0, "t2": 0.0}


def test_severity_weighting_makes_critical_dominate():
    # A failing critical check should hurt the score more than a failing info.
    crit_fail = [
        CheckResult("a", "t", "", False, 0.0, "", Severity.CRITICAL),
        CheckResult("b", "t", "", True, 1.0, "", Severity.INFO),
    ]
    info_fail = [
        CheckResult("a", "t", "", True, 1.0, "", Severity.CRITICAL),
        CheckResult("b", "t", "", False, 0.0, "", Severity.INFO),
    ]
    # crit_fail: 100*(3*0 + 1*1)/4 = 25.0 ; info_fail: 100*(3*1 + 1*0)/4 = 75.0
    assert score_table(crit_fail) == 25.0
    assert score_table(info_fail) == 75.0
    assert score_table(crit_fail) < score_table(info_fail)


def test_summarize_counts():
    s = summarize(_fixed_results())
    assert s["total_checks"] == 4
    assert s["failed_checks"] == 2
    assert s["passed_checks"] == 2
    assert s["scores"] == {"t": 75.0}
