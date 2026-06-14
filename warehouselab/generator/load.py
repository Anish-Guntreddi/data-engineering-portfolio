"""Load deterministic synthetic data into Postgres schema ``raw``.

This is the INFRA boundary: it imports psycopg2 and is therefore only run inside
the containerized pipeline (never required for the host unit tests). The pure
data generation lives in ``generator.generate`` and is imported here.

Connection details are read from the standard libpq environment variables:
    PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE

Usage (inside the pipeline container):
    python -m generator.load
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras

from .generate import derive_golden, generate_events

SCHEMA_SQL = Path(__file__).resolve().parent / "schema.sql"


def _conn_params() -> dict:
    return {
        "host": os.environ.get("PGHOST", "postgres"),
        "port": int(os.environ.get("PGPORT", "5432")),
        "user": os.environ.get("PGUSER", "postgres"),
        "password": os.environ.get("PGPASSWORD", "postgres"),
        "dbname": os.environ.get("PGDATABASE", "warehouse"),
    }


def _apply_schema(cur) -> None:
    cur.execute(SCHEMA_SQL.read_text())


def _truncate(cur) -> None:
    # Restart-identity not needed (ids are explicit) but TRUNCATE guarantees an
    # empty -> populated transition on every run for full determinism.
    cur.execute("TRUNCATE TABLE raw.events, raw.orders, raw.users RESTART IDENTITY;")


def _insert_users(cur, df) -> None:
    rows = [
        (
            int(r.user_id),
            r.signup_date.date() if hasattr(r.signup_date, "date") else r.signup_date,
            str(r.country),
            str(r.plan),
        )
        for r in df.itertuples(index=False)
    ]
    psycopg2.extras.execute_values(
        cur,
        "INSERT INTO raw.users (user_id, signup_date, country, plan) VALUES %s",
        rows,
        page_size=1000,
    )


def _insert_events(cur, df) -> None:
    rows = [
        (
            int(r.event_id),
            int(r.user_id),
            str(r.event_type),
            r.event_ts.to_pydatetime() if hasattr(r.event_ts, "to_pydatetime") else r.event_ts,
            str(r.session_id),
        )
        for r in df.itertuples(index=False)
    ]
    psycopg2.extras.execute_values(
        cur,
        "INSERT INTO raw.events (event_id, user_id, event_type, event_ts, session_id) VALUES %s",
        rows,
        page_size=1000,
    )


def _insert_orders(cur, df) -> None:
    rows = [
        (
            int(r.order_id),
            int(r.user_id),
            float(r.amount),
            r.order_ts.to_pydatetime() if hasattr(r.order_ts, "to_pydatetime") else r.order_ts,
            str(r.status),
        )
        for r in df.itertuples(index=False)
    ]
    psycopg2.extras.execute_values(
        cur,
        "INSERT INTO raw.orders (order_id, user_id, amount, order_ts, status) VALUES %s",
        rows,
        page_size=1000,
    )


def load(
    seed: int = 42,
    n_users: int = 500,
    days: int = 30,
    start_date: str = "2024-01-01",
) -> dict:
    """Generate the deterministic dataset and load it into ``raw.*``.

    Returns the derived golden constants (handy for logging / verification).
    """
    data = generate_events(seed=seed, n_users=n_users, days=days, start_date=start_date)

    params = _conn_params()
    print(
        f"[load] connecting to postgres host={params['host']} port={params['port']} "
        f"db={params['dbname']} user={params['user']}",
        flush=True,
    )

    conn = psycopg2.connect(**params)
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            _apply_schema(cur)
            _truncate(cur)
            _insert_users(cur, data["users"])
            _insert_events(cur, data["events"])
            _insert_orders(cur, data["orders"])
        conn.commit()
    finally:
        conn.close()

    golden = derive_golden(seed=seed, n_users=n_users, days=days, start_date=start_date)
    print(
        f"[load] loaded users={len(data['users'])} events={len(data['events'])} "
        f"orders={len(data['orders'])}",
        flush=True,
    )
    print(
        f"[load] golden date={golden['golden_date']} dau={golden['golden_dau']} "
        f"revenue={golden['golden_revenue']} n_orders={golden['golden_n_orders']}",
        flush=True,
    )
    return golden


if __name__ == "__main__":  # pragma: no cover - container entrypoint
    try:
        load()
    except Exception as exc:  # noqa: BLE001
        print(f"[load] ERROR: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)
