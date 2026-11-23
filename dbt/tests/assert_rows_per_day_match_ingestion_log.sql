-- After deduplication, the rows of each day and customer must equal what the source system says it sent.
-- (Catches lost rows, double loads that survive deduplication, and partitions dropped by mistake.)
with ours as (
    select event_date as partition_date, customer_id, count(*) as rows_in_staging
    from {{ ref('stg_identification_events') }}
    group by 1, 2
),
log as (
    select partition_date, customer_id, max(rows_sent) as rows_sent
    from {{ ref('stg_ingestion_log') }}
    group by 1, 2
)
select coalesce(o.partition_date, l.partition_date) as partition_date,
       coalesce(o.customer_id, l.customer_id) as customer_id,
       o.rows_in_staging, l.rows_sent
from ours o
full outer join log l on o.partition_date = l.partition_date and o.customer_id = l.customer_id
where coalesce(o.rows_in_staging, -1) <> coalesce(l.rows_sent, -1)
