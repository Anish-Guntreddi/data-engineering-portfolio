"""Deterministic synthetic data generator for WarehouseLab.

PURE LOGIC: this module imports ONLY numpy and pandas (no infra libraries),
so it unit-tests on the host without Docker.

The generator is fully seeded. As a result the Daily Active Users (DAU) and
revenue for any given calendar day are knowable by construction. The orchestrator
/ tests bake the golden integers for a single "golden date" derived by actually
running this generator on the host (see ``derive_golden`` below).

Domain model
------------
users : one row per user
    user_id, signup_date, country, plan
events : behavioural event stream
    event_id, user_id, event_type, event_ts, session_id
orders : commerce transactions
    order_id, user_id, amount, order_ts, status

DAU for a calendar day = count of DISTINCT user_id that have at least one event
whose ``event_ts`` falls on that day.

Revenue for a calendar day = sum of ``amount`` over orders with status
'completed' whose ``order_ts`` falls on that day.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# --- domain constants --------------------------------------------------------

EVENT_TYPES = ["page_view", "click", "signup", "purchase"]
# probability weights for sampling an event_type (sum to 1.0)
EVENT_TYPE_WEIGHTS = [0.55, 0.30, 0.05, 0.10]

ORDER_STATUSES = ["placed", "completed", "refunded"]
ORDER_STATUS_WEIGHTS = [0.20, 0.70, 0.10]

COUNTRIES = ["US", "CA", "GB", "DE", "FR", "IN", "BR", "AU"]
PLANS = ["free", "pro", "enterprise"]
PLAN_WEIGHTS = [0.70, 0.25, 0.05]

# The golden date is a fixed offset into the simulated window. It is chosen as
# day index 10 (the 11th day) so it is well inside the active window and not an
# edge case. With start_date='2024-01-01' this resolves to '2024-01-11'.
GOLDEN_DAY_INDEX = 10


def _date_str(d: datetime) -> str:
    return d.strftime("%Y-%m-%d")


def generate_events(
    seed: int = 42,
    n_users: int = 500,
    days: int = 30,
    start_date: str = "2024-01-01",
) -> dict[str, pd.DataFrame]:
    """Generate deterministic synthetic data.

    Returns a dict of DataFrames keyed by 'users', 'events', 'orders'.

    The function is a PURE function of its arguments: calling it twice with the
    same arguments yields identical DataFrames (verified in the unit tests).
    """
    rng = np.random.default_rng(seed)
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")

    # ------------------------------------------------------------------ users
    user_ids = np.arange(1, n_users + 1, dtype=np.int64)
    # signup day index in [0, days-1]; deterministic via rng
    signup_day_idx = rng.integers(low=0, high=days, size=n_users)
    signup_dates = [_date_str(start_dt + timedelta(days=int(i))) for i in signup_day_idx]
    countries = rng.choice(COUNTRIES, size=n_users)
    plans = rng.choice(PLANS, size=n_users, p=PLAN_WEIGHTS)

    users = pd.DataFrame(
        {
            "user_id": user_ids,
            "signup_date": pd.to_datetime(signup_dates),
            "country": countries,
            "plan": plans,
        }
    )

    # ----------------------------------------------------------------- events
    # Each (user, day) pair is "active" with a fixed Bernoulli probability,
    # but ONLY on/after the user's signup day. This makes DAU exactly the count
    # of users that drew an active flag for that day. We materialise the
    # activity matrix deterministically.
    activity_prob = 0.30
    # draw a full (n_users x days) matrix of activity decisions in one call so
    # the RNG stream is stable regardless of how we iterate.
    activity = rng.random((n_users, days)) < activity_prob

    event_rows: list[dict] = []
    event_id = 1
    # number of events emitted per active (user, day); 1..4 deterministically
    for u_idx in range(n_users):
        u_id = int(user_ids[u_idx])
        u_signup = int(signup_day_idx[u_idx])
        for d in range(days):
            if d < u_signup:
                continue
            if not activity[u_idx, d]:
                continue
            day_dt = start_dt + timedelta(days=d)
            n_events = int(rng.integers(low=1, high=5))  # 1..4 events that day
            session_id = f"sess-{u_id}-{d}"
            for e in range(n_events):
                et = rng.choice(EVENT_TYPES, p=EVENT_TYPE_WEIGHTS)
                # spread events across the day deterministically
                second_offset = int(rng.integers(low=0, high=86400))
                event_ts = day_dt + timedelta(seconds=second_offset)
                event_rows.append(
                    {
                        "event_id": event_id,
                        "user_id": u_id,
                        "event_type": str(et),
                        "event_ts": event_ts,
                        "session_id": session_id,
                    }
                )
                event_id += 1

    events = pd.DataFrame(event_rows)
    events["event_ts"] = pd.to_datetime(events["event_ts"])

    # ----------------------------------------------------------------- orders
    # Orders are generated independently from a per-day Poisson-ish count.
    # Amounts are drawn from a fixed lognormal and rounded to cents, so the
    # revenue for a given day is fully determined by the seed.
    order_rows: list[dict] = []
    order_id = 1
    for d in range(days):
        day_dt = start_dt + timedelta(days=d)
        n_orders = int(rng.integers(low=20, high=60))  # 20..59 orders/day
        for _ in range(n_orders):
            buyer = int(rng.choice(user_ids))
            amount = float(np.round(rng.lognormal(mean=3.2, sigma=0.6), 2))
            status = str(rng.choice(ORDER_STATUSES, p=ORDER_STATUS_WEIGHTS))
            second_offset = int(rng.integers(low=0, high=86400))
            order_ts = day_dt + timedelta(seconds=second_offset)
            order_rows.append(
                {
                    "order_id": order_id,
                    "user_id": buyer,
                    "amount": amount,
                    "order_ts": order_ts,
                    "status": status,
                }
            )
            order_id += 1

    orders = pd.DataFrame(order_rows)
    orders["order_ts"] = pd.to_datetime(orders["order_ts"])

    return {"users": users, "events": events, "orders": orders}


def golden_date(start_date: str = "2024-01-01") -> str:
    """Return the golden calendar date string for the default window."""
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    return _date_str(start_dt + timedelta(days=GOLDEN_DAY_INDEX))


def compute_dau(events: pd.DataFrame, date_str: str) -> int:
    """Distinct active users for the given calendar date (pure helper)."""
    day = events["event_ts"].dt.strftime("%Y-%m-%d") == date_str
    return int(events.loc[day, "user_id"].nunique())


def compute_revenue(orders: pd.DataFrame, date_str: str) -> float:
    """Completed-order revenue for the given calendar date (pure helper)."""
    same_day = orders["order_ts"].dt.strftime("%Y-%m-%d") == date_str
    completed = orders["status"] == "completed"
    rev = orders.loc[same_day & completed, "amount"].sum()
    return float(np.round(rev, 2))


def compute_n_orders(orders: pd.DataFrame, date_str: str) -> int:
    """Count of completed orders for the given calendar date (pure helper)."""
    same_day = orders["order_ts"].dt.strftime("%Y-%m-%d") == date_str
    completed = orders["status"] == "completed"
    return int((same_day & completed).sum())


def derive_golden(
    seed: int = 42,
    n_users: int = 500,
    days: int = 30,
    start_date: str = "2024-01-01",
) -> dict:
    """Run the generator and return the golden constants for the golden date.

    This is the canonical way the golden values are derived. The CLI prints the
    result so the integers can be baked into tests and dbt singular tests.
    """
    data = generate_events(seed=seed, n_users=n_users, days=days, start_date=start_date)
    gdate = golden_date(start_date)
    return {
        "golden_date": gdate,
        "golden_dau": compute_dau(data["events"], gdate),
        "golden_revenue": compute_revenue(data["orders"], gdate),
        "golden_n_orders": compute_n_orders(data["orders"], gdate),
        "n_events": int(len(data["events"])),
        "n_orders_total": int(len(data["orders"])),
        "n_users": int(len(data["users"])),
    }


if __name__ == "__main__":  # pragma: no cover - manual derivation entrypoint
    import json

    print(json.dumps(derive_golden(), indent=2))
