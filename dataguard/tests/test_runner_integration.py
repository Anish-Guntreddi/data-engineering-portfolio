"""End-to-end runner test WITHOUT a database.

We stub ``dataguard.db`` (so psycopg2 is never imported) and feed the runner the
in-memory deterministic demo frames. This locks in the table-level golden
scores: orders_clean == 100.0, orders_drifted == 59.0471.
"""

import sys
import types

import pytest


@pytest.fixture()
def runner_with_stub_db(monkeypatch):
    # Install a no-op db stub BEFORE importing the runner so it imports cleanly
    # on a host that has no psycopg2.
    db_stub = types.ModuleType("dataguard.db")
    db_stub.ensure_results_table = lambda *a, **k: None
    db_stub.insert_dq_results = lambda *a, **k: None
    monkeypatch.setitem(sys.modules, "dataguard.db", db_stub)

    # Drop any cached import of the runner so it binds to the stub.
    sys.modules.pop("dataguard.runner", None)
    from dataguard import runner as runner_mod
    from dataguard.seed.seed import (
        generate_orders_clean,
        generate_orders_drifted,
    )

    frames = {
        "orders_clean": generate_orders_clean(),
        "orders_drifted": generate_orders_drifted(),
    }
    monkeypatch.setattr(runner_mod, "_load_table", lambda t: frames[t])
    yield runner_mod
    sys.modules.pop("dataguard.runner", None)


def test_clean_table_scores_100(runner_with_stub_db):
    from dataguard.config import load_expectations
    from dataguard.scoring import score_table
    from dataguard.seed.seed import REFERENCE_NOW

    exps = {e["table"]: e for e in load_expectations()}
    results = runner_with_stub_db.run_checks_for_table(
        "orders_clean", exps["orders_clean"], REFERENCE_NOW
    )
    assert all(r.passed for r in results)
    assert score_table(results) == 100.0


def test_drifted_table_has_failures_and_golden_score(runner_with_stub_db):
    from dataguard.config import load_expectations
    from dataguard.scoring import score_table
    from dataguard.seed.seed import REFERENCE_NOW

    exps = {e["table"]: e for e in load_expectations()}
    results = runner_with_stub_db.run_checks_for_table(
        "orders_drifted", exps["orders_drifted"], REFERENCE_NOW
    )

    by_check = {(r.check, r.column): r for r in results}
    # Drift, freshness, nulls and range must all FAIL on the drifted table.
    assert by_check[("drift_check", "amount")].passed is False
    assert by_check[("freshness_check", "created_at")].passed is False
    assert by_check[("null_check", "amount")].passed is False
    assert by_check[("range_check", "amount")].passed is False
    # quantity is still clean -> passes.
    assert by_check[("range_check", "quantity")].passed is True

    # Deterministic golden table score.
    assert score_table(results) == 59.0471


def test_runner_is_deterministic(runner_with_stub_db):
    from dataguard.config import load_expectations
    from dataguard.scoring import score_table
    from dataguard.seed.seed import REFERENCE_NOW

    exps = {e["table"]: e for e in load_expectations()}

    def run_once():
        return {
            t: score_table(
                runner_with_stub_db.run_checks_for_table(t, exps[t], REFERENCE_NOW)
            )
            for t in ("orders_clean", "orders_drifted")
        }

    assert run_once() == run_once() == {
        "orders_clean": 100.0,
        "orders_drifted": 59.0471,
    }
