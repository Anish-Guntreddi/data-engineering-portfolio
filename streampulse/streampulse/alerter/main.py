"""Alerter: poll the metrics table, evaluate thresholds, write alert rows.

Runtime service (containerized only). Uses psycopg2 to read metrics and write
alerts. The breach logic comes from the PURE ``streampulse.alerting`` module —
the exact same code unit-tested on the host.

Environment
-----------
WINDOW_SECONDS        tumbling window size (default 60), used to scope the
                      lookback to recent windows
LOOKBACK_WINDOWS      how many recent windows to evaluate each pass (default 20)
POLL_SECONDS          how often to evaluate (default 5)
EPM_MAX               events_per_minute alert fires when value > EPM_MAX
                      (default 300)
CONV_MIN              conversion_rate alert fires when value < CONV_MIN
                      (default 0.02)
PG*                   standard libpq env vars (see db.dsn_from_env)
"""

from __future__ import annotations

import os
import signal
import sys
import time

try:
    from streampulse import db
    from streampulse.alerting import evaluate_thresholds
    from streampulse.metrics import CONVERSION_RATE, EVENTS_PER_MINUTE
except ModuleNotFoundError:  # pragma: no cover - container path fallback
    sys.path.insert(0, "/app")
    from streampulse import db
    from streampulse.alerting import evaluate_thresholds
    from streampulse.metrics import CONVERSION_RATE, EVENTS_PER_MINUTE


_RUNNING = True


def _handle_sigterm(signum, frame):  # pragma: no cover - signal handler
    global _RUNNING
    _RUNNING = False


def build_thresholds() -> dict:
    """Build the threshold config from environment variables."""
    epm_max = float(os.getenv("EPM_MAX", "300"))
    conv_min = float(os.getenv("CONV_MIN", "0.02"))
    return {
        EVENTS_PER_MINUTE: {"op": "gt", "threshold": epm_max},
        CONVERSION_RATE: {"op": "lt", "threshold": conv_min},
    }


def _connect_with_retry(retries: int = 30, delay: float = 2.0):
    last_err = None
    for _ in range(retries):
        try:
            conn = db.connect()
            db.init_schema(conn)
            return conn
        except Exception as exc:  # noqa: BLE001 - broad on purpose during boot
            last_err = exc
            print(f"[alerter] waiting for postgres: {exc}", flush=True)
            time.sleep(delay)
    raise RuntimeError(f"postgres unavailable: {last_err}")


def main() -> int:
    window_seconds = int(os.getenv("WINDOW_SECONDS", "60"))
    lookback_windows = int(os.getenv("LOOKBACK_WINDOWS", "20"))
    poll_seconds = float(os.getenv("POLL_SECONDS", "5"))
    thresholds = build_thresholds()

    signal.signal(signal.SIGTERM, _handle_sigterm)
    signal.signal(signal.SIGINT, _handle_sigterm)

    conn = _connect_with_retry()
    print(
        f"[alerter] connected. thresholds={thresholds} "
        f"lookback={lookback_windows} poll={poll_seconds}s",
        flush=True,
    )

    total_alerts = 0
    while _RUNNING:
        min_window_start = time.time() - lookback_windows * window_seconds
        try:
            rows = db.fetch_recent_metrics(conn, min_window_start)
            alerts = evaluate_thresholds(rows, thresholds)
            if alerts:
                db.insert_alerts(conn, alerts)
                total_alerts += len(alerts)
                for a in alerts:
                    print(f"[alerter] ALERT {a['message']}", flush=True)
            else:
                print(
                    f"[alerter] evaluated {len(rows)} rows, no breach "
                    f"(total_alerts={total_alerts})",
                    flush=True,
                )
        except Exception as exc:  # noqa: BLE001 - keep the loop alive
            print(f"[alerter] error: {exc}", flush=True)
            try:
                conn.rollback()
            except Exception:  # noqa: BLE001
                conn = _connect_with_retry()
        time.sleep(poll_seconds)

    conn.close()
    print(f"[alerter] shutdown, total_alerts={total_alerts}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
