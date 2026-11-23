-- Weekly ACCURACY HEALTH status per customer (rules in METRICS.md, section "Health status").
-- Baseline = the customer's own previous 4 weeks (pooled). Change test = quasi-binomial z-score:
--   z = (k - n * p0) / sqrt(phi * n * p0 * (1 - p0)),  phi = var('overdispersion_phi') (events of one device are
--   not independent, so the plain binomial variance is too small; phi is estimated in src/monitoring.py).
-- red   : FP or FN rate up with z > 3, OR bad-robot share > 20%, OR an open critical request
-- amber : FP or FN rate up with z > 2, OR bad-robot share > 10%, OR incognito share up > 5 points, OR an open high request
-- grey  : fewer than 2 weeks of history (no baseline yet)
-- green : otherwise
with w as (
    select
        *,
        sum(control_events)   over prev4 as base_n,
        sum(fp)               over prev4 as base_fp,
        sum(fn)               over prev4 as base_fn,
        sum(incognito_events) over prev4 as base_incognito,
        sum(human_events)     over prev4 as base_human,
        count(*)              over prev4 as base_weeks
    from {{ ref('fct_accuracy_weekly_customer') }}
    window prev4 as (partition by customer_id order by week_start rows between 4 preceding and 1 preceding)
),
z as (
    select
        *,
        {{ ratio('base_fp', 'base_n') }} as fp_rate_baseline,
        {{ ratio('base_fn', 'base_n') }} as fn_rate_baseline,
        case when base_n > 0 and base_fp > 0 then
            (fp - control_events * base_fp * 1.0 / base_n)
            / sqrt({{ var('overdispersion_phi') }} * control_events * (base_fp * 1.0 / base_n) * (1 - base_fp * 1.0 / base_n))
        end as z_fp,
        case when base_n > 0 and base_fn > 0 then
            (fn - control_events * base_fn * 1.0 / base_n)
            / sqrt({{ var('overdispersion_phi') }} * control_events * (base_fn * 1.0 / base_n) * (1 - base_fn * 1.0 / base_n))
        end as z_fn,
        incognito_share - {{ ratio('base_incognito', 'base_human') }} as incognito_share_change
    from w
),
open_requests as (
    -- requests still open at the end of each week (Sunday 23:59)
    select
        c.customer_id,
        wk.week_start,
        {{ count_if("q.urgency = 'critical'") }} as open_critical,
        {{ count_if("q.urgency = 'high'") }}     as open_high,
        count(q.request_id)                       as open_requests
    from (select distinct week_start from z) wk
    cross join {{ ref('stg_customers') }} c
    left join {{ ref('stg_request_queue') }} q
        on q.customer_id = c.customer_id
       and q.opened_at < wk.week_start + interval 7 day
       and (q.resolved_at is null or q.resolved_at >= wk.week_start + interval 7 day)
    group by 1, 2
)
select
    z.week_start,
    z.customer_id,
    c.csm_pod,
    c.sector,
    c.is_prospect,
    c.arr_usd_simulated,
    z.events, z.control_events, z.fp, z.fn,
    z.fp_rate, z.fp_rate_lo, z.fp_rate_hi, z.fn_rate, z.fn_rate_lo, z.fn_rate_hi,
    z.fp_rate_baseline, z.fn_rate_baseline, z.z_fp, z.z_fn,
    z.bad_bot_share, z.incognito_share, z.incognito_share_change, z.below_threshold_share,
    coalesce(o.open_requests, 0) as open_requests,
    coalesce(o.open_critical, 0) as open_critical,
    coalesce(o.open_high, 0)     as open_high,
    case
        when z.base_weeks < 2 then 'grey'
        when z.z_fp > 3 or z.z_fn > 3 or z.bad_bot_share > 0.20 or o.open_critical > 0 then 'red'
        when z.z_fp > 2 or z.z_fn > 2 or z.bad_bot_share > 0.10 or z.incognito_share_change > 0.05 or o.open_high > 0 then 'amber'
        else 'green'
    end as health_status,
    concat_ws('; ',
        case when z.base_weeks < 2 then 'less than 2 weeks of history' end,
        case when z.z_fp > 2 then 'FP rate up (z=' || round(z.z_fp, 1) || ')' end,
        case when z.z_fn > 2 then 'FN rate up (z=' || round(z.z_fn, 1) || ')' end,
        case when z.bad_bot_share > 0.10 then 'bad robots ' || round(100 * z.bad_bot_share) || '% of traffic' end,
        case when z.incognito_share_change > 0.05 then 'incognito share +' || round(100 * z.incognito_share_change) || ' pts' end,
        case when o.open_critical > 0 then o.open_critical || ' open critical request(s)' end,
        case when o.open_high > 0 then o.open_high || ' open high request(s)' end
    ) as health_reasons
from z
join {{ ref('stg_customers') }} c using (customer_id)
left join open_requests o using (customer_id, week_start)
