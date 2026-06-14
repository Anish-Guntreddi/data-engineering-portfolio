#!/usr/bin/env python3
"""End-to-end verification for StreamPulse.

Connects to postgres and asserts the two integration gates:

  1. The ``metrics`` table is populated for *recent* windows (the processor is
     consuming events from Redpanda and writing aggregates within the window).
  2. At least one ``alerts`` row exists (a threshold breach fired — the producer
     bursts events to drive events_per_minute over the limit).

Exits 0 when both gates pass, non-zero otherwise. Used by ``make e2e``.

Environment
-----------
WINDOW_SECONDS    tumbling window size (default 60)
LOOKBACK_WINDOWS  how many recent windows count as "recent" (default 30)
WAIT_SECONDS      total time to wait for gates to satisfy (default 180)
POLL_SECONDS      poll interval (default 5)
PG*               standard libpq env vars
"""

from __future__ import annotations

import os
import sys
import time

# Allow running from the repo root (scripts/) or inside a container (/app).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, "/app")

from streampulse import db  # noqa: E402


def _count_recent_metrics(conn, min_window_start: float) -> int:
    rows = db.fetch_recent_metrics(conn, min_window_start)
    return len(rows)


def _count_alerts(conn) -> int:
    return len(db.fetch_alerts(conn, limit=1000))


def main() -> int:
    window_seconds = int(os.getenv("WINDOW_SECONDS", "60"))
    lookback_windows = int(os.getenv("LOOKBACK_WINDOWS", "30"))
    wait_seconds = float(os.getenv("WAIT_SECONDS", "180"))
    poll_seconds = float(os.getenv("POLL_SECONDS", "5"))

    deadline = time.time() + wait_seconds
    conn = None
    metrics_ok = False
    alerts_ok = False
    last_metrics = 0
    last_alerts = 0

    while time.time() < deadline:
        try:
            if conn is None:
                conn = db.connect()
                db.init_schema(conn)
            conn.rollback()
            min_window_start = time.time() - lookback_windows * window_seconds
            last_metrics = _count_recent_metrics(conn, min_window_start)
            last_alerts = _count_alerts(conn)
            metrics_ok = last_metrics > 0
            alerts_ok = last_alerts > 0
            print(
                f"[e2e] recent_metrics={last_metrics} alerts={last_alerts} "
                f"(metrics_ok={metrics_ok} alerts_ok={alerts_ok})",
                flush=True,
            )
            if metrics_ok and alerts_ok:
                break
        except Exception as exc:  # noqa: BLE001
            print(f"[e2e] waiting: {exc}", flush=True)
            conn = None
        time.sleep(poll_seconds)

    print("=" * 60, flush=True)
    print("StreamPulse E2E verification", flush=True)
    print(f"  Gate 1 — recent metrics populated : {'PASS' if metrics_ok else 'FAIL'} "
          f"(recent rows={last_metrics})", flush=True)
    print(f"  Gate 2 — alert fired on breach     : {'PASS' if alerts_ok else 'FAIL'} "
          f"(alert rows={last_alerts})", flush=True)
    print("=" * 60, flush=True)

    if metrics_ok and alerts_ok:
        print("E2E PASSED", flush=True)
        return 0
    print("E2E FAILED", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
