{{ config(severity = 'warn') }}
-- Completeness: every live customer has a partition for every day up to the latest loaded day.
-- Severity warn: a partition arriving late (2026-10-28 was loaded two days late) shows up here until it lands;
-- the incremental lookback window then rebuilds that day automatically.
with days as (
    select cast(d as date) as partition_date
    from (
        select unnest(generate_series(cast('{{ var("window_start") }}' as timestamp),
                                      cast((select max(partition_date) from {{ ref('stg_ingestion_log') }}) as timestamp),
                                      interval 1 day)) as d
    )
),
expected as (
    select days.partition_date, c.customer_id
    from days
    join {{ ref('stg_customers') }} c on days.partition_date >= c.start_date
)
select e.partition_date, e.customer_id
from expected e
left join {{ ref('stg_ingestion_log') }} l on l.partition_date = e.partition_date and l.customer_id = e.customer_id
where l.customer_id is null
