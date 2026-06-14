#!/usr/bin/env bash
# Block until Postgres is accepting connections, or fail after a timeout.
# Reads PGHOST/PGPORT/PGUSER/PGDATABASE/PGPASSWORD from the environment.
set -euo pipefail

PGHOST="${PGHOST:-postgres}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-postgres}"
PGDATABASE="${PGDATABASE:-warehouse}"
export PGPASSWORD="${PGPASSWORD:-postgres}"

ATTEMPTS="${WAIT_ATTEMPTS:-60}"
SLEEP_SECS="${WAIT_SLEEP:-2}"

echo "[wait] waiting for postgres ${PGHOST}:${PGPORT} (db=${PGDATABASE}, up to $((ATTEMPTS * SLEEP_SECS))s)"

i=0
while [ "$i" -lt "$ATTEMPTS" ]; do
  if pg_isready -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" >/dev/null 2>&1; then
    echo "[wait] postgres is ready"
    exit 0
  fi
  i=$((i + 1))
  echo "[wait] not ready yet (attempt ${i}/${ATTEMPTS})..."
  sleep "$SLEEP_SECS"
done

echo "[wait] ERROR: postgres did not become ready in time" >&2
exit 1
