-- name: ddl_daily_visitors
-- Distinct visitors per customer and day. Distinct counts cannot be summed across days, so the table stores
-- uniqState (a mergeable HyperLogLog-like state); uniqMerge combines states over any period or group.
CREATE TABLE IF NOT EXISTS accuracy.daily_visitors
(
    event_date   Date,
    customer_id  LowCardinality(String),
    visitors     AggregateFunction(uniq, String),
    accounts     AggregateFunction(uniq, String)
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (customer_id, event_date);

-- name: ddl_daily_visitors_mv
CREATE MATERIALIZED VIEW IF NOT EXISTS accuracy.daily_visitors_mv TO accuracy.daily_visitors AS
SELECT toDate(ts_utc) AS event_date, customer_id, uniqState(visitor_id) AS visitors, uniqState(assumeNotNull(linked_id)) AS accounts
FROM accuracy.identification_events
GROUP BY event_date, customer_id;

-- name: query_monthly_visitors
-- Reading it: visitors of a customer over a month (states merged, not summed).
SELECT customer_id, uniqMerge(visitors) AS visitors_month
FROM accuracy.daily_visitors
WHERE event_date BETWEEN '2026-10-01' AND '2026-10-31'
GROUP BY customer_id;
