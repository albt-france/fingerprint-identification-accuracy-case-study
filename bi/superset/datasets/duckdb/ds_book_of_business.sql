-- Weekly book of business per CSM pod (SIMULATED).
SELECT csm_pod, week_start, customers, prospects, arr_usd_simulated, red, amber, green, grey,
       arr_at_risk_usd_simulated, customers_to_watch, status_changes, open_requests
FROM mart_book_of_business
