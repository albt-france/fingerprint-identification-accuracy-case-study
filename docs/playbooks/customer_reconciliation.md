# Playbook: reconciling our numbers with a customer's analysis

**Trigger**: "your dashboard says X, our analysis says Y" (volumes, visitors, error rates, billed identifications).

**Principle**: never argue about who is right. Build a **bridge**: start from their number, explain each difference
with a named, measured step, and end on ours. Whatever is left unexplained is reported as a residual.

## 1. Questions to ask (before any query)

1. Exact definition of their metric (sessions? page views? logins? unique users?) and the query or export.
2. Time zone and day boundaries of their report; date range.
3. Do they count requests whose identification failed or was blocked (ad blockers)? Do they use a proxy integration?
4. Filters: robots, internal traffic, test environments, specific apps.
5. Can they share a daily (better: hourly) export with a column telling whether a visitor id came back?

## 2. Usual causes, in the order to check them

| Step | Check |
|---|---|
| Definition | their "session" vs our identification request; several requests per session? |
| Blocked requests | without a proxy integration, ad blockers block part of the identification requests: those never reach us (look at sessions without a visitor id in their export) |
| Time zone | their local day vs our UTC day; daylight-saving changes shift one hour twice a year |
| Duplicates | page reloads or retries counted twice on their side, or re-sent rows on ours (dbt tests) |
| Late data | a partition loaded late on our side (freshness test, incremental lookback) |
| Filters | robots, internal traffic, test traffic excluded on one side only |

## 3. Worked example (SIMULATED): C03, "our session count is far above your billed identifications"

Generated bridge for October 2026 (`docs/generated/c03_bridge.md`, numbers from `findings.json` `sim.e4`):
their sessions (local days) -> minus sessions with no visitor id (blocked: no proxy integration) -> minus a small
duplicate residual -> our events on the same local days -> time-zone shift -> billed events on UTC days.
Daily comparisons are noisier than the monthly bridge because the local / UTC day boundary moves events between
adjacent days (and by one more hour after the 2026-11-01 daylight-saving change).

**Recommendation to the customer**: set up the proxy integration (fewer blocked requests, so more of their sessions get
a visitor id) and compare on UTC days or with our local-time export.

## 4. Message template

> We reconciled your October numbers with ours step by step (table attached). 9 in 100 of your sessions never reached
> us because the identification request was blocked by ad blockers: a proxy integration would recover most of them.
> The rest is a time-zone effect (your report uses New York days, ours UTC) and a tiny residual we could not attribute
> (0.16%). Billing only counts the requests that reached us.
