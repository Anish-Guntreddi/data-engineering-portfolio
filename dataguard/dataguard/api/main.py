"""FastAPI surface for DataGuard.

Endpoints (all read from the ``dq_results`` table via db.py):

  GET /health   -> liveness + DB connectivity
  GET /tables   -> demo tables present in the database
  GET /results  -> raw check results (optionally ?run_id=...)
  GET /scores   -> one quality score per table for the latest (or given) run
  GET /trends   -> per-run, per-table score history for the trend chart
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, Query

from dataguard import db

app = FastAPI(title="DataGuard API", version="0.1.0")


def _records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Convert a DataFrame to JSON-safe records (timestamps -> ISO strings)."""
    if df.empty:
        return []
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].astype(str)
    return out.to_dict(orient="records")


@app.get("/health")
def health() -> Dict[str, Any]:
    """Liveness probe. Reports DB reachability without failing the request."""
    try:
        db.query_df("SELECT 1 AS ok")
        db_ok = True
    except Exception as exc:  # pragma: no cover - exercised in e2e only
        return {"status": "degraded", "db": False, "error": str(exc)}
    return {"status": "ok", "db": db_ok}


@app.get("/tables")
def tables() -> Dict[str, Any]:
    """List user tables in the database."""
    try:
        names = db.list_tables()
    except Exception as exc:  # pragma: no cover
        return {"tables": [], "error": str(exc)}
    return {"tables": names}


@app.get("/results")
def results(run_id: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    """Return check results, optionally filtered to a single run_id."""
    df = db.fetch_results(run_id)
    return {"count": int(len(df)), "results": _records(df)}


@app.get("/scores")
def scores(run_id: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    """Return one quality score per table for the latest (or given) run."""
    df = db.fetch_scores(run_id)
    return {"scores": _records(df)}


@app.get("/trends")
def trends() -> Dict[str, Any]:
    """Return per-run, per-table score history for trend visualisation."""
    df = db.fetch_trends()
    return {"trends": _records(df)}
