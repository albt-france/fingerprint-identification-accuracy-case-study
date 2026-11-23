-- REAL DATA: the re-identification replay of clickhouse/analyses/11_reconciliation.sql, recomputed in DuckDB on the
-- local Parquet copy. Only sites whose rows are ALL in the local files (local count = ClickHouse count) are kept:
-- a site cut between files would give different histories in the two engines.
-- Fingerprint = the tuple of the 16 attribute columns (no hash: DuckDB has no cityHash64).
with local_counts as (
    select CounterID as counter_id, count(*) as local_rows
    from {{ source('public', 'hits') }}
    group by 1
),
full_sites as (
    select l.counter_id
    from local_counts l
    join {{ ref('clickhouse_site_counts') }} c on c.counter_id = l.counter_id
    where l.local_rows = c.events
),
base as (
    select
        h.*,
        row_number() over (partition by counter_id, user_id order by event_time_s, watch_id) as user_rn,
        lag(event_time_s) over (partition by counter_id, user_id order by event_time_s, watch_id) as prev_t
    from {{ ref('stg_hits') }} h
    where counter_id in (select counter_id from full_sites)
),
grains as (
    -- event grain = every row; visit grain = first row of a user after 30 minutes of inactivity
    select *, 'event' as grain from base
    union all
    select *, 'visit' as grain from base where user_rn = 1 or event_time_s - prev_t > 1800
),
replay as (
    select
        counter_id, grain, user_id,
        row_number() over w_fp                         as fp_seq,
        lag(user_id) over w_fp                         as prev_user,
        row_number() over (partition by counter_id, grain, user_id order by event_time_s, watch_id) as user_seq
    from grains
    window w_fp as (partition by counter_id, grain, OS, UserAgent, UserAgentMajor, UserAgentMinor, ResolutionWidth,
                    ResolutionHeight, ResolutionDepth, ClientTimeZone, BrowserLanguage, BrowserCountry, JavaEnable,
                    CookieEnable, FlashMajor, FlashMinor, SilverlightVersion1, MobilePhoneModel
                    order by event_time_s, watch_id)
)
select
    counter_id,
    grain,
    count(*)                                               as n,
    count(distinct user_id)                                as users,
    {{ count_if('fp_seq > 1 and prev_user = user_id') }}   as tp_n,
    {{ count_if('fp_seq > 1 and prev_user <> user_id') }}  as fp_n,
    {{ count_if('fp_seq = 1 and user_seq > 1') }}          as fn_n,
    {{ count_if('fp_seq = 1 and user_seq = 1') }}          as tn_n
from replay
group by 1, 2
