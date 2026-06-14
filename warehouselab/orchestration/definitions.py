"""Dagster Definitions for WarehouseLab.

Exposes the dbt project as Dagster dbt assets via ``dagster_dbt`` plus an
upstream ``seed_raw`` asset that runs the deterministic generator load. A daily
schedule materialises everything (seed -> staging -> marts).

This module must import cleanly inside the pipeline container (where dagster,
dagster-dbt and dbt-postgres are installed). It does NOT import the pure
generator's infra-free path for testing -- the generator load is infra-touching
and intentionally containerized.
"""

from __future__ import annotations

import os
from pathlib import Path

from dagster import (
    AssetExecutionContext,
    AssetKey,
    Definitions,
    MaterializeResult,
    ScheduleDefinition,
    asset,
    define_asset_job,
)
from dagster_dbt import DbtCliResource, DbtProject, dbt_assets

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
# Repository layout inside the container: /app/orchestration/definitions.py and
# /app/warehouse_dbt/. DBT_PROJECT_DIR can override for local runs.
_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent
DBT_PROJECT_DIR = Path(os.environ.get("DBT_PROJECT_DIR", _REPO_ROOT / "warehouse_dbt"))

# DbtProject manages manifest preparation. When DAGSTER_DBT_PARSE_PROJECT_ON_LOAD
# is set (e.g. during image build) it parses the project; otherwise it expects a
# prebuilt manifest at target/manifest.json.
dbt_project = DbtProject(project_dir=os.fspath(DBT_PROJECT_DIR))
dbt_project.prepare_if_dev()


# --------------------------------------------------------------------------- #
# Upstream asset: seed the raw schema from the deterministic generator.
# --------------------------------------------------------------------------- #
@asset(
    compute_kind="python",
    description="Run the deterministic generator and load raw.users/events/orders.",
)
def seed_raw(context: AssetExecutionContext) -> MaterializeResult:
    # Imported lazily so this module imports even if psycopg2 is unavailable at
    # import time in some environments; the generator load owns the infra deps.
    from generator.load import load

    golden = load()
    context.log.info(
        "seeded raw schema; golden date=%s dau=%s revenue=%s",
        golden["golden_date"],
        golden["golden_dau"],
        golden["golden_revenue"],
    )
    return MaterializeResult(
        metadata={
            "golden_date": golden["golden_date"],
            "golden_dau": golden["golden_dau"],
            "golden_revenue": golden["golden_revenue"],
            "golden_n_orders": golden["golden_n_orders"],
            "n_events": golden["n_events"],
            "n_orders_total": golden["n_orders_total"],
            "n_users": golden["n_users"],
        }
    )


# --------------------------------------------------------------------------- #
# dbt assets. The three raw.* dbt sources are collapsed onto the single
# ``seed_raw`` asset key so the generator load is wired upstream of staging:
# seed_raw -> staging -> marts. `dbt build` runs models AND tests (including the
# singular golden tests).
# --------------------------------------------------------------------------- #
from dagster_dbt import DagsterDbtTranslator  # noqa: E402


class _Translator(DagsterDbtTranslator):
    def get_asset_key(self, dbt_resource_props):  # type: ignore[override]
        if dbt_resource_props.get("resource_type") == "source":
            return AssetKey(["seed_raw"])
        return super().get_asset_key(dbt_resource_props)


@dbt_assets(manifest=dbt_project.manifest_path, dagster_dbt_translator=_Translator())
def warehouse_dbt_assets_linked(context: AssetExecutionContext, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()


# --------------------------------------------------------------------------- #
# Job + daily schedule that materialises the whole pipeline.
# --------------------------------------------------------------------------- #
materialize_all_job = define_asset_job(
    name="materialize_all",
    description="Seed raw data then build & test all dbt models.",
)

daily_schedule = ScheduleDefinition(
    name="daily_refresh",
    job=materialize_all_job,
    cron_schedule="0 6 * * *",
    execution_timezone="UTC",
)


defs = Definitions(
    assets=[seed_raw, warehouse_dbt_assets_linked],
    jobs=[materialize_all_job],
    schedules=[daily_schedule],
    resources={
        "dbt": DbtCliResource(project_dir=os.fspath(DBT_PROJECT_DIR)),
    },
)
