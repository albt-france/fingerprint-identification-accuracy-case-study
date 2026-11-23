-- FIRST-PASS SQL SCREEN for accuracy anomalies (the full alerting logic, with day-of-week adjustment,
-- Benjamini-Hochberg correction and the 2-consecutive-days rule, lives in src/monitoring.py).
-- Series = customer x browser x major version, measured on the control set. For each day: today's FP and FN
-- counts against the pooled rate of the previous 28 days of the same series (quasi-binomial z, phi from vars).
-- A candidate needs at least 100 control events today and 500 in the baseline.
with d as (
    select event_date, customer_id, browser, browser_major,
           sum(control_events) as n, sum(fp) as fp, sum(fn) as fn
    from {{ ref('fct_accuracy_daily') }}
    group by 1, 2, 3, 4
),
b as (
    select
        *,
        sum(n)  over w as base_n,
        sum(fp) over w as base_fp,
        sum(fn) over w as base_fn
    from d
    window w as (partition by customer_id, browser, browser_major order by event_date
                 range between interval 28 days preceding and interval 1 day preceding)
),
z as (
    select
        *,
        {{ ratio('fp', 'n') }} as fp_rate,
        {{ ratio('fn', 'n') }} as fn_rate,
        {{ ratio('base_fp', 'base_n') }} as fp_rate_baseline,
        {{ ratio('base_fn', 'base_n') }} as fn_rate_baseline,
        case when base_n >= 500 and base_fp > 0 then
            (fp - n * base_fp * 1.0 / base_n) / sqrt({{ var('overdispersion_phi') }} * n * (base_fp * 1.0 / base_n) * (1 - base_fp * 1.0 / base_n)) end as z_fp,
        case when base_n >= 500 and base_fn > 0 then
            (fn - n * base_fn * 1.0 / base_n) / sqrt({{ var('overdispersion_phi') }} * n * (base_fn * 1.0 / base_n) * (1 - base_fn * 1.0 / base_n)) end as z_fn
    from b
)
select *
from z
where n >= 100 and (z_fp > 3 or z_fn > 3)
