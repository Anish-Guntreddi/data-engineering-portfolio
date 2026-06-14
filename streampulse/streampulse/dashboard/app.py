"""Streamlit dashboard: live StreamPulse metrics and alerts.

Runtime service (containerized only). Reads the ``metrics`` and ``alerts`` tables
from postgres and renders an auto-refreshing live view.

Environment
-----------
REFRESH_SECONDS   auto-refresh interval (default 5)
PG*               standard libpq env vars (see db.dsn_from_env)
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

try:
    from streampulse import db
    from streampulse.metrics import CONVERSION_RATE, EVENTS_PER_MINUTE
except ModuleNotFoundError:  # pragma: no cover - container path fallback
    sys.path.insert(0, "/app")
    from streampulse import db
    from streampulse.metrics import CONVERSION_RATE, EVENTS_PER_MINUTE


REFRESH_SECONDS = int(os.getenv("REFRESH_SECONDS", "5"))


def _fmt_ts(epoch: float) -> str:
    return datetime.fromtimestamp(float(epoch), tz=timezone.utc).strftime(
        "%H:%M:%S"
    )


@st.cache_resource
def get_connection():
    """One pooled connection per Streamlit session (cached resource)."""
    conn = db.connect()
    db.init_schema(conn)
    return conn


def load_data(conn):
    metrics = db.fetch_metrics(conn, limit=1000)
    alerts = db.fetch_alerts(conn, limit=100)
    return metrics, alerts


def main() -> None:
    st.set_page_config(page_title="StreamPulse", layout="wide")
    st.title("StreamPulse — Real-Time Event Analytics")
    st.caption(
        "producer -> Redpanda -> processor -> metrics (Postgres) -> "
        "dashboard + alerter"
    )

    try:
        conn = get_connection()
    except Exception as exc:  # noqa: BLE001
        st.error(f"Cannot connect to Postgres yet: {exc}")
        st.stop()
        return

    try:
        # Make sure the cached connection is healthy; reconnect on failure.
        conn.rollback()
        metrics, alerts = load_data(conn)
    except Exception as exc:  # noqa: BLE001
        get_connection.clear()
        st.warning(f"Reconnecting to Postgres: {exc}")
        time.sleep(REFRESH_SECONDS)
        st.rerun()
        return

    mdf = pd.DataFrame(metrics)
    adf = pd.DataFrame(alerts)

    col1, col2, col3 = st.columns(3)
    if not mdf.empty:
        epm = mdf[mdf["metric"] == EVENTS_PER_MINUTE]
        conv = mdf[mdf["metric"] == CONVERSION_RATE]
        latest_epm = epm.sort_values("window_start")["value"].iloc[-1] if not epm.empty else 0.0
        latest_conv = conv.sort_values("window_start")["value"].iloc[-1] if not conv.empty else 0.0
        col1.metric("Latest events/min", f"{latest_epm:.1f}")
        col2.metric("Latest conversion", f"{latest_conv:.4f}")
    else:
        col1.metric("Latest events/min", "—")
        col2.metric("Latest conversion", "—")
    col3.metric("Total alerts", str(len(adf)))

    st.subheader("Events per minute (recent windows)")
    if not mdf.empty:
        epm = mdf[mdf["metric"] == EVENTS_PER_MINUTE].copy()
        if not epm.empty:
            epm["window"] = epm["window_start"].map(_fmt_ts)
            chart = epm.sort_values("window_start").set_index("window")[["value"]]
            st.line_chart(chart, height=240)
    else:
        st.info("Waiting for the processor to populate metrics…")

    st.subheader("Conversion rate (recent windows)")
    if not mdf.empty:
        conv = mdf[mdf["metric"] == CONVERSION_RATE].copy()
        if not conv.empty:
            conv["window"] = conv["window_start"].map(_fmt_ts)
            chart = conv.sort_values("window_start").set_index("window")[["value"]]
            st.line_chart(chart, height=240)

    st.subheader("Alerts")
    if not adf.empty:
        adf = adf.copy()
        adf["when"] = adf["ts"].map(_fmt_ts)
        st.dataframe(
            adf[["when", "metric", "value", "threshold", "message"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.success("No alerts — all metrics within thresholds.")

    st.caption(f"Auto-refreshing every {REFRESH_SECONDS}s.")
    time.sleep(REFRESH_SECONDS)
    st.rerun()


if __name__ == "__main__":
    main()
