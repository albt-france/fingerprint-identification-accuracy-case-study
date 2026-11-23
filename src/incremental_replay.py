"""Replays the daily dbt runs around the pipeline incident (SIMULATED event 5) to show what the incremental model
with a 3-day lookback window does with late and re-sent data.

Timeline (UTC): partition 2026-10-27 of C05 is re-sent at 05:40 the next morning (duplicates); partition
2026-10-28 (all customers) lands two days late, on 2026-10-31 at about 02:00.

For each morning run at 06:00 UTC, dbt only sees rows loaded before that time (var as_of) and builds
fct_accuracy_daily incrementally in a separate database (dbt/fingerprint_replay.duckdb). After each run we record
the rows per event day. A NAIVE pipeline (append only days newer than the latest loaded day, no deduplication) is
reconstructed from the same snapshots for comparison.

    python src/incremental_replay.py
"""
import json
import subprocess
import sys
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DBT_DIR = ROOT / "dbt"
REPLAY_DB = DBT_DIR / "fingerprint_replay.duckdb"
DBT = str(Path(sys.executable).parent / "dbt")
RUNS = ["2026-10-26 06:00:00", "2026-10-27 06:00:00", "2026-10-28 06:00:00", "2026-10-29 06:00:00",
        "2026-10-30 06:00:00", "2026-10-31 06:00:00", "2026-11-01 06:00:00", "2026-11-02 06:00:00"]
DAYS = ["2026-10-25", "2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30", "2026-10-31"]


def dbt_run(as_of: str, full_refresh: bool):
    # own target path: the replay must not overwrite target/run_results.json of the main build (read by findings.py)
    cmd = [DBT, "build", "--profiles-dir", ".", "--target", "replay", "--target-path", "target_replay", "--select", "+fct_accuracy_daily",
           "--exclude", "test_type:unit", "--vars", json.dumps({"as_of": as_of})]
    if full_refresh:
        cmd.append("--full-refresh")
    r = subprocess.run(cmd, cwd=DBT_DIR, capture_output=True, text=True)
    status = "ok" if r.returncode == 0 else "failed"
    warns = [l for l in r.stdout.splitlines() if "WARN" in l and " of " in l]
    return status, warns


def main():
    if REPLAY_DB.exists():
        REPLAY_DB.unlink()
    snaps = []
    for i, as_of in enumerate(RUNS):
        status, warns = dbt_run(as_of, full_refresh=(i == 0))
        con = duckdb.connect(str(REPLAY_DB), read_only=True)
        df = con.sql("select cast(event_date as varchar) as event_date, sum(events) as events, sum(control_events) as control_events "
                     "from fct_accuracy_daily group by 1").df()
        con.close()
        df["run_at"] = as_of
        snaps.append(df)
        print(as_of, status, "| warnings:", len(warns))
    snap = pd.concat(snaps)
    # raw rows visible at each run (what a naive pipeline without deduplication would count)
    con = duckdb.connect()
    raw = con.sql("""select cast(cast(ts_utc as date) as varchar) as event_date, loaded_at, count(*) as n
                     from read_parquet('data/sim/identification_events/*/*.parquet', hive_partitioning = true)
                     where cast(ts_utc as date) between date '2026-10-25' and date '2026-10-31'
                     group by 1, 2""").df()
    rows = []
    for as_of in RUNS:
        t = pd.Timestamp(as_of)
        vis = raw[raw["loaded_at"] <= t].groupby("event_date")["n"].sum()
        inc = snap[snap["run_at"] == as_of].set_index("event_date")["events"]
        for d in DAYS:
            rows.append({"run_at": as_of, "event_date": d, "raw_rows_visible": int(vis.get(d, 0)),
                         "incremental_model_events": int(inc.get(d, 0))})
    out = pd.DataFrame(rows)
    # naive pipeline A ("append-only"): each morning, append the days newer than the latest day already loaded,
    # counting raw rows. A day that lands after a newer day was appended is never picked up again.
    naive = {}
    for as_of in RUNS:
        vis = out[out["run_at"] == as_of].set_index("event_date")["raw_rows_visible"]
        latest = max(naive) if naive else None
        for d in DAYS:
            if vis[d] > 0 and (latest is None or d > latest) and d not in naive:
                naive[d] = int(vis[d])
    out["naive_pipeline_events"] = out["event_date"].map(lambda d: naive.get(d, 0))
    # naive chart B: rows charted by LOAD day (the day before the batch landed), duplicates included:
    # a hole on the day the late partition was missing, then a spike when it lands with the next one.
    by_load = raw.assign(report_day=(pd.to_datetime(raw["loaded_at"]).dt.normalize() - pd.Timedelta(days=1)).dt.strftime("%Y-%m-%d"))
    by_load = by_load.groupby("report_day")["n"].sum().rename("rows_by_load_day").reset_index()
    by_load.to_csv(ROOT / "data" / "processed" / "incremental_naive_by_load_day.csv", index=False)
    final = out[out["run_at"] == RUNS[-1]].set_index("event_date")
    full = duckdb.connect(str(DBT_DIR / "fingerprint.duckdb"), read_only=True).sql(
        "select cast(event_date as varchar) as event_date, sum(events) as events from fct_accuracy_daily group by 1").df().set_index("event_date")["events"]
    final_check = {d: {"incremental_after_last_run": int(final.loc[d, "incremental_model_events"]),
                       "full_build": int(full.get(d, 0)),
                       "naive_pipeline": int(naive.get(d, 0))} for d in DAYS}
    out.to_csv(ROOT / "data" / "processed" / "incremental_replay.csv", index=False)
    (ROOT / "data" / "processed" / "incremental_replay_check.json").write_text(json.dumps(final_check, indent=2))
    print(json.dumps(final_check, indent=1))


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    main()
