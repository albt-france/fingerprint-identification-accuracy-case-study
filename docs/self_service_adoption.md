# Self-service tools: scope and adoption plan

## Which requests can be self-served

`mart_request_queue.self_service_possible` = standard accuracy questions, trend questions and recurring reports: the
three templates the tools answer without an analyst. Their share of the 140 SIMULATED requests and of analyst hours is
in `findings.json` (`sim.queue.self_service_share`, `self_service_hours_share`). Investigations, custom metrics,
reconciliations and POC readouts stay with the analyst, but start from the same tools.

## The tools

| Tool | For whom | Answers |
|---|---|---|
| `tools/accuracy_cli.py` | CSMs, SEs, analysts | accuracy of a customer over a period (by browser, version, device, week), "is this change real?", definitions, health |
| `tools/health_report.py` | CSMs, for customer calls | one printable page per customer |
| `tools/book_of_business.py` | CSM pods | weekly digest per pod (draft, never sent automatically) |
| `tools/mcp_server/` | anyone using an AI assistant that supports MCP | the same five read-only questions in conversation |

All of them use the same whitelisted, read-only query layer (`tools/accuracy_core.py`).

## Adoption goals (SIMULATED targets for the first quarter)

| Metric | Target |
|---|---|
| Weekly active users of the tools (CS + SE) | 60% of the CSMs and SEs by week 8 |
| Standard questions answered without an analyst | 70% by week 8 |
| Median time to answer a standard question | from about a day (queue) to minutes |
| Health reports used in customer calls | every Enterprise QBR |
| Wrong or misread answers reported | tracked; each one becomes a test or a clearer sentence |

Measured from the tools' call log (`tools/logs/calls.jsonl`: tool, parameters, time; no personal data) and from the queue.

## 4-week launch plan

| Week | Actions |
|---|---|
| 1 | Pilot with 2 CSMs and 1 SE: 30-minute walkthrough, their real questions, collect confusion points. |
| 2 | Fix wording and defaults; add the missing question type; publish a one-page "which tool for which question". |
| 3 | Open to all CS and SE; office hours twice; answer standard queue requests with the tool command + output. |
| 4 | Review the call log and the queue: adoption, unanswered questions, errors; decide the next tool. |

## Feedback to collect

- Which question could the tool not answer? (becomes the backlog)
- Which sentence was misunderstood by a customer? (becomes a template change)
- Did a number differ from another dashboard? (becomes a reconciliation and a test)
