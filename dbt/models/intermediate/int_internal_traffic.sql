-- Suspected INTERNAL traffic (support or call-centre agents logging into customer accounts).
-- Rule (written in METRICS.md): a visitor linked to >= 20 distinct accounts over the window, whose main network
-- (ip_hash) is shared by >= 5 such visitors. A household device (2-4 accounts) never reaches the threshold;
-- a false positive merging two people adds 1-2 accounts, not dozens. Visitors whose linked requests are mostly
-- robots (bot_result good or bad) are robot traffic, not staff: they are left out of the rule and reported apart.
with per_visitor as (
    select
        customer_id,
        visitor_id,
        count(distinct linked_id)                  as accounts,
        sum(events)                                as events,
        sum(bad_bot_events)                        as bad_bot_events,
        sum(bot_events)                            as bot_events,
        mode(main_ip_hash)                         as main_ip_hash
    from {{ ref('int_linked_id_pairs') }}
    group by 1, 2
),
candidates as (
    select *, accounts >= 20 and bot_events * 1.0 / events < 0.5 as many_accounts from per_visitor
),
networks as (
    select customer_id, main_ip_hash, {{ count_if('many_accounts') }} as heavy_visitors_on_network
    from candidates
    group by 1, 2
)
select
    c.customer_id,
    c.visitor_id,
    c.accounts,
    c.events,
    c.bad_bot_events,
    c.bot_events,
    c.main_ip_hash,
    n.heavy_visitors_on_network,
    c.many_accounts and n.heavy_visitors_on_network >= 5 as is_internal_suspected
from candidates c
join networks n using (customer_id, main_ip_hash)
