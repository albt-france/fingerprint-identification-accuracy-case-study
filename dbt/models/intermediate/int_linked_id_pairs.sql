-- Account (linkedId sent by the customer) x visitor pairs: the raw material of customer-specific metrics.
select
    customer_id,
    linked_id,
    visitor_id,
    count(*)                                 as events,
    min(ts_utc)                              as first_seen,
    max(ts_utc)                              as last_seen,
    {{ count_if('is_bad_bot') }}             as bad_bot_events,
    {{ count_if("bot_result in ('bad', 'good') or is_bad_bot") }} as bot_events,
    mode(ip_hash)                            as main_ip_hash
from {{ ref('stg_identification_events') }}
where linked_id is not null
group by 1, 2, 3
