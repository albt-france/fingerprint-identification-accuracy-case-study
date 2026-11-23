# Playbook: triaging an accuracy anomaly ("is it the model, the mix or the measurement?")

**Trigger**: an alert from the monitor, a jump on a global dashboard, or a question from Product.

## 1. First 15 minutes

1. **Which view fired?** Global crude rate, mix-standardized rate, a platform segment, a customer segment, the robot or
   volume monitor (`docs/oncall_runbook.md`).
2. **Is the data complete?** Check dbt test results (freshness, row counts vs ingestion log, duplicates). A hole or a
   spike in volume is a pipeline question first.
3. **Model, mix or measurement?**

| Question | Look at | If yes |
|---|---|---|
| Did rates move **inside** segments? | mix-standardized rate, per-segment series | **model** (or browser) change: platform segment alerts, release calendar |
| Did only the **composition** change? | crude vs standardized vs stable cohort; new customers; robot and incognito shares | **mix**: fix the dashboard, no model incident |
| Did the **measurement** change? | control share, incognito share, grain, time zone, duplicates | **measurement**: correct the metric or the pipeline |

## 2. Worked example (SIMULATED): the week of 2026-10-19

- The global weekly FP rate rose by about 30% (`findings.json` `sim.e8.crude_change`). The global p'-chart signalled
  every day from 2026-10-19.
- The mix-standardized rate did not move; the stable cohort did not move; no customer moved significantly week over week;
  no platform segment alerted.
- Cause: C12, a large mobile marketplace, went live on 2026-10-19. Its traffic is mostly look-alike iPhones, a segment
  with a higher error rate everywhere; C12's rate in that segment matches the other customers' (intervals overlap).
- Decision: **no model incident**. Fix the dashboard: show the mix-standardized and stable-cohort lines next to the
  crude one, and annotate onboardings.

## 3. Message template for Product

> The global FP line went up ~30% on 19 October because a large mobile-heavy customer went live, not because the model
> got worse. At a constant traffic mix the rate is flat, every existing customer is stable, and the new customer's
> rate per segment matches everybody else's. We added a constant-mix line to the dashboard so this does not page anyone
> again.
