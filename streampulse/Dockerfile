# Single image used by every StreamPulse runtime service (producer, processor,
# alerter, dashboard, e2e). The host's Python 3.14 is never required to RUN the
# pipeline — everything runs in this python:3.11-slim container.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# psycopg2-binary ships wheels; confluent-kafka wheels bundle librdkafka. No
# apt build deps are required, but we keep curl for simple healthchecks.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Application code + e2e script.
COPY streampulse /app/streampulse
COPY scripts /app/scripts

# Run as an unprivileged user (not root) for safer containers.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

# Default command is overridden per-service in docker-compose.yml.
CMD ["python", "-m", "streampulse.producer.main"]
