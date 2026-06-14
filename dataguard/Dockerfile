# Single image used by the api, dashboard and runner services. python:3.11-slim
# per the monorepo conventions (the host's Python 3.14 is never required to RUN
# the pipeline).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Build deps for psycopg2-binary are not needed (it ships wheels), but we keep
# the image lean and add curl for healthchecks.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the application package and expectations.
COPY dataguard /app/dataguard
COPY expectations /app/expectations

# Run as an unprivileged user (defense in depth — never run containers as root).
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

# Default command is overridden per-service in docker-compose.yml.
CMD ["python", "-m", "dataguard.runner"]
