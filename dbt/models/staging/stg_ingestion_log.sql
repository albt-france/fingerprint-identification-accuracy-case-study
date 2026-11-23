select
    cast(partition_date as date)  as partition_date,
    customer_id,
    rows_sent,
    rows_loaded,
    loaded_at
from {{ source('sim', 'ingestion_log') }}
where loaded_at <= cast('{{ var("as_of") }}' as timestamp)
