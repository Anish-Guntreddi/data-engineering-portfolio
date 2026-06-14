"""Streamlit dashboard for DataGuard.

Reads from the FastAPI service (preferred) and falls back to the database
directly if the API is unreachable. Shows:
  * per-table quality scores (metric cards)
  * a table of failing checks
  * a trend line of quality score over runs
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

import pandas as pd
import requests
import streamlit as st

API_URL = os.environ.get("DATAGUARD_API_URL", "http://localhost:8201")


def _api_get(path: str, params: Dict[str, Any] | None = None) -> Dict[str, Any] | None:
    """GET a JSON document from the API; return None on any failure."""
    try:
        resp = requests.get(f"{API_URL}{path}", params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def _load_scores() -> pd.DataFrame:
    data = _api_get("/scores")
    if data is not None:
        return pd.DataFrame(data.get("scores", []))
    # Fallback: read DB directly.
    from dataguard import db

    return db.fetch_scores()


def _load_results() -> pd.DataFrame:
    data = _api_get("/results")
    if data is not None:
        return pd.DataFrame(data.get("results", []))
    from dataguard import db

    return db.fetch_results(db.latest_run_id())


def _load_trends() -> pd.DataFrame:
    data = _api_get("/trends")
    if data is not None:
        return pd.DataFrame(data.get("trends", []))
    from dataguard import db

    return db.fetch_trends()


def main() -> None:
    st.set_page_config(page_title="DataGuard", layout="wide")
    st.title("DataGuard — Data Quality Monitoring")
    st.caption(f"API: {API_URL}")

    scores = _load_scores()
    results = _load_results()
    trends = _load_trends()

    st.header("Quality scores (latest run)")
    if scores.empty:
        st.warning("No scores yet. Run `make demo` to seed and check data.")
    else:
        cols = st.columns(max(1, len(scores)))
        for col, (_, row) in zip(cols, scores.iterrows()):
            score_val = float(row["table_score"])
            col.metric(label=str(row["table"]), value=f"{score_val:.1f}")
            col.progress(min(1.0, max(0.0, score_val / 100.0)))

    st.header("Failing checks (latest run)")
    if results.empty:
        st.info("No check results found.")
    else:
        failing = results[results["passed"] == False]  # noqa: E712
        if failing.empty:
            st.success("All checks passing for the latest run.")
        else:
            st.dataframe(
                failing[
                    ["table", "column", "check_name", "severity", "score", "detail"]
                ].reset_index(drop=True),
                use_container_width=True,
            )

    st.header("Quality score trend")
    if trends.empty:
        st.info("No trend data yet. Run `make demo` a few times to build history.")
    else:
        trends = trends.copy()
        trends["run_ts"] = pd.to_datetime(trends["run_ts"])
        pivot = trends.pivot_table(
            index="run_ts", columns="table", values="table_score", aggfunc="max"
        ).sort_index()
        st.line_chart(pivot)

    st.header("All check results (latest run)")
    if not results.empty:
        st.dataframe(results.reset_index(drop=True), use_container_width=True)


if __name__ == "__main__":
    main()
