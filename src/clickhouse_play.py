"""Polite client for the public, read-only ClickHouse playground (play.clickhouse.com, user 'play').

Rules applied here (see clickhouse/README.md):
- aggregates only, never visitor-level rows;
- at most 150 queries in total for the whole study (counted in data/cache/clickhouse/_log.jsonl);
- at least 1 second between two queries (polite.post);
- every result cached with its SQL text, run date and duration, so later runs never hit the network.

Usage:
    python src/clickhouse_play.py clickhouse/analyses/01_profile.sql      # run every statement of a file
    python src/clickhouse_play.py --all                                   # run all analyses (cache first)
"""
import datetime as dt
import hashlib
import io
import json
import re
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from polite import post  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / "clickhouse"
LOG = CACHE / "_log.jsonl"
URL = "https://play.clickhouse.com/?user=play"
MAX_QUERIES = 150


def queries_used() -> int:
    if not LOG.exists():
        return 0
    return sum(1 for line in LOG.read_text(encoding="utf-8").splitlines() if line.strip())


def run(name: str, sql: str, force: bool = False) -> pd.DataFrame:
    """Return the result of `sql` as a DataFrame, from cache when available.

    `name` is the cache key (e.g. '04_reid_event_grain'). The SQL hash is stored too: if the SQL text changes,
    the query is re-run (and counted)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    sql = sql.strip().rstrip(";")
    h = hashlib.sha1(sql.encode()).hexdigest()[:12]
    pq, meta = CACHE / f"{name}.parquet", CACHE / f"{name}.json"
    if not force and pq.exists() and meta.exists() and json.loads(meta.read_text())["sql_sha1"] == h:
        return pd.read_parquet(pq)
    if queries_used() >= MAX_QUERIES:
        raise RuntimeError("Query budget of 150 reached: rewrite or reuse the cache.")
    t0 = time.time()
    r = post(URL, (sql + "\nFORMAT Parquet").encode())
    secs = round(time.time() - t0, 2)
    status = getattr(r, "status_code", None)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"name": name, "sql_sha1": h, "status": status, "seconds": secs,
                            "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}) + "\n")
    if r is None or status != 200:
        msg = r.text[:400] if r is not None else "no response"
        raise RuntimeError(f"[{name}] HTTP {status}: {msg}")
    df = pd.read_parquet(io.BytesIO(r.content))
    df.to_parquet(pq, index=False)
    meta.write_text(json.dumps({"name": name, "sql_sha1": h, "sql": sql, "seconds": secs, "rows": len(df),
                                "run_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                                "server": "play.clickhouse.com"}, indent=2))
    print(f"[ran] {name}: {len(df)} rows in {secs}s (budget used {queries_used()}/{MAX_QUERIES})")
    return df


def explain_ast(name: str, sql: str) -> dict:
    """Syntax check of a DDL statement with EXPLAIN AST (parses, never executes). Cached like any other query."""
    CACHE.mkdir(parents=True, exist_ok=True)
    sql = sql.strip().rstrip(";")
    h = hashlib.sha1(sql.encode()).hexdigest()[:12]
    meta = CACHE / f"{name}.json"
    if meta.exists() and json.loads(meta.read_text())["sql_sha1"] == h:
        return json.loads(meta.read_text())
    if queries_used() >= MAX_QUERIES:
        raise RuntimeError("Query budget of 150 reached.")
    r = post(URL, ("EXPLAIN AST " + sql + chr(10) + "FORMAT TabSeparatedRaw").encode())
    status = getattr(r, "status_code", None)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"name": name, "sql_sha1": h, "status": status, "seconds": None,
                            "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}) + chr(10))
    res = {"name": name, "sql_sha1": h, "sql": sql, "http_status": status, "accepted": status == 200,
           "ast_lines": len(r.text.splitlines()) if status == 200 else 0,
           "error": None if status == 200 else (r.text[:300] if r is not None else "no response"),
           "run_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    meta.write_text(json.dumps(res, indent=2))
    return res


def write_dbt_seeds():
    """dbt seeds derived from cached playground results (aggregates, CC BY-NC-SA 4.0): site row counts and the
    replay reference used by the DuckDB vs ClickHouse reconciliation test."""
    seeds = ROOT / "dbt" / "seeds"
    pd.read_parquet(CACHE / "01_profile_sites.parquet")[["CounterID", "events"]].rename(columns={"CounterID": "counter_id"})         .to_csv(seeds / "clickhouse_site_counts.csv", index=False)
    pd.read_parquet(CACHE / "11_reconciliation.parquet").rename(columns={"CounterID": "counter_id"})         .to_csv(seeds / "clickhouse_reid_reference.csv", index=False)


def split_file(path: Path) -> list[tuple[str, str]]:
    """A .sql file holds one or more statements, each preceded by a line `-- name: <key>`."""
    text = path.read_text(encoding="utf-8")
    parts = re.split(r"^-- name:\s*(\S+)\s*$", text, flags=re.M)
    out = []
    for i in range(1, len(parts), 2):
        body = parts[i + 1].strip()
        if body:
            out.append((parts[i], body))
    return out


def run_file(path: Path, force: bool = False) -> dict:
    return {name: run(name, sql, force) for name, sql in split_file(path)}


if __name__ == "__main__":
    if "--ddl" in sys.argv:
        for f in sorted((ROOT / "clickhouse" / "ddl").glob("*.sql")):
            for name, sql in split_file(f):
                r = explain_ast(name, sql)
                print(name, "accepted" if r["accepted"] else f"REJECTED: {r['error'][:200]}")
        sys.exit(0)
    files = sorted((ROOT / "clickhouse" / "analyses").glob("*.sql")) if "--all" in sys.argv else [Path(a) for a in sys.argv[1:] if not a.startswith("--")]
    for f in files:
        for k, v in run_file(f, force="--force" in sys.argv).items():
            print(k, v.shape)
    if "--all" in sys.argv:
        write_dbt_seeds()
    print("budget used:", queries_used())
