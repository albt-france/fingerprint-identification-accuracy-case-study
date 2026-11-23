{{
  config(
    materialized = 'incremental',
    incremental_strategy = 'delete+insert',
    unique_key = ['event_date', 'customer_id', 'browser', 'browser_major', 'device_type'],
    on_schema_change = 'fail'
  )
}}
-- Daily accuracy facts at the grain day x customer x browser x major version x device type.
-- Measured rates follow Fingerprint's control / test definitions (int_events_measured) and EXCLUDE bad robots
-- (bot_result = 'bad'), which are reported separately. truth_* columns exist only because the data is simulated.
--
-- INCREMENTAL: on each run only the last var('lookback_days') days (3) already in the table are recomputed,
-- plus anything newer. Why a lookback window and not "only new days": a partition can arrive late
-- (2026-10-28 was loaded two days late) and re-sent rows can land after the first load. With delete+insert on
-- the unique key, recomputed days replace the old rows, so late data is absorbed without a full refresh.

with events as (
    select *
    from {{ ref('stg_identification_events') }}
    {% if is_incremental() %}
    -- recompute the lookback window: days >= (latest day already built - 3 days)
    where event_date >= (select max(event_date) - interval '{{ var("lookback_days") }} days' from {{ this }})
    {% endif %}
),
measured as (
    select *
    from {{ ref('int_events_measured') }}
    {% if is_incremental() %}
    where event_date >= (select max(event_date) - interval '{{ var("lookback_days") }} days' from {{ this }})
    {% endif %}
),
truth as (
    select *
    from {{ ref('int_events_truth') }}
    {% if is_incremental() %}
    where event_date >= (select max(event_date) - interval '{{ var("lookback_days") }} days' from {{ this }})
    {% endif %}
),
customers as (
    select customer_id, confidence_threshold from {{ ref('stg_customers') }}
),
volume as (
    select
        e.event_date, e.customer_id, e.browser, e.browser_major, e.device_type,
        count(*)                                                                as events,
        {{ count_if('e.is_bad_bot') }}                                          as bad_bot_events,
        {{ count_if('not e.is_bad_bot') }}                                      as human_events,
        {{ count_if('e.is_incognito and not e.is_bad_bot') }}                   as incognito_events,
        {{ count_if('not e.visitor_found and not e.is_bad_bot') }}              as new_visitor_events,
        {{ count_if('e.is_control and not e.is_bad_bot') }}                     as control_events,
        -- events whose confidence is under the threshold the customer uses for step-up (e.g. one-time codes)
        {{ count_if('e.visitor_found and e.confidence_score < c.confidence_threshold and not e.is_bad_bot') }} as below_threshold_events,
        {{ count_if('e.visitor_found and not e.is_bad_bot') }}                  as found_events,
        avg(case when e.visitor_found and not e.is_bad_bot and e.method = 'probabilistic' then e.confidence_score end) as avg_confidence_probabilistic
    from events e
    join customers c using (customer_id)
    group by 1, 2, 3, 4, 5
),
m as (
    select
        event_date, customer_id, browser, browser_major, device_type,
        {{ count_if("measured_outcome = 'TP'") }} as tp,
        {{ count_if("measured_outcome = 'FP'") }} as fp,
        {{ count_if("measured_outcome = 'FN'") }} as fn,
        {{ count_if("measured_outcome = 'TN'") }} as tn
    from measured
    where not is_bad_bot
    group by 1, 2, 3, 4, 5
),
t as (
    select
        event_date, customer_id, browser, browser_major, device_type,
        {{ count_if("truth_outcome = 'TP'") }} as truth_tp,
        {{ count_if("truth_outcome = 'FP'") }} as truth_fp,
        {{ count_if("truth_outcome = 'FN'") }} as truth_fn,
        {{ count_if("truth_outcome = 'TN'") }} as truth_tn
    from truth
    where not is_bad_bot
    group by 1, 2, 3, 4, 5
)
select
    v.*,
    coalesce(m.tp, 0) as tp,
    coalesce(m.fp, 0) as fp,
    coalesce(m.fn, 0) as fn,
    coalesce(m.tn, 0) as tn,
    coalesce(t.truth_tp, 0) as truth_tp,
    coalesce(t.truth_fp, 0) as truth_fp,
    coalesce(t.truth_fn, 0) as truth_fn,
    coalesce(t.truth_tn, 0) as truth_tn,
    a.days_since_release,
    coalesce(a.version_age_bucket, 'unknown') as version_age_bucket,
    current_timestamp as built_at
from volume v
left join m using (event_date, customer_id, browser, browser_major, device_type)
left join t using (event_date, customer_id, browser, browser_major, device_type)
left join {{ ref('int_version_age') }} a using (browser, browser_major, event_date)
