-- CUSTOMER-SPECIFIC metrics built from the customer's own account ids (linkedId), per customer and scope:
--   all                      : every account x visitor pair
--   excl_bad_bots            : pairs seen only through bad-robot traffic removed
--   excl_internal_and_bots   : also removes visitors flagged as internal traffic (int_internal_traffic)
-- accounts per visitor answers "does one visitor id group many of my accounts?" (possible false positives,
-- shared devices, agents); visitors per account answers "is one account split into many visitors?" (possible false
-- negatives, several devices per person, robots).
with pairs as (
    select
        p.*,
        coalesce(i.is_internal_suspected, false) as is_internal
    from {{ ref('int_linked_id_pairs') }} p
    left join {{ ref('int_internal_traffic') }} i using (customer_id, visitor_id)
),
scoped as (
    select 'all' as scope, * from pairs
    union all
    select 'excl_bad_bots', * from pairs where bad_bot_events < events
    union all
    select 'excl_internal_and_bots', * from pairs where bad_bot_events < events and not is_internal
),
per_visitor as (
    select scope, customer_id, visitor_id, count(distinct linked_id) as accounts
    from scoped group by 1, 2, 3
),
per_account as (
    select scope, customer_id, linked_id, count(distinct visitor_id) as visitors
    from scoped group by 1, 2, 3
),
v as (
    select scope, customer_id,
        count(*)                                         as visitors,
        avg(accounts)                                    as accounts_per_visitor_mean,
        quantile_cont(accounts, 0.99)                    as accounts_per_visitor_p99,
        max(accounts)                                    as accounts_per_visitor_max,
        avg(case when accounts > 5 then 1.0 else 0 end)  as share_visitors_over_5_accounts
    from per_visitor group by 1, 2
),
a as (
    select scope, customer_id,
        count(*)                                         as accounts,
        avg(visitors)                                    as visitors_per_account_mean,
        quantile_cont(visitors, 0.99)                    as visitors_per_account_p99,
        max(visitors)                                    as visitors_per_account_max,
        avg(case when visitors > 3 then 1.0 else 0 end)  as share_accounts_over_3_visitors
    from per_account group by 1, 2
)
select v.*, a.accounts, a.visitors_per_account_mean, a.visitors_per_account_p99, a.visitors_per_account_max,
       a.share_accounts_over_3_visitors
from v join a using (scope, customer_id)
