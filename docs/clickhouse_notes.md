# ClickHouse notes

What this project learnt and shows about ClickHouse, the team's analytical warehouse. All analyses ran on the public
read-only playground (ClickHouse 26.10.3.7); the target tables in `clickhouse/ddl/` are written as they would be created
in production (syntax checked where the read-only playground allowed it, see `clickhouse/README.md`).

## Writing efficient event-level SQL

- **Filter on the sorting key.** `default.hits` is sorted by `(CounterID, EventDate, UserID, EventTime, WatchID)`.
  Every replay filters `CounterID IN top` first, so ClickHouse reads only the granules of those sites.
- **Aggregate before you join**: `09_cookie_churn_bound.sql` builds one row per user (`min`/`max` of `EventTime`)
  before joining, instead of joining event rows.
- **Window functions**: `row_number()` and `lagInFrame()` over `PARTITION BY CounterID, fingerprint ORDER BY EventTime, WatchID`.
  `lagInFrame` respects the window frame, so the frame is written explicitly (`ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`).
  `WatchID` breaks ties, so the order (and the result) is deterministic.
- **`countIf`, `uniqExact`, `quantileExact`, `entropy`** keep each query to a single pass.
- **Memory**: the playground caps a query at 18.6 GiB. Two queries hit it; they were rewritten, never retried as is:
  first event per user-day with `GROUP BY ... min((EventTime, WatchID, fingerprint))` instead of a window; five
  fingerprint variants with `ARRAY JOIN` applied **after** filtering visit starts, and the 30 sites split in two.
- **`FORMAT Parquet`** for results: typed, compact, read directly by pandas.

## `uniq` vs `uniqExact`

`uniq` is an adaptive-sampling approximate distinct count: fast and memory-bounded. On the 100M rows it returned
17,578,964 users against 17,630,976 for `uniqExact` (-0.30%, see `findings.json` `real.profile`). Rule used here:
`uniq` for dashboards and trends, `uniqExact` for anything compared with a customer's number or used in a test.

## Table engines for the marts (`clickhouse/ddl/`)

| Need | Engine | Why |
|---|---|---|
| Raw identification events | `MergeTree` partitioned by month, `ORDER BY (customer_id, event_date, visitor_id)` | per-customer reads, cheap pruning |
| Re-sent rows | `ReplacingMergeTree(loaded_at)` keyed on `event_id` | duplicates collapse at merge time; query with `FINAL` or dedupe in the model when exactness matters |
| Daily accuracy facts | `SummingMergeTree` keyed on the grain | counts add up across inserts, so a late partition is just another insert |
| Daily distinct visitors | `AggregatingMergeTree` with `uniqState` / `uniqMerge` | distinct counts cannot be summed; states can be merged across days and customers |
| Feeding the marts | **materialized view** from the raw table | aggregates are maintained at insert time: dashboards read thousands of rows instead of billions |

## dbt on ClickHouse

The dbt project runs on DuckDB here (no local ClickHouse: no Docker or WSL on this machine). Portability is handled
with `adapter.dispatch` macros (`approx_distinct` -> `uniq`, `exact_distinct` -> `uniqExact`, `week_start` -> `toMonday`,
`count_if` -> `countIf`). On ClickHouse the incremental model would use the `delete+insert` strategy (or
`insert_overwrite` by partition) with the same lookback window.
