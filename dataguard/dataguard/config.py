"""Expectation loading.

Reads ``expectations/*.yml`` into plain dicts. This module uses only ``pyyaml``
(no infra libs) so it can be exercised on the host. The shapes it returns are
exactly what the checks consume as ``config``.

Expectation file shape (per table)::

    table: orders_clean
    timestamp_column: created_at      # optional, used as default freshness col
    schema:
      id: int
      amount: float
      status: string
      created_at: datetime
    checks:
      - type: null_check
        column: amount
        threshold: 0.0
        severity: warning
      - type: range_check
        column: amount
        min: 0
        max: 10000
        threshold: 1.0
      - type: freshness_check
        column: created_at
        max_age_hours: 48
      - type: drift_check
        column: amount
        baseline_query: "SELECT amount FROM orders_clean"
        bins: 10
        threshold: 0.2
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
# expectations/ lives at the project root, one level above the package dir.
DEFAULT_EXPECTATIONS_DIR = os.path.normpath(os.path.join(HERE, "..", "expectations"))


def load_expectation_file(path: str) -> Dict[str, Any]:
    """Load a single expectation YAML file into a dict."""
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Expectation file {path} did not parse to a mapping.")
    if "table" not in data:
        raise ValueError(f"Expectation file {path} is missing required key 'table'.")
    data.setdefault("schema", {})
    data.setdefault("checks", [])
    return data


def load_expectations(expectations_dir: str | None = None) -> List[Dict[str, Any]]:
    """Load every ``*.yml`` / ``*.yaml`` file in the expectations directory.

    Returns a list of table-expectation dicts, sorted by table name for
    deterministic ordering.
    """
    directory = expectations_dir or DEFAULT_EXPECTATIONS_DIR
    expectations: List[Dict[str, Any]] = []
    for name in sorted(os.listdir(directory)):
        if name.endswith((".yml", ".yaml")):
            expectations.append(load_expectation_file(os.path.join(directory, name)))
    expectations.sort(key=lambda d: d["table"])
    return expectations
