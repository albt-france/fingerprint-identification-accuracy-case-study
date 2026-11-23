"""Tests of the read-only MCP server with the SDK's in-process client. No language model is involved: the test
plays the role of the AI assistant and calls the tools directly."""
import asyncio
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "mcp_server"))
sys.path.insert(0, str(ROOT / "tools"))

pytestmark = pytest.mark.skipif(not (ROOT / "dbt" / "fingerprint.duckdb").exists(), reason="run dbt build first")

from mcp import Client  # noqa: E402

import server  # noqa: E402

VISITOR_RE = re.compile(r"\bV[0-9a-f]{12}\b")
ACCOUNT_RE = re.compile(r"\bACC\d+")
IP_RE = re.compile(r"\bIP[0-9a-f]{10}\b")


def call(name, args=None):
    async def run():
        async with Client(server.mcp) as client:
            res = await client.call_tool(name, args or {})
            text = "".join(getattr(c, "text", "") for c in res.content)
            return res, text
    return asyncio.run(run())


def payload(res, text):
    if res.structured_content is not None:
        sc = res.structured_content
        return sc.get("result", sc) if isinstance(sc, dict) else sc
    return json.loads(text)


def test_exactly_five_tools_listed():
    async def run():
        async with Client(server.mcp) as client:
            return await client.list_tools()
    tools = asyncio.run(run())
    names = sorted(t.name for t in tools.tools)
    assert names == sorted(["list_customers", "accuracy_summary", "is_change_significant", "explain_metric", "customer_health"])


def test_list_customers():
    res, text = call("list_customers")
    data = payload(res, text)
    assert len(data) == 14 and {"C01", "P02"} <= {r["customer_id"] for r in data}


def test_accuracy_summary_returns_aggregates_only():
    res, text = call("accuracy_summary", {"customer_id": "C07", "start": "2026-10-26", "end": "2026-11-22", "group_by": "browser"})
    data = payload(res, text)
    assert data["label"].startswith("SIMULATED")
    assert 0 < len(data["rows"]) <= 200
    assert all(0 <= r["fp_rate"] <= 1 for r in data["rows"])
    assert not VISITOR_RE.search(text) and not ACCOUNT_RE.search(text) and not IP_RE.search(text)


def test_change_significance_flags_the_false_signal_correctly():
    # C04 is a stable customer: the week C12 goes live must NOT look like a change for C04
    res, text = call("is_change_significant", {"customer_id": "C04", "metric": "fp", "period_a_start": "2026-10-05", "period_a_end": "2026-10-18",
                                               "period_b_start": "2026-10-19", "period_b_end": "2026-11-01"})
    data = payload(res, text)
    assert data["significant_at_1pct"] is False


def test_sql_injection_and_bad_parameters_are_rejected():
    for args in [{"customer_id": "C01'; drop table x; --", "start": "2026-09-01", "end": "2026-09-30"},
                 {"customer_id": "C01", "start": "2020-01-01", "end": "2026-09-30"},
                 {"customer_id": "C01", "start": "2026-09-01", "end": "2026-09-30", "group_by": "visitor_id"}]:
        res, text = call("accuracy_summary", args)
        data = payload(res, text)
        assert "error" in data


def test_explain_and_health():
    res, text = call("explain_metric", {"name": "false negative"})
    assert "NEW" in payload(res, text)["definition"]
    res, text = call("customer_health", {"customer_id": "P01"})
    h = payload(res, text)
    assert h["current"]["status"] in {"green", "amber", "red", "grey"}
    assert len(h["last_4_weeks"]) <= 4


def test_calls_are_logged():
    log = ROOT / "tools" / "logs" / "calls.jsonl"
    before = log.read_text(encoding="utf-8").count("\n") if log.exists() else 0
    call("explain_metric", {"name": "control_set"})
    assert log.read_text(encoding="utf-8").count("\n") == before + 1
