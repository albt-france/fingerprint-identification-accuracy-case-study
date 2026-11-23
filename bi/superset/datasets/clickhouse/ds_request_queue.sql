-- Request queue (SIMULATED), ClickHouse dialect.
SELECT request_id, opened_at, resolved_at, toMonday(toDate(opened_at)) AS week_opened, requesting_team, request_type,
       question_template, customer_id, arr_at_stake_usd, urgency, impact, priority_score, priority_tier, sla_hours,
       dateDiff('minute', opened_at, resolved_at) / 60 AS hours_to_resolve, resolved_at IS NULL AS is_open,
       question_template IN ('standard_accuracy_question', 'trend_question', 'report') AS self_service_possible, effort_hours
FROM accuracy.mart_request_queue
