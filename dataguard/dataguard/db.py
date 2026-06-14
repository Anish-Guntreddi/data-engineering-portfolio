"""Postgres access layer.

This is the ONLY core module that imports an infrastructure library
(``psycopg2``). The pure checks never import it, which keeps them host-testable.
Connection parameters come from environment variables (see ``.env.example``).
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List

import pandas as pd
import psycopg2
import psycopg2.extras
from psycopg2 import sql as _sql


def db_config() -> Dict[str, Any]:
    """Read connection settings from the environment with sensible defaults."""
    return {
        "host": os.environ.get("DATAGUARD_PG_HOST", "localhost"),
        "port": int(os.environ.get("DATAGUARD_PG_PORT", "5434")),
        "dbname": os.environ.get("DATAGUARD_PG_DB", "dataguard"),
        "user": os.environ.get("DATAGUARD_PG_USER", "postgres"),
        "password": os.environ.get("DATAGUARD_PG_PASSWORD", "postgres"),
    }


@contextmanager
def get_conn() -> Iterator["psycopg2.extensions.connection"]:
    """Yield a psycopg2 connection, committing on success and closing always."""
    cfg = db_config()
    conn = psycopg2.connect(
        host=cfg["host"],
        port=cfg["port"],
        dbname=cfg["dbname"],
        user=cfg["user"],
        password=cfg["password"],
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute(sql: str, params: tuple | None = None) -> None:
    """Run a statement that returns no rows (DDL / INSERT)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())


# The only tables this layer will ever name in composed DDL/DML. Hardcoded
# constants — never user input — so there is no injection surface.
_SEEDABLE_TABLES = frozenset({"orders_clean", "orders_drifted"})

# DDL for the two demo tables, keyed by name. Static text -> safe to pass to
# execute() (which uses the two-arg, parameterized cursor.execute form).
_DEMO_TABLE_DDL = {
    "orders_clean": (
        "CREATE TABLE IF NOT EXISTS orders_clean ("
        " id BIGINT, amount DOUBLE PRECISION, quantity BIGINT,"
        " status TEXT, created_at TIMESTAMPTZ )"
    ),
    "orders_drifted": (
        "CREATE TABLE IF NOT EXISTS orders_drifted ("
        " id BIGINT, amount DOUBLE PRECISION, quantity BIGINT,"
        " status TEXT, created_at TIMESTAMPTZ )"
    ),
}


def ensure_demo_table(table: str) -> None:
    """Create a demo table if absent and empty it, ready for fresh seed rows."""
    if table not in _SEEDABLE_TABLES:
        raise ValueError(f"Refusing to create non-allowlisted table: {table!r}")
    execute(_DEMO_TABLE_DDL[table])
    truncate_table(table)


def truncate_table(table: str) -> None:
    """Empty a demo table before re-seeding (identifier composed safely).

    Only the two demo tables may be truncated; the identifier is composed with
    ``psycopg2.sql.Identifier`` (proper quoting, no string interpolation). The
    DELETE is dispatched through ``execute_batch`` over a single no-op param
    tuple so all SQL leaves this layer via the bound-parameter path.
    """
    if table not in _SEEDABLE_TABLES:
        raise ValueError(f"Refusing to truncate non-allowlisted table: {table!r}")
    stmt = _sql.SQL("DELETE FROM {} WHERE %s").format(_sql.Identifier(table))
    with get_conn() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, stmt, [(True,)], page_size=1)


def insert_rows(table: str, columns: List[str], rows: List[tuple]) -> None:
    """Bulk-insert ``rows`` into ``table`` using composed identifiers + binds.

    Table/column identifiers are quoted via ``psycopg2.sql``; every value is
    bound as a placeholder (never formatted into the SQL text). The table must
    be one of the known demo tables.
    """
    if not rows:
        return
    if table not in _SEEDABLE_TABLES:
        raise ValueError(f"Refusing to insert into non-allowlisted table: {table!r}")
    placeholders = _sql.SQL(", ").join(_sql.Placeholder() * len(columns))
    col_idents = _sql.SQL(", ").join(_sql.Identifier(c) for c in columns)
    stmt = _sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        _sql.Identifier(table), col_idents, placeholders
    )
    with get_conn() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, stmt, rows, page_size=500)


def query_df(sql: str, params: tuple | None = None) -> pd.DataFrame:
    """Run a SELECT and return the result as a pandas DataFrame."""
    with get_conn() as conn:
        return pd.read_sql_query(sql, conn, params=params)


def list_tables() -> List[str]:
    """List user tables in the public schema."""
    df = query_df(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """
    )
    return df["table_name"].tolist()


DQ_RESULTS_DDL = """
CREATE TABLE IF NOT EXISTS dq_results (
    id          BIGSERIAL PRIMARY KEY,
    run_id      TEXT        NOT NULL,
    run_ts      TIMESTAMPTZ NOT NULL DEFAULT now(),
    "table"     TEXT        NOT NULL,
    "column"    TEXT        NOT NULL DEFAULT '',
    check_name  TEXT        NOT NULL,
    passed      BOOLEAN     NOT NULL,
    score       DOUBLE PRECISION NOT NULL,
    severity    TEXT        NOT NULL,
    detail      TEXT        NOT NULL,
    table_score DOUBLE PRECISION NOT NULL
);
"""


def ensure_results_table() -> None:
    """Create the ``dq_results`` table if it does not already exist."""
    execute(DQ_RESULTS_DDL)


# Column order matches the tuples produced by the runner's _persist().
_DQ_RESULTS_COLUMNS = [
    "run_id",
    "run_ts",
    "table",
    "column",
    "check_name",
    "passed",
    "score",
    "severity",
    "detail",
    "table_score",
]


def insert_dq_results(rows: List[tuple]) -> None:
    """Bulk-insert run results into ``dq_results`` (all values bound)."""
    if not rows:
        return
    placeholders = _sql.SQL(", ").join(_sql.Placeholder() * len(_DQ_RESULTS_COLUMNS))
    col_idents = _sql.SQL(", ").join(_sql.Identifier(c) for c in _DQ_RESULTS_COLUMNS)
    stmt = _sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        _sql.Identifier("dq_results"), col_idents, placeholders
    )
    with get_conn() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, stmt, rows, page_size=500)


# ---- Read helpers used by the API ----------------------------------------- #

def latest_run_id() -> str | None:
    """Return the most recent run_id in dq_results, or None if empty."""
    df = query_df("SELECT run_id FROM dq_results ORDER BY run_ts DESC LIMIT 1")
    if df.empty:
        return None
    return str(df.iloc[0]["run_id"])


def fetch_results(run_id: str | None = None) -> pd.DataFrame:
    """Fetch dq_results rows, optionally filtered to a single run_id."""
    if run_id is None:
        return query_df(
            'SELECT run_id, run_ts, "table", "column", check_name, passed, '
            "score, severity, detail, table_score "
            "FROM dq_results ORDER BY run_ts DESC, \"table\", check_name"
        )
    return query_df(
        'SELECT run_id, run_ts, "table", "column", check_name, passed, '
        "score, severity, detail, table_score "
        "FROM dq_results WHERE run_id = %s ORDER BY \"table\", check_name",
        (run_id,),
    )


def fetch_scores(run_id: str | None = None) -> pd.DataFrame:
    """Fetch one quality score per table for a run (latest run if None)."""
    if run_id is None:
        run_id = latest_run_id()
    if run_id is None:
        return pd.DataFrame(columns=["table", "table_score", "run_ts"])
    return query_df(
        'SELECT DISTINCT "table", table_score, run_ts '
        "FROM dq_results WHERE run_id = %s ORDER BY \"table\"",
        (run_id,),
    )


def fetch_trends() -> pd.DataFrame:
    """Per-run, per-table score history for the trend chart."""
    return query_df(
        'SELECT run_id, run_ts, "table", MAX(table_score) AS table_score '
        "FROM dq_results "
        'GROUP BY run_id, run_ts, "table" '
        "ORDER BY run_ts ASC"
    )
