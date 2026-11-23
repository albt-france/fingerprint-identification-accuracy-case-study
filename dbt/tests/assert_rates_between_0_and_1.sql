-- Every published rate is a proportion: between 0 and 1 (or NULL when the denominator is 0).
select 'weekly' as model, customer_id as id, week_start
from {{ ref('fct_accuracy_weekly_customer') }}
where fp_rate not between 0 and 1 or fn_rate not between 0 and 1
   or fp_rate_lo not between 0 and 1 or fp_rate_hi not between 0 and 1
   or incognito_share not between 0 and 1 or bad_bot_share not between 0 and 1
union all
select 'mix', 'platform', week_start
from {{ ref('mart_mix_standardized') }}
where fp_rate_crude not between 0 and 1 or fp_rate_standardized not between 0 and 1 or fp_rate_stable_cohort not between 0 and 1
