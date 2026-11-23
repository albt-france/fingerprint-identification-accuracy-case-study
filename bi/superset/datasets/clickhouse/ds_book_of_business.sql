-- Weekly book of business per CSM pod (SIMULATED), ClickHouse dialect.
SELECT csm_pod, week_start, count() AS customers, countIf(is_prospect) AS prospects, sum(arr_usd_simulated) AS arr_usd_simulated,
       countIf(health_status = 'red') AS red, countIf(health_status = 'amber') AS amber,
       countIf(health_status = 'green') AS green, countIf(health_status = 'grey') AS grey,
       sumIf(arr_usd_simulated, health_status IN ('red', 'amber')) AS arr_at_risk_usd_simulated,
       arrayStringConcat(arraySort(groupArrayIf(customer_id, health_status IN ('red', 'amber'))), ', ') AS customers_to_watch
FROM accuracy.mart_customer_health FINAL
GROUP BY csm_pod, week_start
