-- HIDDEN TRUTH (simulation only): true device of each event. Used to measure the bias of the measurement.
select
    event_id,
    true_device_id,
    true_visitor_id,
    device_seen_before,
    true_is_internal_agent,
    true_is_bad_bot
from {{ source('sim', 'device_truth') }}
