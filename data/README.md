# Data

Two kinds of data, always labelled: **PUBLIC DATA** (real, public sources) and **SIMULATED** (a fictional
identification platform and fictional customers). No internal Fingerprint data is used or invented.

## Public sources (read on 2026-11-23)

| Source | What | Access | Licence / terms | Used for |
|---|---|---|---|---|
| ClickBench `hits` on the public ClickHouse playground (`play.clickhouse.com`, user `play`, read-only) | ~100M real web-analytics events of July 2013, anonymised in 2019 with `clickhouse-obfuscator` | SQL over HTTPS, aggregates only, 150 queries max, 1 s between queries | ClickBench repository: **CC BY-NC-SA 4.0** (no separate data licence found, so the same terms are applied) | re-identification replay, entropy, anonymity sets, calibration, version roll-out |
| ClickBench Parquet files `hits_0` to `hits_4` (`datasets.clickhouse.com/hits_compatible/athena_partitioned/`) | 5,000,000 rows of the same table | file download, cached locally, **never published** | CC BY-NC-SA 4.0 | dbt models on real data, DuckDB vs ClickHouse reconciliation |
| Chromium Dash `fetch_releases` (Stable, Windows) | Chrome stable builds with dates | JSON API | public Chromium project data | real release dates |
| Mozilla `product-details` (`firefox_history_major_releases.json`) | Firefox major release dates | JSON | Mozilla public data | real release dates |
| endoflife.date API v1 (`products/ios`) | iOS release dates | JSON API | endoflife.date, MIT-licensed project | real release dates |
| Wikimedia Foundation, published datasets: browser shares (`all_sites_by_os_and_browser.tsv`) | weekly page views by OS and browser version, 2015-06-07 to 2026-11-15 | TSV | Wikimedia published datasets, CC0 as stated on the published-datasets page | adoption curves, browser mix |
| Wikimedia Foundation, Analytics API: unique devices (`en.wikipedia.org`, daily) | devices counted without fingerprinting (last-access cookie + offset correction) | REST API | Wikimedia Analytics API terms, CC0 data | a real counting example; real series for the anomaly detector |
| Fingerprint public documentation (`docs.fingerprint.com`) | definitions of accuracy, confidence score, linkedId, MCP server | Markdown pages | quoted briefly with link and date | definitions used everywhere |
| Fingerprint job post (Greenhouse API), careers list, GitHub `fingerprintjs/fingerprintjs` | facts about the role and the open-source library | JSON APIs | public pages | page 1 of the report |

Collection rules: official APIs and files only, one request per second at most, neutral User-Agent
`fingerprint-case-study/1.0`, raw responses cached in `data/raw/` (not published), no account, no form, no call to
Fingerprint's API.

## What is published here

- `processed/`: small aggregates only. The ClickHouse results in `processed/` and in `dbt/seeds/` are **aggregates
  derived from ClickBench** and are shared under **CC BY-NC-SA 4.0** with attribution to the ClickBench project
  (non-commercial use, same licence for derivatives). No visitor-level row of `hits` is published.
- `sample/`: 10,000 SIMULATED events for demonstration (no network hash), the simulated C03 export and a 20,000-pair sample of the simulated C07 export.
- Not published (too large or not ours to redistribute): `raw/`, `sim/`, `cache/`, the DuckDB files.

## Real-data pitfalls (see `docs/data_issues_log.md`)

- Values are **obfuscated**: the most frequent "screen resolution" is not a real resolution. Only **equality** between
  values is meaningful; no value is interpreted.
- Coverage: only **17 of the 30 July days** exist, with very uneven volumes; each site covers a few days. The study
  never plots raw daily counts, only rates.
- The cookie (`UserID`) is the ground truth of the replay, and it is not perfect: a cleared cookie creates a new
  `UserID` for the same device. An upper bound of this effect is computed.
- A site can be cut between two local files: only sites whose local row count equals the ClickHouse count are compared.
- 2013 data from a web-analytics service: **not** Fingerprint data, and far fewer signals than any modern
  identification product. The replay illustrates the **measurement mechanics**, not a level of accuracy.
