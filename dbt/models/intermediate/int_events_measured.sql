{{ config(materialized='view') }}  -- a view: the incremental mart filters it, so only the lookback days are scanned
-- Fingerprint-style MEASURED accuracy (docs.fingerprint.com/docs/identification-accuracy-and-confidence):
--   control set = events identified deterministically (method = 'deterministic');
--   test set    = the same events re-identified WITHOUT the deterministic signal (probabilistic_visitor_*).
--   TP = the test answer is the same visitor as the control answer
--   FP = the test answer is ANOTHER existing visitor
--   FN = the test answer is "new visitor" although the control answer is an existing visitor
--   TN = both answers say "new visitor"
-- Only control events can be measured this way: incognito traffic (no cookie) never enters this table, which is
-- why the measured accuracy is optimistic when the incognito share grows (see int_events_truth).
select
    event_id,
    event_date,
    customer_id,
    browser,
    browser_major,
    os,
    os_major,
    device_type,
    is_vpn,
    is_bad_bot,
    bot_result,
    case
        when not probabilistic_visitor_found and not visitor_found then 'TN'
        when not probabilistic_visitor_found and visitor_found     then 'FN'
        when probabilistic_visitor_id = visitor_id                 then 'TP'
        else 'FP'
    end as measured_outcome
from {{ ref('stg_identification_events') }}
where is_control
