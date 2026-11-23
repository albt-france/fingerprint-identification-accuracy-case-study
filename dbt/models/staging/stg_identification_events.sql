{{ config(materialized='table') }}
-- One row per identification request, deduplicated.
-- * Only rows loaded at or before var('as_of') are visible (lets src/incremental_replay.py replay daily runs).
-- * Re-sent batches duplicate event_id (C05, 2026-10-27): keep the FIRST load of each event_id.
-- * Timestamps are UTC; event_date is the UTC day (customers often report in local time: see the C03 playbook).
with src as (
    select *
    from {{ source('sim', 'identification_events') }}
    where loaded_at <= cast('{{ var("as_of") }}' as timestamp)
)
select
    event_id,
    ts_utc,
    cast(ts_utc as date)                       as event_date,
    customer_id,
    visitor_id,
    visitor_found,
    confidence_score,
    method,
    method = 'deterministic'                   as is_control,        -- control set of the accuracy experiment
    probabilistic_visitor_id,
    probabilistic_visitor_found,
    browser,
    browser_major,
    os,
    os_major,
    device_type,
    is_incognito,
    is_vpn,
    bot_result,
    bot_result = 'bad'                         as is_bad_bot,
    ip_hash,
    country,
    sdk,
    sdk_version,
    proxy_integration,
    linked_id,
    loaded_at
from src
qualify row_number() over (partition by event_id order by loaded_at) = 1
