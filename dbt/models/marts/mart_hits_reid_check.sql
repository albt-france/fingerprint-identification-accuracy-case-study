-- CROSS-ENGINE RECONCILIATION (real data): the replay computed by DuckDB here (int_hits_reid) against the same
-- definition run on the ClickHouse playground (clickhouse/analyses/11_reconciliation.sql, cached in a seed).
-- Expected difference: 0 on every site, grain and measure (singular test assert_hits_reid_matches_clickhouse).
select
    coalesce(d.counter_id, c.counter_id)        as counter_id,
    coalesce(d.grain, c.grain)                  as grain,
    d.n      as duckdb_n,      c.n      as clickhouse_n,
    d.users  as duckdb_users,  c.users  as clickhouse_users,
    d.tp_n   as duckdb_tp,     c.tp_n   as clickhouse_tp,
    d.fp_n   as duckdb_fp,     c.fp_n   as clickhouse_fp,
    d.fn_n   as duckdb_fn,     c.fn_n   as clickhouse_fn,
    d.tn_n   as duckdb_tn,     c.tn_n   as clickhouse_tn,
    abs(coalesce(d.n, 0) - coalesce(c.n, 0)) + abs(coalesce(d.users, 0) - coalesce(c.users, 0))
      + abs(coalesce(d.tp_n, 0) - coalesce(c.tp_n, 0)) + abs(coalesce(d.fp_n, 0) - coalesce(c.fp_n, 0))
      + abs(coalesce(d.fn_n, 0) - coalesce(c.fn_n, 0)) + abs(coalesce(d.tn_n, 0) - coalesce(c.tn_n, 0)) as total_abs_diff
from {{ ref('int_hits_reid') }} d
full outer join {{ ref('clickhouse_reid_reference') }} c using (counter_id, grain)
