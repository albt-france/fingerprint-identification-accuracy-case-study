# Read-only MCP server: identification accuracy (SIMULATED data)

A [Model Context Protocol](https://modelcontextprotocol.io) server that lets a Customer Success or Sales Engineering
colleague ask accuracy questions in plain language from **any MCP-compatible AI assistant**. The assistant calls five
read-only tools; it never sees raw events.

| Tool | Parameters | Returns |
|---|---|---|
| `list_customers` | none | fictional customers and prospects, sector, use case, CSM pod, confidence threshold |
| `accuracy_summary` | `customer_id`, `start`, `end` (ISO dates), `group_by` (`none`, `browser`, `browser_version`, `device_type`, `week`) | measured FP and FN rates with 95% Wilson intervals, plain-English summary |
| `is_change_significant` | `customer_id`, `metric` (`fp` or `fn`), period A start/end, period B start/end | rates, difference with interval, quasi-binomial test, plain-English verdict |
| `explain_metric` | `name` (e.g. `false_negative`, `control_set`, `confidence_score`) | definition from METRICS.md |
| `customer_health` | `customer_id` | current health status, reasons, last 4 weeks |

## Guard-rails (shared with the CLI in `tools/accuracy_core.py`)

- The DuckDB file is opened **read-only**; only **whitelisted, parameterised** queries exist (no free SQL).
- Every parameter is validated (customer id pattern and existence, ISO dates inside the data window, whitelists).
- Outputs are **aggregates only**: no event-level row, no visitor id, no account id, no network hash. Results capped at 200 rows.
- Every call is logged to `tools/logs/calls.jsonl` (tool, parameters, row count, time) for adoption tracking and audit.
- Invalid parameters return a clean error message, never a stack trace.

## Tests (no language model involved)

`tests/test_mcp_server.py` starts the server in-process with the MCP SDK client and calls the tools directly: the test
plays the role of the assistant. It checks the tool list, aggregates-only outputs (no identifiers), rejection of an
SQL-injection attempt, of out-of-window dates and of non-whitelisted `group_by`, the false-signal case (C04 must not
show a significant change the week C12 goes live) and the call log.

```
python -m pytest tests/test_mcp_server.py -q
```

## How a colleague would connect it (local, stdio)

1. Build the marts once: `cd dbt && dbt build --profiles-dir .`
2. In the MCP settings of their AI assistant, add a local server whose command is the project's Python and whose
   argument is this file, for example:

```json
{
  "mcpServers": {
    "identification-accuracy": {
      "command": "<path to the project>/.venv/Scripts/python.exe",
      "args": ["<path to the project>/tools/mcp_server/server.py"]
    }
  }
}
```

3. Ask, for example: "Is C07's false-positive rate in the last two weeks different from the two weeks before?" The
   assistant calls `is_change_significant` and answers with the numbers and the verdict.

The server is **not deployed** by this project. A shared deployment would add authentication, per-role access to customers
(CSM pods), and would point at the production warehouse through the same whitelisted queries.
