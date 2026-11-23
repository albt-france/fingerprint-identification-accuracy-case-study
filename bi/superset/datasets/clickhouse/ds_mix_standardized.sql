-- Platform weekly rates (SIMULATED), ClickHouse dialect. Reference mix = control-event shares before 2026-10-19.
WITH seg AS (
    SELECT toMonday(event_date) AS week_start, browser, device_type, sum(control_events) AS n, sum(fp) AS fp
    FROM accuracy.accuracy_daily GROUP BY week_start, browser, device_type
),
ref AS (
    SELECT browser, device_type, sum(n) / (SELECT sum(n) FROM seg WHERE week_start < '2026-10-19') AS w
    FROM seg WHERE week_start < '2026-10-19' GROUP BY browser, device_type
)
SELECT s.week_start,
       sum(s.fp) / sum(s.n)                        AS fp_rate_crude,
       sumIf(r.w * s.fp / s.n, s.n > 0) / sumIf(r.w, s.n > 0) AS fp_rate_standardized
FROM seg AS s INNER JOIN ref AS r USING (browser, device_type)
GROUP BY s.week_start ORDER BY s.week_start
