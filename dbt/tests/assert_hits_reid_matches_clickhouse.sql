-- Cross-engine reconciliation on REAL data: DuckDB and ClickHouse must give identical replay counts.
select *
from {{ ref('mart_hits_reid_check') }}
where total_abs_diff <> 0
