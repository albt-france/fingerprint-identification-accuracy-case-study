# On-call runbook: identification accuracy

Roles, not names. Schedule shared and published in advance; one primary analyst, one secondary, an engineering
on-call for the identification models, and the CSM of the customer when a customer is affected.

## Alerts

| Alert | Source | Threshold | Severity |
|---|---|---|---|
| Platform segment (browser x version) FP or FN up | `src/monitoring.py` | 2-day pooled exact test, phi-adjusted, BH FDR 1%, both days above reference | **SEV-2**; SEV-1 if several large segments or > 3x the reference |
| Customer segment FP or FN up | same | same | SEV-3 (SEV-2 for Enterprise customers or POCs in their last week) |
| Global crude rate above the p'-chart limit **without** a standardized-rate signal | `monitoring_pchart.csv` | Laney p' limits | **no page**: dashboard annotation (mix change) |
| Standardized rate above its limit or CUSUM > 5 | same | | SEV-2 |
| Bad-robot share | robot monitor | > 3 sd above the customer's 28-day median and > 2x and > 8% | SEV-3 (inform CSM / SE) |
| Next-morning row count | volume monitor | +-25% vs the same weekday of the last 4 weeks | SEV-3 (data team) |
| dbt test failure (error) | `dbt build` | any | SEV-2: dashboards on hold |
| dbt test warning | `dbt build` | known incident patterns (duplicates, late partition) | ticket |

Back-test on the 13 simulated weeks (`findings.json` `monitoring`): every hidden accuracy, robot and pipeline event was
caught; the false signal of the week of 2026-10-19 did not page anyone; the number of false alerts per week is the
on-call load figure to watch.

## First moves (in order)

1. Acknowledge in the alert channel; open the incident note from the template below.
2. Check data completeness: dbt results, freshness, row counts. If the data is incomplete, stop: it is a pipeline incident.
3. Run the triage (`docs/playbooks/anomaly_triage.md`): model, mix or measurement?
4. Size it: segment, customers affected, events affected, simulated ARR concerned.
5. If the model or a browser release is the cause: page the engineering on-call with the evidence pack (segment,
   start time, release calendar, rates with intervals, example volumes).
6. Tell the CSMs of affected customers **before** the customers notice; send the customer explainer if needed.

## When to wake whom

| Situation | Who | When |
|---|---|---|
| SEV-1: platform-wide accuracy regression on a large segment | engineering on-call + accuracy lead | immediately, any hour |
| SEV-2: one platform segment, or an Enterprise customer | engineering on-call | within business hours of the on-call region; immediately if a strategic customer is escalating |
| SEV-3: customer segment, robots, volume | analyst queue | next business day |
| Mix change only | nobody | annotate the dashboard |

## Incident note template

```
Title:            [segment] [FP|FN] up since [date]
Severity:         SEV-x          Status: investigating | mitigated | resolved
Detected by:      [alert / customer / CSM]    Detected at: [UTC]
Impact:           [segment, customers, events, step-ups]
Model, mix or measurement:  [answer + evidence]
Timeline (UTC):   ...
Actions:          ...
Customer comms:   [who, when, explainer used]
Follow-ups:       [monitor change, dashboard change, playbook update]
```
