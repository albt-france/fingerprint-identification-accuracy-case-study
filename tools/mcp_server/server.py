"""Read-only MCP server exposing five accuracy tools to any MCP-compatible AI assistant (SIMULATED data).

Every tool goes through tools/accuracy_core.py: whitelisted parameterised queries only (no free SQL), validated
parameters, aggregates only (no event-level rows, no visitor or account ids), row cap, call log.

Run locally over stdio (never deployed by this project):
    python tools/mcp_server/server.py
"""
import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import accuracy_core as core  # noqa: E402

mcp = MCPServer("identification-accuracy-readonly")


def _safe(fn, *args):
    """Return the tool result, or a clean error message for invalid parameters (never a stack trace)."""
    try:
        return fn(*args)
    except core.ToolError as err:
        return {"error": str(err)}


@mcp.tool()
def list_customers() -> list[dict] | dict:
    """List the (fictional) customers and prospects with their sector, use case, CSM pod and confidence threshold."""
    return _safe(core.list_customers)


@mcp.tool()
def accuracy_summary(customer_id: str, start: str, end: str, group_by: str = "none") -> dict:
    """Measured false-positive and false-negative rates of one customer between two ISO dates, with 95% intervals.
    group_by: none, browser, browser_version, device_type or week."""
    return _safe(core.accuracy_summary, customer_id, start, end, group_by)


@mcp.tool()
def is_change_significant(customer_id: str, metric: str, period_a_start: str, period_a_end: str,
                          period_b_start: str, period_b_end: str) -> dict:
    """Is the change of the FP ('fp') or FN ('fn') rate between period A and period B real or noise?"""
    return _safe(core.is_change_significant, customer_id, metric, period_a_start, period_a_end, period_b_start, period_b_end)


@mcp.tool()
def explain_metric(name: str) -> dict:
    """Plain-English definition of an accuracy metric (false_positive, false_negative, control_set, confidence_score...)."""
    return _safe(core.explain_metric, name)


@mcp.tool()
def customer_health(customer_id: str) -> dict:
    """Current accuracy health status (green, amber, red, grey) of a customer, with reasons and the last 4 weeks."""
    return _safe(core.customer_health, customer_id)


if __name__ == "__main__":
    mcp.run()
