-- Weekly health status per customer (SIMULATED).
SELECT week_start, customer_id, csm_pod, sector, is_prospect, arr_usd_simulated, health_status, health_reasons,
       fp_rate, fp_rate_lo, fp_rate_hi, fn_rate, fn_rate_lo, fn_rate_hi, z_fp, z_fn, bad_bot_share, incognito_share,
       below_threshold_share, open_requests
FROM mart_customer_health
