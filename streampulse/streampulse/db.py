"""Postgres schema and access helpers for StreamPulse.

The SQL schema constants and DSN builder are pure (stdlib only). psycopg2 is
imported *lazily* inside the functions that actually need a connection, so this
module can be imported on the host without psycopg2 installed (the pure tests
never call the connecting helpers).

Tables
------
metrics(id, window_start, window_end, metric, value, created_at)
    Unique on (window_start, metric) so the processor can UPSERT a window's
    metrics idempotently as it re-emits.

alerts(id, ts, metric, value, threshold, message, created_at)
    Unique on (ts, metric) so the alerter does not write duplicate alerts for
    the same breaching window.
"""

from __future__ import annotations

import os
from typing import Dict, List

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS metrics (
    id            BIGSERIAL PRIMARY KEY,
    window_start  DOUBLE PRECISION NOT NULL,
    window_end    DOUBLE PRECISION NOT NULL,
    metric        TEXT NOT NULL,
    value         DOUBLE PRECISION NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (window_start, metric)
);

CREATE INDEX IF NOT EXISTS idx_metrics_window_start ON metrics (window_start);
CREATE INDEX IF NOT EXISTS idx_metrics_metric ON metrics (metric);

CREATE TABLE IF NOT EXISTS alerts (
    id          BIGSERIAL PRIMARY KEY,
    ts          DOUBLE PRECISION NOT NULL,
    metric      TEXT NOT NULL,
    value       DOUBLE PRECISION NOT NULL,
    threshold   DOUBLE PRECISION NOT NULL,
    message     TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (ts, metric)
);

CREATE INDEX IF NOT EXISTS idx_alerts_ts ON alerts (ts);
"""

UPSERT_METRIC_SQL = """
INSERT INTO metrics (window_start, window_end, metric, value)
VALUES (%(window_start)s, %(window_end)s, %(metric)s, %(value)s)
ON CONFLICT (window_start, metric)
DO UPDATE SET value = EXCLUDED.value,
              window_end = EXCLUDED.window_end,
              created_at = now();
"""

INSERT_ALERT_SQL = """
INSERT INTO alerts (ts, metric, value, threshold, message)
VALUES (%(ts)s, %(metric)s, %(value)s, %(threshold)s, %(message)s)
ON CONFLICT (ts, metric) DO NOTHING;
"""

SELECT_RECENT_METRICS_SQL = """
SELECT window_start, window_end, metric, value
FROM metrics
WHERE window_start >= %(min_window_start)s
ORDER BY window_start DESC, metric ASC;
"""

SELECT_ALL_METRICS_SQL = """
SELECT window_start, window_end, metric, value
FROM metrics
ORDER BY window_start DESC, metric ASC
LIMIT %(limit)s;
"""

SELECT_ALL_ALERTS_SQL = """
SELECT ts, metric, value, threshold, message, created_at
FROM alerts
ORDER BY ts DESC
LIMIT %(limit)s;
"""


def dsn_from_env() -> str:
    """Build a libpq DSN from environment variables (with sane defaults)."""
    host = os.getenv("PGHOST", "postgres")
    port = os.getenv("PGPORT", "5432")
    db = os.getenv("PGDATABASE", "streampulse")
    user = os.getenv("PGUSER", "postgres")
    pw = os.getenv("PGPASSWORD", "postgres")
    return f"host={host} port={port} dbname={db} user={user} password={pw}"


def connect(dsn: str | None = None):
    """Open a psycopg2 connection (autocommit off). Imports psycopg2 lazily."""
    import psycopg2  # noqa: WPS433 (lazy infra import on purpose)

    return psycopg2.connect(dsn or dsn_from_env())


def init_schema(conn) -> None:
    """Create tables/indexes if they do not exist."""
    with conn.cursor() as cur:
        cur.execute(SCHEMA_SQL)
    conn.commit()


def upsert_metrics(conn, rows: List[Dict]) -> int:
    """UPSERT a list of metric rows. Returns the number of rows processed."""
    if not rows:
        return 0
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(UPSERT_METRIC_SQL, row)
    conn.commit()
    return len(rows)


def insert_alerts(conn, alerts: List[Dict]) -> int:
    """Insert alert rows (ignoring duplicates). Returns rows attempted."""
    if not alerts:
        return 0
    with conn.cursor() as cur:
        for alert in alerts:
            cur.execute(INSERT_ALERT_SQL, alert)
    conn.commit()
    return len(alerts)


def fetch_recent_metrics(conn, min_window_start: float) -> List[Dict]:
    """Return metric rows with window_start >= ``min_window_start``."""
    with conn.cursor() as cur:
        cur.execute(SELECT_RECENT_METRICS_SQL, {"min_window_start": min_window_start})
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def fetch_metrics(conn, limit: int = 500) -> List[Dict]:
    """Return the most recent ``limit`` metric rows (for the dashboard)."""
    with conn.cursor() as cur:
        cur.execute(SELECT_ALL_METRICS_SQL, {"limit": limit})
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def fetch_alerts(conn, limit: int = 100) -> List[Dict]:
    """Return the most recent ``limit`` alert rows (for the dashboard)."""
    with conn.cursor() as cur:
        cur.execute(SELECT_ALL_ALERTS_SQL, {"limit": limit})
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
