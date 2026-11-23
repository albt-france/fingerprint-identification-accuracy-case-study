{{ config(severity = 'warn') }}
-- RAW files vs rows sent by the source: a mismatch means re-sent (duplicated) or missing rows in the landing zone.
-- Severity warn: the known incident (C05, 2026-10-27, rows re-sent after an upstream error) is caught here and
-- handled by the deduplication in stg_identification_events (the error-level test on staging then passes).
with raw as (
    select cast(ts_utc as date) as partition_date, customer_id, count(*) as raw_rows
    from {{ source('sim', 'identification_events') }}
    where loaded_at <= cast('{{ var("as_of") }}' as timestamp)
    group by 1, 2
)
select r.partition_date, r.customer_id, r.raw_rows, l.rows_sent, r.raw_rows - l.rows_sent as extra_rows
from raw r
join {{ ref('stg_ingestion_log') }} l on r.partition_date = l.partition_date and r.customer_id = l.customer_id
where r.raw_rows <> l.rows_sent
