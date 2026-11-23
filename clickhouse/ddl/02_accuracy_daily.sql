-- name: ddl_accuracy_daily
-- Daily accuracy facts. SummingMergeTree: rows with the same key are summed at merge time, so a late partition is
-- simply another insert (no update needed). Read with sum() ... GROUP BY, never row by row.
CREATE TABLE IF NOT EXISTS accuracy.accuracy_daily
(
    event_date      Date,
    customer_id     LowCardinality(String),
    browser         LowCardinality(String),
    browser_major   UInt16,
    device_type     LowCardinality(String),
    events          UInt64,
    bad_bot_events  UInt64,
    control_events  UInt64,
    tp              UInt64,
    fp              UInt64,
    fn              UInt64,
    tn              UInt64
)
ENGINE = SummingMergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (customer_id, event_date, browser, browser_major, device_type);

-- name: ddl_accuracy_daily_mv
-- Materialized view: maintains accuracy_daily at insert time from the raw events (control set, Fingerprint's
-- definitions). Dashboards then read thousands of rows instead of scanning billions of events.
CREATE MATERIALIZED VIEW IF NOT EXISTS accuracy.accuracy_daily_mv TO accuracy.accuracy_daily AS
SELECT
    toDate(ts_utc)                                                         AS event_date,
    customer_id, browser, browser_major, device_type,
    count()                                                                AS events,
    countIf(bot_result = 'bad')                                            AS bad_bot_events,
    countIf(method = 'deterministic' AND bot_result != 'bad')              AS control_events,
    countIf(method = 'deterministic' AND bot_result != 'bad' AND probabilistic_visitor_found AND probabilistic_visitor_id = visitor_id)   AS tp,
    countIf(method = 'deterministic' AND bot_result != 'bad' AND probabilistic_visitor_found AND probabilistic_visitor_id != visitor_id)  AS fp,
    countIf(method = 'deterministic' AND bot_result != 'bad' AND NOT probabilistic_visitor_found AND visitor_found)                     AS fn,
    countIf(method = 'deterministic' AND bot_result != 'bad' AND NOT probabilistic_visitor_found AND NOT visitor_found)                 AS tn
FROM accuracy.identification_events
GROUP BY event_date, customer_id, browser, browser_major, device_type;
