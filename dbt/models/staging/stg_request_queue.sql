select
    request_id,
    opened_at,
    resolved_at,
    requesting_team,
    request_type,
    question_template,
    customer_id,
    arr_at_stake_usd,
    urgency,
    effort_hours,
    title,
    linked_hidden_event
from {{ source('sim', 'request_queue') }}
