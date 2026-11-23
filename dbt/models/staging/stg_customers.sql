select
    customer_id,
    sector,
    use_case,
    plan,
    region,
    csm_pod,
    cast(start_date as date)          as start_date,
    confidence_threshold,
    arr_usd_simulated,
    timezone,
    proxy_integration,
    linked_id_share,
    plan = 'POC'                      as is_prospect
from {{ source('sim', 'customers') }}
