{{ config(materialized='view') }}  -- a view: the incremental mart filters it, so only the lookback days are scanned
-- SIMULATION ONLY: every event classified against the hidden true device.
--   TP = the platform returned an existing visitor and it is the visitor id of that very device
--   FP = the platform returned an existing visitor that belongs to ANOTHER device
--   FN = the platform said "new visitor" although the device had been seen before
--   TN = the platform said "new visitor" and the device was really new
-- Comparing this with int_events_measured shows the bias of the measurement (control set vs all traffic).
select
    e.event_id,
    e.event_date,
    e.customer_id,
    e.browser,
    e.browser_major,
    e.device_type,
    e.method,
    e.is_incognito,
    e.is_bad_bot,
    t.true_is_internal_agent,
    case
        when e.visitor_found and e.visitor_id = t.true_visitor_id then 'TP'
        when e.visitor_found                                      then 'FP'
        when t.device_seen_before                                 then 'FN'
        else 'TN'
    end as truth_outcome
from {{ ref('stg_identification_events') }} e
join {{ ref('stg_device_truth') }} t using (event_id)
