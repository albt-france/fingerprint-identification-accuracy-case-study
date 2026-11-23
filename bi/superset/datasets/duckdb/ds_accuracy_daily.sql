-- Superset virtual dataset (DuckDB dialect, database dbt/fingerprint.duckdb opened read-only). SIMULATED.
-- Saved metrics: fp_rate = SUM(fp) / NULLIF(SUM(control_events), 0) ; fn_rate = SUM(fn) / NULLIF(SUM(control_events), 0)
SELECT event_date, customer_id, browser, browser_major, device_type, version_age_bucket,
       events, bad_bot_events, human_events, incognito_events, new_visitor_events, control_events, tp, fp, fn, tn,
       found_events, below_threshold_events
FROM fct_accuracy_daily
