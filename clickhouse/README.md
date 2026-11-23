# ClickHouse

All SQL in `analyses/` ran on the **public, read-only ClickHouse playground** (`https://play.clickhouse.com/?user=play`,
ClickHouse 26.10.3.7) against `default.hits` (ClickBench, CC BY-NC-SA 4.0), through `src/clickhouse_play.py`:
aggregates only, `FORMAT Parquet`, at least 1 second between queries, every result cached with its SQL, date and duration
in `data/cache/clickhouse/`. Queries sent in total: **34 of the 150 allowed** (3 failed and were
rewritten, never retried as is: memory limit of the playground).

- `analyses/01..10`: the real-data analyses of the report (each file starts with its question, grain and definitions).
- `analyses/11_reconciliation.sql`: the same replay as the dbt model `int_hits_reid`, for the DuckDB vs ClickHouse check.
- `ddl/`: target tables for the marts as they would be created in production (ReplacingMergeTree, SummingMergeTree,
  AggregatingMergeTree with `uniqState`/`uniqMerge`, materialized views). Not executed (read-only playground);
  **syntax checked with `EXPLAIN AST`**, which the playground accepts.

Rerun (uses the cache, sends nothing if the SQL did not change): `python src/clickhouse_play.py --all` and `--ddl`.

| Statement | Rows returned | Seconds (wall-clock, incl. up to 1 s politeness delay) | Run (UTC) |
|---|---:|---:|---|
| `00_schema` | 25 | 0.13 | 2026-11-23 09:19 |
| `01_profile_daily` | 17 | 1.01 | 2026-11-23 09:23 |
| `01_profile_sites` | 6,506 | 0.95 | 2026-11-23 09:23 |
| `01_profile_totals` | 1 | 0.27 | 2026-11-23 09:23 |
| `02_attribute_entropy` | 1 | 1.42 | 2026-11-23 09:23 |
| `03_anon_buckets` | 14 | 0.18 | 2026-11-23 09:23 |
| `03_anon_summary` | 1 | 0.18 | 2026-11-23 09:23 |
| `03_attribute_sets_check` | 1 | 0.98 | 2026-11-23 09:23 |
| `03_fps_per_user_month` | 1 | 1.53 | 2026-11-23 09:23 |
| `04_reid_event_grain` | 30 | 2.27 | 2026-11-23 09:23 |
| `05_reid_day_grain` | 30 | 0.71 | 2026-11-23 09:25 |
| `05_reid_visit_grain` | 30 | 2.06 | 2026-11-23 09:24 |
| `06_reid_tolerant_a` | 75 | 2.07 | 2026-11-23 09:25 |
| `06_reid_tolerant_b` | 75 | 0.63 | 2026-11-23 09:25 |
| `07_bots_effect` | 90 | 2.06 | 2026-11-23 09:24 |
| `08_confidence_calibration` | 10,294 | 2.61 | 2026-11-23 09:24 |
| `09_cookie_churn_bound` | 30 | 2.1 | 2026-11-23 09:24 |
| `10_ua_major_daily` | 546 | 0.22 | 2026-11-23 09:24 |
| `10_upgrade_instability` | 2 | 1.04 | 2026-11-23 09:24 |
| `11_reconciliation` | 134 | 0.4 | 2026-11-23 09:26 |
| `ddl_accuracy_daily` (EXPLAIN AST) | accepted | - | 2026-11-23 10:10 |
| `ddl_accuracy_daily_mv` (EXPLAIN AST) | accepted | - | 2026-11-23 10:10 |
| `ddl_daily_visitors` (EXPLAIN AST) | accepted | - | 2026-11-23 10:10 |
| `ddl_daily_visitors_mv` (EXPLAIN AST) | accepted | - | 2026-11-23 10:11 |
| `ddl_identification_events` (EXPLAIN AST) | accepted | - | 2026-11-23 10:10 |
| `query_monthly_visitors` (EXPLAIN AST) | accepted | - | 2026-11-23 10:11 |
| `superset_ds_accuracy_daily` (EXPLAIN AST) | accepted | - | 2026-11-23 13:04 |
| `superset_ds_book_of_business` (EXPLAIN AST) | accepted | - | 2026-11-23 13:04 |
| `superset_ds_customer_health` (EXPLAIN AST) | accepted | - | 2026-11-23 13:04 |
| `superset_ds_mix_standardized` (EXPLAIN AST) | accepted | - | 2026-11-23 13:04 |
| `superset_ds_request_queue` (EXPLAIN AST) | accepted | - | 2026-11-23 13:04 |

Notes on the design choices: `docs/clickhouse_notes.md`.
