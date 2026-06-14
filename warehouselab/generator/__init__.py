"""WarehouseLab data generator package.

``generate`` holds the PURE deterministic data generator (numpy/pandas only).
``load`` holds the infra-touching Postgres loader (psycopg2). Keep them apart so
the pure logic unit-tests on the host without infra imports.
"""

from .generate import (
    GOLDEN_DAY_INDEX,
    compute_dau,
    compute_n_orders,
    compute_revenue,
    derive_golden,
    generate_events,
    golden_date,
)

__all__ = [
    "GOLDEN_DAY_INDEX",
    "compute_dau",
    "compute_n_orders",
    "compute_revenue",
    "derive_golden",
    "generate_events",
    "golden_date",
]
