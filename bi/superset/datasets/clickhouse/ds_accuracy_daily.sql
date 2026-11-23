-- Superset virtual dataset (ClickHouse dialect, table accuracy.accuracy_daily from clickhouse/ddl/02). SIMULATED.
-- SummingMergeTree: always aggregate (sum) in the chart, never read rows one by one.
SELECT event_date, customer_id, browser, browser_major, device_type,
       sum(events) AS events, sum(bad_bot_events) AS bad_bot_events, sum(control_events) AS control_events,
       sum(tp) AS tp, sum(fp) AS fp, sum(fn) AS fn, sum(tn) AS tn
FROM accuracy.accuracy_daily
GROUP BY event_date, customer_id, browser, browser_major, device_type
