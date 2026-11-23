-- Weekly platform-wide measured FP and FN rates, three ways:
--   crude          : sum(FP) / sum(control events) over every customer (what a naive global dashboard shows)
--   standardized   : DIRECT STANDARDIZATION to a fixed segment mix. Segment = browser x device type. Reference
--                    weights = control-event shares of each segment before 2026-10-19 (all customers). The rate of
--                    each segment this week is weighted by the reference weight, so a change of traffic MIX
--                    (a new mobile-heavy customer) cannot move the line; only a change WITHIN segments can.
--   stable_cohort  : crude rate restricted to customers live during the whole window (no onboarding effect).
with seg as (
    select {{ week_start('event_date') }} as week_start, browser, device_type, customer_id,
           sum(control_events) as n, sum(fp) as fp, sum(fn) as fn
    from {{ ref('fct_accuracy_daily') }}
    group by 1, 2, 3, 4
),
ref_w as (
    select browser, device_type, sum(n) * 1.0 / sum(sum(n)) over () as w
    from seg
    where week_start < date '2026-10-19'
    group by 1, 2
),
week_seg as (
    select week_start, browser, device_type, sum(n) as n, sum(fp) as fp, sum(fn) as fn
    from seg group by 1, 2, 3
),
std as (
    select
        ws.week_start,
        sum(r.w * ws.fp * 1.0 / ws.n) / sum(r.w) as fp_rate_standardized,
        sum(r.w * ws.fn * 1.0 / ws.n) / sum(r.w) as fn_rate_standardized
    from week_seg ws
    join ref_w r using (browser, device_type)
    where ws.n > 0
    group by 1
),
crude as (
    select week_start, sum(n) as control_events, sum(fp) * 1.0 / sum(n) as fp_rate_crude, sum(fn) * 1.0 / sum(n) as fn_rate_crude
    from seg group by 1
),
stable as (
    select s.week_start, sum(s.fp) * 1.0 / sum(s.n) as fp_rate_stable_cohort, sum(s.fn) * 1.0 / sum(s.n) as fn_rate_stable_cohort
    from seg s
    join {{ ref('stg_customers') }} c using (customer_id)
    where c.start_date <= cast('{{ var("window_start") }}' as date)
    group by 1
)
select *
from crude
join std using (week_start)
join stable using (week_start)
order by week_start
