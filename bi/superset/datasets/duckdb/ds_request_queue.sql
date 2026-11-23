-- Request queue with priority and self-service flag (SIMULATED).
SELECT request_id, opened_at, resolved_at, week_opened, requesting_team, request_type, question_template, customer_id,
       arr_at_stake_usd, urgency, impact, priority_score, priority_tier, sla_hours, hours_to_resolve, is_open, self_service_possible,
       effort_hours
FROM mart_request_queue
