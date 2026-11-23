"""Prefect 3 flow of the whole pipeline, run locally without a Prefect server (ephemeral mode).

    python pipelines/flow.py

Same steps as src/run_all.py: fetch_public -> clickhouse (cache) -> simulate -> dbt build -> monitoring ->
incremental replay -> findings -> tests -> reports -> dashboard -> pdf. Each step is a task with retries for the
network steps only; a failed step stops the flow.
"""
import subprocess
import sys
from pathlib import Path

from prefect import flow, get_run_logger, task

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
DBT = str(Path(PY).parent / "dbt")


def _run(cmd, cwd=ROOT):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(map(str, cmd))} failed:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    return r.stdout[-500:]


@task(retries=2, retry_delay_seconds=30)
def fetch_public():
    return _run([PY, "src/fetch_public.py"])


@task(retries=1, retry_delay_seconds=60)
def clickhouse_cache():
    return _run([PY, "src/clickhouse_play.py", "--all"])


@task
def simulate():
    return _run([PY, "src/simulate_platform.py"])


@task
def dbt_build():
    return _run([DBT, "build", "--profiles-dir", "."], cwd=ROOT / "dbt")


@task
def monitoring():
    return _run([PY, "src/monitoring.py"])


@task
def incremental_replay():
    return _run([PY, "src/incremental_replay.py"])


@task
def findings():
    return _run([PY, "src/findings.py"])


@task
def tests():
    return _run([PY, "-m", "pytest", "-q"])


@task
def reports():
    _run([PY, "tools/health_report.py", "--all-examples"])
    return _run([PY, "tools/book_of_business.py", "--week", "2026-11-16"])


@task
def dashboard():
    return _run([PY, "src/build_dashboard.py"])


@task
def notebook():
    return _run([str(Path(PY).parent / "jupyter"), "nbconvert", "--to", "notebook", "--execute", "--inplace",
                 "notebooks/fingerprint_identification_accuracy.ipynb"])


@task
def pdf():
    _run([PY, "src/build_pdf.py"])
    _run([PY, "src/build_readme.py"])
    return _run([PY, "src/build_dbt_docs.py"])


@flow(name="identification-accuracy-pipeline", log_prints=True)
def pipeline(skip_simulation: bool = False):
    log = get_run_logger()
    fetch_public()
    clickhouse_cache()
    if not skip_simulation:
        simulate()
    dbt_build()
    monitoring()
    incremental_replay()
    findings()
    tests()
    reports()
    dashboard()
    notebook()
    pdf()
    log.info("pipeline finished")


if __name__ == "__main__":
    pipeline(skip_simulation="--skip-simulation" in sys.argv)
