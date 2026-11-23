"""Tests of the self-service tools (CLI, health report, book of business) on the built marts."""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
pytestmark = pytest.mark.skipif(not (ROOT / "dbt" / "fingerprint.duckdb").exists(), reason="run dbt build first")

import accuracy_cli  # noqa: E402
import accuracy_core as core  # noqa: E402
import book_of_business  # noqa: E402
import health_report  # noqa: E402


def test_summary_total_matches_mart():
    res = core.accuracy_summary("C07", "2026-10-26", "2026-11-22")
    row = res["rows"][0]
    assert row["fp_rate_ci95"][0] <= row["fp_rate"] <= row["fp_rate_ci95"][1]
    import duckdb
    n = duckdb.connect(str(core.DB), read_only=True).execute(
        "select sum(control_events) from fct_accuracy_daily where customer_id='C07' and event_date between '2026-10-26' and '2026-11-22'").fetchone()[0]
    assert row["control_events"] == n


def test_grouped_summary_adds_up():
    total = core.accuracy_summary("C02", "2026-09-01", "2026-09-30")["rows"][0]["control_events"]
    by_b = core.accuracy_summary("C02", "2026-09-01", "2026-09-30", "browser")["rows"]
    assert sum(r["control_events"] for r in by_b) == total


@pytest.mark.parametrize("bad", ["C13", "X01", "c01; select 1", "", "P03"])
def test_invalid_customer_rejected(bad):
    with pytest.raises(core.ToolError):
        core.check_customer(bad)


def test_dates_outside_window_rejected():
    with pytest.raises(core.ToolError):
        core.accuracy_summary("C01", "2026-01-01", "2026-02-01")
    with pytest.raises(core.ToolError):
        core.accuracy_summary("C01", "2026-10-10", "2026-10-01")


def test_cli_returns_plain_english(capsys):
    assert accuracy_cli.main(["change", "--customer", "C09", "--metric", "fp", "--a", "2026-09-14", "2026-10-11", "--b", "2026-10-12", "2026-11-08"]) == 0
    out = capsys.readouterr().out
    assert "SIMULATED" in out and ("real change" in out or "normal noise" in out)


def test_cli_json_and_error_code(capsys):
    assert accuracy_cli.main(["--json", "health", "--customer", "P01"]) == 0
    assert json.loads(capsys.readouterr().out)["customer_id"] == "P01"
    assert accuracy_cli.main(["health", "--customer", "Z99"]) == 2


def test_health_reports_have_no_identifiers(tmp_path):
    for cid in health_report.EXAMPLES:
        html = health_report.build(cid).read_text(encoding="utf-8")
        assert "SIMULATED" in html and "not affiliated" in html
        assert not re.search(r"\bV[0-9a-f]{12}\b|\bACC\d+|\bIP[0-9a-f]{10}\b", html)


def test_book_of_business_covers_every_pod():
    files = book_of_business.build("2026-11-16")
    assert {f.name.split("_")[1] for f in files} == {"POD-A", "POD-B", "POD-C"}
    md = files[0].with_suffix(".md").read_text(encoding="utf-8")
    assert "not sent automatically" in md
