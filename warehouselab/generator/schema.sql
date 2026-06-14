-- Raw landing schema for WarehouseLab.
-- The generator loads synthetic data here; dbt sources read from raw.*.
-- Idempotent: safe to re-run. The loader TRUNCATEs before inserting so a
-- `make run` from an empty database always yields the same deterministic state.

CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.users (
    user_id      BIGINT      NOT NULL PRIMARY KEY,
    signup_date  DATE        NOT NULL,
    country      TEXT        NOT NULL,
    plan         TEXT        NOT NULL
);

CREATE TABLE IF NOT EXISTS raw.events (
    event_id    BIGINT       NOT NULL PRIMARY KEY,
    user_id     BIGINT       NOT NULL,
    event_type  TEXT         NOT NULL,
    event_ts    TIMESTAMP    NOT NULL,
    session_id  TEXT         NOT NULL
);

CREATE TABLE IF NOT EXISTS raw.orders (
    order_id   BIGINT        NOT NULL PRIMARY KEY,
    user_id    BIGINT        NOT NULL,
    amount     NUMERIC(12,2) NOT NULL,
    order_ts   TIMESTAMP     NOT NULL,
    status     TEXT          NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_event_ts ON raw.events (event_ts);
CREATE INDEX IF NOT EXISTS idx_orders_order_ts ON raw.orders (order_ts);
