-- Weekly accuracy per customer (weeks start on Monday), with 95% Wilson intervals.
-- Rates are computed on the CONTROL set (Fingerprint's method), bad robots excluded.
--   measured FP rate = FP / control events ; measured FN rate = FN / control events
-- truth_* rates use ALL human events (simulation only) and show the bias of the control-set measurement.
with w as (
    select
        {{ week_start('event_date') }}         as week_start,
        customer_id,
        sum(events)                            as events,
        sum(human_events)                      as human_events,
        sum(bad_bot_events)                    as bad_bot_events,
        sum(incognito_events)                  as incognito_events,
        sum(new_visitor_events)                as new_visitor_events,
        sum(control_events)                    as control_events,
        sum(tp) as tp, sum(fp) as fp, sum(fn) as fn, sum(tn) as tn,
        sum(truth_tp) as truth_tp, sum(truth_fp) as truth_fp, sum(truth_fn) as truth_fn, sum(truth_tn) as truth_tn,
        sum(found_events)                      as found_events,
        sum(below_threshold_events)            as below_threshold_events,
        count(distinct event_date)             as days_with_data
    from {{ ref('fct_accuracy_daily') }}
    group by 1, 2
)
select
    *,
    {{ ratio('fp', 'control_events') }}                          as fp_rate,
    {{ wilson_lower('fp', 'control_events') }}                   as fp_rate_lo,
    {{ wilson_upper('fp', 'control_events') }}                   as fp_rate_hi,
    {{ ratio('fn', 'control_events') }}                          as fn_rate,
    {{ wilson_lower('fn', 'control_events') }}                   as fn_rate_lo,
    {{ wilson_upper('fn', 'control_events') }}                   as fn_rate_hi,
    {{ ratio('truth_fp', 'truth_tp + truth_fp + truth_fn + truth_tn') }}   as truth_fp_rate,
    {{ ratio('truth_fn', 'truth_tp + truth_fp + truth_fn + truth_tn') }}   as truth_fn_rate,
    {{ ratio('control_events', 'human_events') }}                as control_share,
    {{ ratio('incognito_events', 'human_events') }}              as incognito_share,
    {{ ratio('bad_bot_events', 'events') }}                      as bad_bot_share,
    {{ ratio('new_visitor_events', 'human_events') }}            as new_visitor_share,
    {{ ratio('below_threshold_events', 'found_events') }}        as below_threshold_share
from w
