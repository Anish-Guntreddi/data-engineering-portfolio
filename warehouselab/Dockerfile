# WarehouseLab runtime image: dbt-postgres + dagster + dagster-dbt + psycopg2.
# Used by the `pipeline`, `dagster-webserver` and `dagster-daemon` services.
# Pinned to python:3.11-slim so the host's Python is never required to RUN.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DBT_PROJECT_DIR=/app/warehouse_dbt \
    DBT_PROFILES_DIR=/app/warehouse_dbt \
    DAGSTER_HOME=/app/dagster_home \
    REPO_ROOT=/app

# postgresql-client provides pg_isready (used by wait_for_postgres.sh).
# build-essential + libpq-dev cover any source builds for psycopg2.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        postgresql-client \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt

# Copy the project (generator, dbt project, orchestration, scripts).
COPY generator /app/generator
COPY warehouse_dbt /app/warehouse_dbt
COPY orchestration /app/orchestration
COPY scripts /app/scripts

RUN chmod +x /app/scripts/*.sh \
    && mkdir -p /app/dagster_home

# Pre-compile the dbt manifest so dagster-dbt can load assets at import time.
# DBT_PG_* are unset here; dbt deps/parse do not need a live DB connection
# (profiles.yml resolves env_var defaults). The baked target/manifest.json is
# what DbtProject.manifest_path points at for the dagster services.
RUN dbt deps  --project-dir /app/warehouse_dbt --profiles-dir /app/warehouse_dbt \
    && dbt parse --project-dir /app/warehouse_dbt --profiles-dir /app/warehouse_dbt \
    && test -f /app/warehouse_dbt/target/manifest.json

# Run as a non-root user for least privilege. The user owns /app so dbt can
# write target/ and dagster can write DAGSTER_HOME at runtime.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

# Default command runs the full one-command pipeline. Compose overrides this for
# the dagster services.
CMD ["bash", "/app/scripts/run_pipeline.sh"]
