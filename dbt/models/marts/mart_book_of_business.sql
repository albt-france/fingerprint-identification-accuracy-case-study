-- Weekly BOOK-OF-BUSINESS summary per CSM pod: customers, simulated ARR, health statuses, open requests.
-- Feeds tools/book_of_business.py (Markdown / HTML digest, never sent automatically).
with h as (
    select * from {{ ref('mart_customer_health') }}
),
prev as (
    select customer_id, week_start + interval 7 day as week_start, health_status as previous_status
    from h
)
select
    h.csm_pod,
    h.week_start,
    count(*)                                                        as customers,
    {{ count_if('h.is_prospect') }}                                 as prospects,
    sum(h.arr_usd_simulated)                                        as arr_usd_simulated,
    {{ count_if("h.health_status = 'red'") }}                       as red,
    {{ count_if("h.health_status = 'amber'") }}                     as amber,
    {{ count_if("h.health_status = 'green'") }}                     as green,
    {{ count_if("h.health_status = 'grey'") }}                      as grey,
    sum(case when h.health_status in ('red', 'amber') then h.arr_usd_simulated else 0 end) as arr_at_risk_usd_simulated,
    string_agg(case when h.health_status in ('red', 'amber') then h.customer_id end, ', ' order by h.customer_id) as customers_to_watch,
    string_agg(case when p.previous_status is not null and p.previous_status <> h.health_status
                    then h.customer_id || ' ' || p.previous_status || '->' || h.health_status end, ', ' order by h.customer_id) as status_changes,
    sum(h.open_requests)                                            as open_requests
from h
left join prev p using (customer_id, week_start)
group by 1, 2
