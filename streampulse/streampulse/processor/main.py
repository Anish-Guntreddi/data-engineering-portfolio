"""Processor: consume 'events', maintain tumbling windows, write metrics rows.

Runtime service (containerized only). Uses confluent-kafka to consume and
psycopg2 to write. The window/metric math comes from the PURE
``streampulse.windowing`` and ``streampulse.metrics`` modules — the exact same
code unit-tested on the host.

Strategy
--------
The processor keeps an in-memory map of window_start -> aggregated Window. On a
periodic flush interval it:

  1. recomputes metrics for every buffered window via the pure helpers,
  2. UPSERTs those metric rows into postgres (idempotent on (window_start,
     metric)), so a window is continually refined as more events arrive and is
     finalized once the window closes,
  3. evicts windows older than a retention horizon to bound memory.

Environment
-----------
KAFKA_BOOTSTRAP   broker bootstrap (default redpanda:9092)
EVENTS_TOPIC      topic (default "events")
CONSUMER_GROUP    group id (default "streampulse-processor")
WINDOW_SECONDS    tumbling window size (default 60)
FLUSH_SECONDS     how often to upsert metrics (default 5)
RETENTION_WINDOWS how many recent windows to keep in memory (default 30)
PG*               standard libpq env vars (see db.dsn_from_env)
"""

from __future__ import annotations

import json
import os
import signal
import sys
import time
from typing import Dict

from confluent_kafka import Consumer, KafkaException

try:
    from streampulse import db
    from streampulse.metrics import compute_metrics
    from streampulse.windowing import _empty_counts, window_bounds
except ModuleNotFoundError:  # pragma: no cover - container path fallback
    sys.path.insert(0, "/app")
    from streampulse import db
    from streampulse.metrics import compute_metrics
    from streampulse.windowing import _empty_counts, window_bounds


_RUNNING = True


def _handle_sigterm(signum, frame):  # pragma: no cover - signal handler
    global _RUNNING
    _RUNNING = False


def _ingest(windows: Dict[float, Dict], event: Dict, window_seconds: int) -> None:
    """Fold a single event into the in-memory tumbling-window state."""
    ts = float(event["event_ts"])
    etype = event["event_type"]
    start, end = window_bounds(ts, window_seconds)
    win = windows.get(start)
    if win is None:
        win = {
            "window_start": start,
            "window_end": end,
            "total": 0,
            "counts": _empty_counts(),
        }
        windows[start] = win
    win["total"] += 1
    win["counts"][etype] = win["counts"].get(etype, 0) + 1


def _evict(windows: Dict[float, Dict], retention_windows: int, window_seconds: int) -> None:
    """Drop windows older than the retention horizon to bound memory."""
    if not windows:
        return
    newest = max(windows.keys())
    horizon = newest - retention_windows * window_seconds
    stale = [k for k in windows if k < horizon]
    for k in stale:
        del windows[k]


def _connect_with_retry(retries: int = 30, delay: float = 2.0):
    """Connect to postgres, retrying while the container starts up."""
    last_err = None
    for _ in range(retries):
        try:
            conn = db.connect()
            db.init_schema(conn)
            return conn
        except Exception as exc:  # noqa: BLE001 - broad on purpose during boot
            last_err = exc
            print(f"[processor] waiting for postgres: {exc}", flush=True)
            time.sleep(delay)
    raise RuntimeError(f"postgres unavailable: {last_err}")


def main() -> int:
    bootstrap = os.getenv("KAFKA_BOOTSTRAP", "redpanda:9092")
    topic = os.getenv("EVENTS_TOPIC", "events")
    group = os.getenv("CONSUMER_GROUP", "streampulse-processor")
    window_seconds = int(os.getenv("WINDOW_SECONDS", "60"))
    flush_seconds = float(os.getenv("FLUSH_SECONDS", "5"))
    retention_windows = int(os.getenv("RETENTION_WINDOWS", "30"))

    signal.signal(signal.SIGTERM, _handle_sigterm)
    signal.signal(signal.SIGINT, _handle_sigterm)

    conn = _connect_with_retry()
    print("[processor] connected to postgres, schema ready", flush=True)

    consumer = Consumer(
        {
            "bootstrap.servers": bootstrap,
            "group.id": group,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
        }
    )
    consumer.subscribe([topic])
    print(
        f"[processor] consuming topic={topic} group={group} "
        f"window={window_seconds}s flush={flush_seconds}s",
        flush=True,
    )

    windows: Dict[float, Dict] = {}
    last_flush = time.time()
    consumed = 0

    try:
        while _RUNNING:
            msg = consumer.poll(1.0)
            if msg is not None:
                if msg.error():
                    raise KafkaException(msg.error())
                try:
                    event = json.loads(msg.value().decode("utf-8"))
                except (ValueError, UnicodeDecodeError) as exc:
                    print(f"[processor] bad message skipped: {exc}", flush=True)
                    event = None
                if event is not None:
                    _ingest(windows, event, window_seconds)
                    consumed += 1

            now = time.time()
            if now - last_flush >= flush_seconds and windows:
                rows = compute_metrics(list(windows.values()), window_seconds)
                db.upsert_metrics(conn, rows)
                _evict(windows, retention_windows, window_seconds)
                print(
                    f"[processor] consumed={consumed} windows={len(windows)} "
                    f"metric_rows={len(rows)}",
                    flush=True,
                )
                last_flush = now
    finally:
        if windows:
            rows = compute_metrics(list(windows.values()), window_seconds)
            db.upsert_metrics(conn, rows)
        consumer.close()
        conn.close()
        print(f"[processor] shutdown, total consumed={consumed}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
