# Request triage: impact x urgency

Requests reach the accuracy analyst from Customer Success (CS), Sales Engineering (SE) and Product. The queue is
modelled in `mart_request_queue` (140 SIMULATED requests over 13 weeks).

## Scoring

| Impact (1-4) | Rule |
|---|---|
| 4 | customer with simulated ARR >= $400k |
| 3 | ARR $250k-$400k, **or** a POC prospect (pipeline at stake), **or** a platform-wide question (e.g. the global dashboard) |
| 2 | ARR $100k-$250k |
| 1 | ARR < $100k |

| Urgency (1-4) | Rule (declared by the requester, checked at triage) |
|---|---|
| 4 critical | customer escalation, POC decision this week, possible incident |
| 3 high | customer meeting within days, visible customer impact |
| 2 medium | question with a date, no visible impact |
| 1 low | curiosity, documentation, nice to have |

**Priority = impact x urgency** (1-16): **P1 >= 12**, **P2 >= 6**, **P3 >= 3**, **P4** otherwise.
Resolution targets (calendar time, first answer much sooner): P1 2 days, P2 5 days, P3 10 days, P4 20 days. A P1 gets a first answer the same day.

## Rules of thumb

- A suspected incident goes to the on-call process, not the queue.
- Standard questions (accuracy of a customer over a period, trend, report) are pointed to the **self-service tools**
  first; the analyst reviews the answer if asked.
- Three similar requests in a month = build or extend a tool (that is how the CLI, health report and MCP server were scoped).
- Batch P3 / P4 requests in two weekly slots; protect time for P1 / P2.

## Applied to the 140 requests

The tier counts, resolution times by tier, share resolved within target and the share of requests a self-service tool
could have answered are generated from `mart_request_queue` into `findings.json` (`sim.queue`) and shown on the
dashboard (Request queue tab) and in the report (page 10).
