"""Deterministic demo data + Postgres seeding.

The two generators are PURE (numpy/pandas only) so they can be unit-tested on
the host and so golden constants are known by construction. Seeding into
Postgres is a thin wrapper that imports ``dataguard.db`` only at call time, so
importing this module never pulls in psycopg2.

Tables produced
---------------
* ``orders_clean``   — well-behaved orders; every check should pass.
* ``orders_drifted`` — same schema but with injected problems:
    - NULLs in ``amount``
    - out-of-range ``amount`` (negatives and huge values)
    - a shifted ``amount`` distribution (mean pushed up) -> PSI drift
    - stale ``created_at`` timestamps (far in the past) -> freshness failure

``REFERENCE_NOW`` is the fixed "now" used so freshness behaviour is
deterministic and the golden values are stable.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Tuple

import numpy as np
import pandas as pd

SEED = 1337
N_ROWS = 1000

# A fixed reference time. orders_clean is timestamped just before this; the
# drifted table is mostly stale relative to it.
REFERENCE_NOW = datetime(2026, 6, 14, 12, 0, 0, tzinfo=timezone.utc)

_STATUSES = ["pending", "paid", "shipped", "delivered", "cancelled"]


def _rng() -> np.random.Generator:
    return np.random.default_rng(SEED)


def generate_orders_clean() -> pd.DataFrame:
    """A clean orders table. Every configured check should pass against it."""
    rng = _rng()
    n = N_ROWS

    ids = np.arange(1, n + 1, dtype=np.int64)
    # Amounts: log-normal-ish, all positive and within [0, 10000].
    amount = rng.normal(loc=120.0, scale=30.0, size=n)
    amount = np.clip(amount, 1.0, 10000.0)
    amount = np.round(amount, 2)

    quantity = rng.integers(1, 11, size=n)  # 1..10 inclusive
    status = rng.choice(_STATUSES, size=n)

    # Timestamps within the last 12 hours before REFERENCE_NOW -> always fresh.
    age_minutes = rng.integers(0, 12 * 60, size=n)
    created_at = [REFERENCE_NOW - timedelta(minutes=int(m)) for m in age_minutes]

    return pd.DataFrame(
        {
            "id": ids,
            "amount": amount,
            "quantity": quantity.astype(np.int64),
            "status": status.astype(object),
            "created_at": pd.to_datetime(created_at, utc=True),
        }
    )


def generate_orders_drifted() -> pd.DataFrame:
    """An orders table with deliberately injected data-quality problems."""
    rng = _rng()  # same seed -> deterministic problem placement
    n = N_ROWS

    ids = np.arange(1, n + 1, dtype=np.int64)

    # Shifted amount distribution: mean pushed from 120 to 260 -> PSI drift.
    amount = rng.normal(loc=260.0, scale=60.0, size=n)
    amount = np.round(amount, 2)

    # Inject out-of-range values: ~5% negative, ~3% absurdly large.
    neg_idx = rng.choice(n, size=int(0.05 * n), replace=False)
    amount[neg_idx] = -np.abs(amount[neg_idx])
    big_idx = rng.choice(n, size=int(0.03 * n), replace=False)
    amount[big_idx] = 50000.0 + np.abs(amount[big_idx])

    amount_obj = amount.astype(object)
    # Inject ~8% NULLs into amount.
    null_idx = rng.choice(n, size=int(0.08 * n), replace=False)
    for i in null_idx:
        amount_obj[i] = None

    quantity = rng.integers(1, 11, size=n)
    status = rng.choice(_STATUSES, size=n)

    # Stale timestamps: 10..40 days before REFERENCE_NOW -> freshness failure.
    age_days = rng.integers(10, 41, size=n)
    created_at = [REFERENCE_NOW - timedelta(days=int(d)) for d in age_days]

    return pd.DataFrame(
        {
            "id": ids,
            "amount": amount_obj,
            "quantity": quantity.astype(np.int64),
            "status": status.astype(object),
            "created_at": pd.to_datetime(created_at, utc=True),
        }
    )


def baseline_amounts() -> np.ndarray:
    """The baseline ``amount`` distribution (from the clean table).

    Used as the drift reference. Returns the clean amounts as a float array.
    """
    return generate_orders_clean()["amount"].to_numpy(dtype=float)


# --------------------------------------------------------------------------- #
# Postgres seeding (imports db lazily so this module stays infra-free to import)
# --------------------------------------------------------------------------- #

# Column layout shared by both demo tables. Defined once so DDL/DML are
# generated from a single source of truth and identifiers are never built from
# free-form strings.
_COLUMNS = ("id", "amount", "quantity", "status", "created_at")


def _df_to_rows(df: pd.DataFrame):
    rows = []
    for rec in df.itertuples(index=False):
        amount = rec.amount
        if amount is None or (isinstance(amount, float) and np.isnan(amount)):
            amount = None
        else:
            amount = float(amount)
        ts = rec.created_at
        # pandas Timestamp -> python datetime for psycopg2.
        ts = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
        rows.append((int(rec.id), amount, int(rec.quantity), str(rec.status), ts))
    return rows


def _seed_table(table: str, df: pd.DataFrame) -> None:
    from dataguard import db  # local import keeps this module infra-free to import

    # All identifier handling and allowlisting lives in the db layer, which
    # composes statements with psycopg2.sql.Identifier and binds every row
    # value as a placeholder — no string-formatted SQL anywhere.
    db.ensure_demo_table(table)
    db.insert_rows(table, list(_COLUMNS), _df_to_rows(df))


def seed_database() -> Tuple[int, int]:
    """Create + populate ``orders_clean`` and ``orders_drifted`` in Postgres.

    Returns the row counts ``(clean, drifted)`` actually written.
    """
    from dataguard import db

    db.ensure_results_table()

    clean = generate_orders_clean()
    drifted = generate_orders_drifted()
    _seed_table("orders_clean", clean)
    _seed_table("orders_drifted", drifted)
    return len(clean), len(drifted)


if __name__ == "__main__":
    c, d = seed_database()
    print(f"Seeded orders_clean={c} rows, orders_drifted={d} rows.")
