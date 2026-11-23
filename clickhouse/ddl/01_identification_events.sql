-- Target tables as they would be created in ClickHouse for the accuracy marts (production design, not executed:
-- the public playground is read-only). Syntax checked with EXPLAIN AST on the playground: see clickhouse/README.md.

-- name: ddl_identification_events
-- Raw identification events. ReplacingMergeTree keyed on event_id: a re-sent batch (same event_id, later loaded_at)
-- collapses to the latest version when parts merge. Queries that must be exact use FINAL or deduplicate in dbt.
CREATE TABLE IF NOT EXISTS accuracy.identification_events
(
    event_id                     String,
    ts_utc                       DateTime64(3, 'UTC'),
    event_date                   Date MATERIALIZED toDate(ts_utc),
    customer_id                  LowCardinality(String),
    visitor_id                   String,
    visitor_found                Bool,
    confidence_score             Float32,
    method                       LowCardinality(String),
    probabilistic_visitor_id     Nullable(String),
    probabilistic_visitor_found  Nullable(Bool),
    browser                      LowCardinality(String),
    browser_major                UInt16,
    os                           LowCardinality(String),
    device_type                  LowCardinality(String),
    is_incognito                 Bool,
    is_vpn                       Bool,
    bot_result                   LowCardinality(String),
    country                      LowCardinality(String),
    linked_id                    Nullable(String),
    loaded_at                    DateTime('UTC')
)
ENGINE = ReplacingMergeTree(loaded_at)
PARTITION BY toYYYYMM(event_date)
ORDER BY (customer_id, event_date, event_id)
TTL event_date + INTERVAL 13 MONTH;
