"""Host unit tests for the PURE generator (pandas/numpy only -- no infra).

These run on the host in the project .venv. They lock in determinism and the
golden constants that are ALSO baked into the dbt singular tests and
dbt_project.yml vars. If you change the generator, re-derive with
``python -m generator.generate`` and update BOTH places.
"""

import pandas as pd

from generator.generate import (
    EVENT_TYPES,
    ORDER_STATUSES,
    compute_dau,
    compute_n_orders,
    compute_revenue,
    derive_golden,
    generate_events,
    golden_date,
)

# --- Golden constants (derived by running generator.generate on the host) ----
GOLDEN_DATE = "2024-01-11"
GOLDEN_DAU = 57
GOLDEN_REVENUE = 1175.29
GOLDEN_N_ORDERS = 35


def test_golden_date_resolves():
    assert golden_date() == GOLDEN_DATE


def test_generate_is_deterministic_across_two_calls():
    a = generate_events()
    b = generate_events()
    for key in ("users", "events", "orders"):
        pd.testing.assert_frame_equal(a[key], b[key])


def test_generate_seed_changes_output():
    a = generate_events(seed=42)
    b = generate_events(seed=7)
    # different seed -> different event volume / distinct content
    assert not a["events"].equals(b["events"])


def test_dau_for_golden_date_matches_golden_int():
    data = generate_events()
    assert compute_dau(data["events"], GOLDEN_DATE) == GOLDEN_DAU


def test_revenue_for_golden_date_matches_golden_float():
    data = generate_events()
    assert compute_revenue(data["orders"], GOLDEN_DATE) == GOLDEN_REVENUE


def test_n_orders_for_golden_date_matches_golden_int():
    data = generate_events()
    assert compute_n_orders(data["orders"], GOLDEN_DATE) == GOLDEN_N_ORDERS


def test_derive_golden_matches_baked_constants():
    g = derive_golden()
    assert g["golden_date"] == GOLDEN_DATE
    assert g["golden_dau"] == GOLDEN_DAU
    assert g["golden_revenue"] == GOLDEN_REVENUE
    assert g["golden_n_orders"] == GOLDEN_N_ORDERS


def test_event_types_within_accepted_set():
    data = generate_events()
    observed = set(data["events"]["event_type"].unique())
    assert observed.issubset(set(EVENT_TYPES))


def test_order_statuses_within_accepted_set():
    data = generate_events()
    observed = set(data["orders"]["status"].unique())
    assert observed.issubset(set(ORDER_STATUSES))


def test_schemas_have_expected_columns():
    data = generate_events()
    assert list(data["users"].columns) == ["user_id", "signup_date", "country", "plan"]
    assert list(data["events"].columns) == [
        "event_id",
        "user_id",
        "event_type",
        "event_ts",
        "session_id",
    ]
    assert list(data["orders"].columns) == [
        "order_id",
        "user_id",
        "amount",
        "order_ts",
        "status",
    ]


def test_primary_keys_are_unique():
    data = generate_events()
    assert data["users"]["user_id"].is_unique
    assert data["events"]["event_id"].is_unique
    assert data["orders"]["order_id"].is_unique


def test_no_events_before_signup():
    data = generate_events()
    users = data["users"][["user_id", "signup_date"]]
    ev = data["events"].merge(users, on="user_id", how="left")
    # every event must occur on/after the user's signup date
    assert (ev["event_ts"].dt.normalize() >= ev["signup_date"]).all()
