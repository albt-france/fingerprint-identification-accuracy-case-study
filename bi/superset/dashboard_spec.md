# Superset dashboard specification: "Identification accuracy"

> Built on the **SIMULATED** marts of this case study (dbt). The same views are rendered offline in
> `dashboard/index.html`, the visual reference for this spec. Every chart title starts with **SIMULATED**; the dashboard
> description carries "Independent case study · fictional platform and customers · not Fingerprint data".

## 1. Databases and datasets

- **Production target**: ClickHouse (Preset or self-hosted Superset), datasets in `datasets/clickhouse/` (syntax checked
  with `EXPLAIN AST` on the public playground).
- **This repository**: DuckDB (`dbt/fingerprint.duckdb`, opened **read-only** through `duckdb-engine`), datasets in `datasets/duckdb/`.

| Dataset | Grain | Main columns |
|---|---|---|
| `ds_accuracy_daily` | day x customer x browser x major x device type | control_events, tp, fp, fn, tn, events, bad_bot_events, incognito_events, below_threshold_events |
| `ds_customer_health` | week x customer | health_status, health_reasons, fp/fn rates with Wilson bounds, z-scores, shares |
| `ds_mix_standardized` | week | crude, constant-mix and stable-cohort FP and FN rates |
| `ds_book_of_business` | week x CSM pod | customers, ARR, statuses, ARR at risk, customers to watch |
| `ds_request_queue` | request | priority tier, SLA, hours to resolve, self-service flag |

**Saved metrics** (defined once on the dataset, reused everywhere): `fp_rate = SUM(fp) / NULLIF(SUM(control_events), 0)`,
`fn_rate = SUM(fn) / NULLIF(SUM(control_events), 0)`, `bad_bot_share = SUM(bad_bot_events) / NULLIF(SUM(events), 0)`,
`step_up_share = SUM(below_threshold_events) / NULLIF(SUM(found_events), 0)`, `self_service_share = AVG(CASE WHEN self_service_possible THEN 1 ELSE 0 END)`.
Rates are always ratios of sums, never averages of daily rates.

## 2. Tabs and charts

| Tab | Chart | Type | Dataset | Metric / dimension | Question |
|---|---|---|---|---|---|
| Accuracy monitor | Platform FP rate, three readings | Line, 3 series | ds_mix_standardized | crude, constant mix, stable cohort | Is it the model or the mix? |
| | FP / FN by browser version | Line, one series per major | ds_accuracy_daily | fp_rate, fn_rate by browser_major, filter browser | Did a new version drift? |
| | Version age | Bar | ds_accuracy_daily | fn_rate by version_age_bucket | Are new versions worse? |
| Customer health | Status heatmap | Heatmap customer x week | ds_customer_health | health_status | Who needs attention? |
| | Status table | Table, conditional colour | ds_customer_health | latest week, reasons | Why? |
| | FP rate with interval | Line + band (Mixed chart) | ds_customer_health | fp_rate, fp_rate_lo, fp_rate_hi | Real change or noise? |
| Book of business | ARR at risk by pod | Bar | ds_book_of_business | arr_at_risk_usd_simulated | Where is the money at risk? |
| | Pod table | Table | ds_book_of_business | latest week | What do I say in the pod meeting? |
| Request queue | Requests by tier and team | Stacked bar | ds_request_queue | count | What is the load? |
| | Time to resolve | Box plot by tier | ds_request_queue | hours_to_resolve | Do we meet targets? |
| | Self-service share | Big number + trend | ds_request_queue | self_service_share by week_opened | Is adoption working? |

## 3. Native filters

Date range (default last 13 weeks), customer_id, csm_pod, browser, device_type, priority_tier. Cross-filtering from the
status heatmap to every chart of the Customer health tab.

## 4. Access (roles)

| Role | Access |
|---|---|
| Identification Accuracy analysts | all tabs, SQL Lab on the marts |
| Customer Success | Customer health, Book of business (row-level security: own pod only), read-only |
| Sales Engineering | Customer health filtered to prospects (`is_prospect`), Accuracy monitor read-only |
| Product, Engineering | Accuracy monitor, Request queue |
| Everyone | no event-level dataset; no visitor, account or network identifiers in any dataset |

## 5. Refresh and caching

dbt runs after the daily load (06:00 UTC); dataset cache timeout 6 hours; the monitor tab is refreshed after each dbt run.
A dashboard annotation layer marks customer go-lives and model releases (from `stg_model_releases`).

## 6. Alerts and reports for on-call (Superset Alerts & Reports)

| Alert / report | Condition | Recipient | Frequency |
|---|---|---|---|
| Standardized FP rate | `fp_rate_standardized` of the current week > 1.2 x the mean of the previous 4 weeks | accuracy on-call channel | daily 07:00 UTC |
| Customer turns red | any `health_status = 'red'` in the latest week | CSM pod channel + analyst | daily |
| Bad-robot share | `bad_bot_share` of a customer > 10% yesterday | CSM / SE of the customer | daily |
| Weekly book of business | PDF of the Book of business tab per pod | CSM pods | Monday 08:00 (local) |

The statistical alerting (exact tests, Benjamini-Hochberg, 2-day persistence) stays in `src/monitoring.py`: Superset alerts
are simple threshold checks and serve as a safety net.

## 7. Installation attempt (this repository)

See the README section "Superset": one attempt on Windows (not an officially supported platform), in a separate
virtual environment, with a local admin whose random password is stored only in `.env`.
