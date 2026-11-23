# Playbook: reported false positives ("you merge my users")

**Trigger**: a customer, CSM or Sales Engineer reports that different people get the same visitor id, or the
false-positive monitor alerts, or a customer sees more step-ups (one-time codes) than usual.

**Goal**: in one working day, say whether the merges are real false positives, where they come from, and what the
customer should do; in plain language.

## 1. Questions to ask the customer

1. Which visitor ids or accounts? From when? (a list of 5-20 examples with timestamps, UTC or local time?)
2. How do they know two users are different (different accounts, different payment instruments, support tickets)?
3. Do they send `linkedId` (account ids)? Do they use a confidence threshold, and which one?
4. Anything that changed on their side: release, campaign, new app version, new traffic source, support tooling?
5. Do staff or support agents log into customer accounts from their own machines?

## 2. Queries (read-only, in this order)

```
python tools/accuracy_cli.py summary --customer C02 --start <4 weeks ago> --end <today> --by browser_version
python tools/accuracy_cli.py change --customer C02 --metric fp --a <before> --b <after>
```
- `fct_accuracy_daily` filtered on the customer: FP rate by browser x version x device type, with intervals.
- Platform view of the same segments (`mart_anomaly_candidates`, `data/processed/monitoring_alerts.csv`): is the
  segment worse for **every** customer (model / browser issue) or only for this one (customer traffic)?
- `mart_linked_id_metrics`: accounts per visitor, all vs `excl_internal_and_bots`.
- `int_internal_traffic`: visitors with 20+ accounts on a shared network (agents, test devices).
- Confidence distribution of the affected answers vs the customer's threshold.

## 3. Decision tree

```
Is the FP increase significant (quasi-binomial test, p < 0.01)?
 |- no  -> noise or a handful of anecdotes: explain with the interval; ask for more examples; close.
 |- yes -> Is it concentrated in one browser version / OS version?
           |- yes, on every customer  -> platform issue (e.g. a new OS release): open an engineering ticket with
           |                             the segment, start date, size; check calibration of the score in the segment.
           |- yes, one customer only  -> customer traffic: new app version, webview, test devices?
           |- no  -> Do the "merged" accounts come from few visitors on shared networks?
                     |- yes -> internal traffic or shared devices: NOT false positives (playbook linked_id_custom_metrics).
                     |- no  -> Did the customer's traffic mix change (new market, mobile share)?
                               |- yes -> mix effect: show standardized rates (playbook anomaly_triage).
                               |- no  -> escalate with the full evidence pack.
```

## 4. Worked example (SIMULATED): C02, "our users receive more one-time codes"

- The step-up share of C02 rose after mid-September. By segment, only **Mobile Safari on iOS 27** moved: the platform
  monitor had flagged the same segment for every customer the day after the real iOS 27 release (2026-09-14).
- In that segment, true false positives were about 5% while the confidence score announced about 3%: the score was
  **overconfident**, and part of the answers fell under C02's 0.95 threshold -> more one-time codes.
- After the model recalibration (simulated release of 2026-10-07) the segment went back to normal.
- Figures: report page 6 and `findings.json` (`sim.e2`).

## 5. Message template for Customer Success

> Thanks for the examples. We confirmed a temporary increase of mistaken matches for iPhone users on the latest iOS
> version, between [dates]. It affected all customers, not only you; your other traffic was unchanged. Because those
> answers carried a lower confidence, some of your users were asked for a one-time code: that was your threshold doing
> its job. A fix was released on [date] and the rate is back to normal since [date]. We will keep watching this segment
> and send you the weekly health report.
