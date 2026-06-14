#!/usr/bin/env bash
# The ONE COMMAND body for WarehouseLab.
#   1. wait for postgres
#   2. run the deterministic generator load (raw schema: empty -> populated)
#   3. dbt deps (install packages)
#   4. dbt build (run models + run all tests, incl. golden singular tests)
# Exits non-zero on the first failure so `make run` fails loudly.
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/app}"
DBT_PROJECT_DIR="${DBT_PROJECT_DIR:-${REPO_ROOT}/warehouse_dbt}"
export DBT_PROFILES_DIR="${DBT_PROFILES_DIR:-${DBT_PROJECT_DIR}}"

echo "=============================================================="
echo "[pipeline] WarehouseLab pipeline starting"
echo "[pipeline] repo_root=${REPO_ROOT} dbt_project=${DBT_PROJECT_DIR}"
echo "=============================================================="

# 1. wait for postgres -------------------------------------------------------
bash "${REPO_ROOT}/scripts/wait_for_postgres.sh"

# 2. generator load ----------------------------------------------------------
echo "[pipeline] loading deterministic seed data into raw.*"
cd "${REPO_ROOT}"
python -m generator.load

# 3. dbt deps ----------------------------------------------------------------
echo "[pipeline] installing dbt packages (dbt deps)"
dbt deps --project-dir "${DBT_PROJECT_DIR}" --profiles-dir "${DBT_PROFILES_DIR}"

# 4. dbt build (run + test) --------------------------------------------------
echo "[pipeline] dbt build (run models + run tests)"
dbt build --project-dir "${DBT_PROJECT_DIR}" --profiles-dir "${DBT_PROFILES_DIR}"

echo "=============================================================="
echo "[pipeline] SUCCESS: marts populated and all dbt tests passed"
echo "=============================================================="
