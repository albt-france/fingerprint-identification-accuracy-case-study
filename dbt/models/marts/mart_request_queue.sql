-- REQUEST QUEUE of the accuracy analyst with an impact x urgency priority (rules in docs/request_triage.md).
--   impact  1-4 : simulated ARR at stake (POC prospects count as 3: pipeline at stake; platform-wide questions as 3)
--   urgency 1-4 : low, medium, high, critical (as declared by the requester, checked at triage)
--   priority = impact x urgency (1..16) -> tier P1 (>= 12), P2 (>= 6), P3 (>= 3), P4
--   resolution target: P1 2 days, P2 5 days, P3 10 days, P4 20 days (calendar hours)
-- self_service_possible: the question is a standard one that the self-service tools answer without an analyst.
with q as (
    select
        r.*,
        c.is_prospect,
        case
            when c.is_prospect                       then 3
            when r.customer_id is null               then 3   -- platform-wide question (e.g. global dashboard)
            when r.arr_at_stake_usd >= 400000        then 4
            when r.arr_at_stake_usd >= 250000        then 3
            when r.arr_at_stake_usd >= 100000        then 2
            else 1
        end as impact,
        case r.urgency when 'critical' then 4 when 'high' then 3 when 'medium' then 2 else 1 end as urgency_score
    from {{ ref('stg_request_queue') }} r
    left join {{ ref('stg_customers') }} c using (customer_id)
)
select
    *,
    impact * urgency_score as priority_score,
    case when impact * urgency_score >= 12 then 'P1'
         when impact * urgency_score >= 6  then 'P2'
         when impact * urgency_score >= 3  then 'P3'
         else 'P4' end as priority_tier,
    case when impact * urgency_score >= 12 then 48
         when impact * urgency_score >= 6  then 120
         when impact * urgency_score >= 3  then 240
         else 480 end as sla_hours,
    date_diff('minute', opened_at, resolved_at) / 60.0 as hours_to_resolve,
    resolved_at is null as is_open,
    question_template in ('standard_accuracy_question', 'trend_question', 'report') as self_service_possible,
    {{ week_start('cast(opened_at as date)') }} as week_opened
from q
