-- No mart may contain the same grain twice (an incremental merge gone wrong would show up here first).
select 'fct_accuracy_daily' as model,
       count(*) - count(distinct (event_date, customer_id, browser, browser_major, device_type)) as duplicates
from {{ ref('fct_accuracy_daily') }}
having count(*) <> count(distinct (event_date, customer_id, browser, browser_major, device_type))
union all
select 'fct_accuracy_weekly_customer', count(*) - count(distinct (week_start, customer_id))
from {{ ref('fct_accuracy_weekly_customer') }}
having count(*) <> count(distinct (week_start, customer_id))
union all
select 'mart_customer_health', count(*) - count(distinct (week_start, customer_id))
from {{ ref('mart_customer_health') }}
having count(*) <> count(distinct (week_start, customer_id))
