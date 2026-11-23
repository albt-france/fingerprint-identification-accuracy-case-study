"""Run the whole pipeline in order, with a log (fallback for the Prefect flow in pipelines/flow.py; same steps).

    python src/run_all.py                 # everything (ClickHouse and public data come from the cache when present)
    python src/run_all.py --from findings # resume from a step
"""
import datetime as dt
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
DBT = str(Path(PY).parent / "dbt")
LOG = ROOT / "data" / "cache" / "run_all.log"

STEPS = [
    ("fetch_public", [PY, "src/fetch_public.py"], ROOT),
    ("clickhouse", [PY, "src/clickhouse_play.py", "--all"], ROOT),
    ("simulate", [PY, "src/simulate_platform.py"], ROOT),
    ("dbt_build", [DBT, "build", "--profiles-dir", "."], ROOT / "dbt"),
    ("monitoring", [PY, "src/monitoring.py"], ROOT),
    ("incremental_replay", [PY, "src/incremental_replay.py"], ROOT),
    ("findings", [PY, "src/findings.py"], ROOT),
    ("tests", [PY, "-m", "pytest", "-q"], ROOT),
    ("reports", [PY, "tools/health_report.py", "--all-examples"], ROOT),
    ("book_of_business", [PY, "tools/book_of_business.py", "--week", "2026-11-16"], ROOT),
    ("dashboard", [PY, "src/build_dashboard.py"], ROOT),
    ("notebook", [str(Path(PY).parent / "jupyter"), "nbconvert", "--to", "notebook", "--execute", "--inplace",
                  "notebooks/fingerprint_identification_accuracy.ipynb"], ROOT),
    ("pdf", [PY, "src/build_pdf.py"], ROOT),
    ("readme", [PY, "src/build_readme.py"], ROOT),
    ("dbt_docs", [PY, "src/build_dbt_docs.py"], ROOT),
]


def run_step(name, cmd, cwd) -> bool:
    t0 = dt.datetime.now()
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    secs = (dt.datetime.now() - t0).total_seconds()
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{t0:%Y-%m-%d %H:%M:%S} {name:<20} exit={r.returncode} {secs:7.1f}s\n")
        if r.returncode != 0:
            f.write(r.stdout[-3000:] + r.stderr[-3000:] + "\n")
    print(f"{name:<20} {'ok' if r.returncode == 0 else 'FAILED'} ({secs:.0f}s)")
    return r.returncode == 0


def main():
    LOG.parent.mkdir(parents=True, exist_ok=True)
    start = sys.argv[sys.argv.index("--from") + 1] if "--from" in sys.argv else STEPS[0][0]
    names = [s[0] for s in STEPS]
    for name, cmd, cwd in STEPS[names.index(start):]:
        if not run_step(name, cmd, cwd):
            print(f"stopped at {name}: see {LOG.relative_to(ROOT)}")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
