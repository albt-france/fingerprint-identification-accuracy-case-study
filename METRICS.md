# Metrics dictionary

Every metric used in the dashboard, the health reports, the self-service tools and the report. Accuracy definitions
follow Fingerprint's public documentation ([Identification accuracy and confidence](https://docs.fingerprint.com/docs/identification-accuracy-and-confidence),
read 2026-11-23). Everything computed on the simulated platform is **SIMULATED**. Nothing here describes Fingerprint's
own accuracy, models or signals.

## 1. Accuracy outcomes (Fingerprint's definitions)

Fingerprint measures accuracy with a prediction experiment:

- **Control set**: events identified **deterministically** (a signal such as a cookie gives the answer).
- **Test set**: the **same events** with the deterministic signal removed, identified again from the other signals only.
- Each control event gets exactly one outcome:

| Outcome | Definition | In this project |
|---|---|---|
| True positive (TP) | the test answer is the same visitor as the control answer | `measured_outcome = 'TP'` |
| False positive (FP) | identified as **another existing visitor** (two people merged) | `'FP'` |
| False negative (FN) | identified as a **new visitor** although the visitor exists (one person split) | `'FN'` |
| True negative (TN) | a new visitor identified as new | `'TN'` |

Identity checked by a singular dbt test: `TP + FP + FN + TN = control events` (`assert_outcomes_sum_to_control`).

## 2. Rates

| Metric | Formula | Grain | Notes |
|---|---|---|---|
| Measured FP rate | FP / control events | day x customer x browser x major x device type, then any roll-up | bad robots excluded |
| Measured FN rate | FN / control events | same | bad robots excluded |
| True FP / FN rate (sim only) | errors against the hidden true device / all human events | same | only exists because the data is simulated: shows the bias of the measurement |
| Event-grain rate (real data) | outcomes counted on every page view | event | repeated page views of a returning user are easy wins: inflates TP |
| Visit-grain rate (real data) | outcomes counted on the first event after 30 minutes of inactivity | visit | closer to one identification request per visit |
| Day-grain rate (real data) | first event of a user each day | user-day | |
| Wilson 95% interval | see `docs/statistics_notes.md` | any rate | used everywhere instead of the normal interval |
| Mix-standardized rate | sum over segments of w_s x rate_s, weights fixed (browser x device type mix before 2026-10-19) | week | moves only when rates **inside** segments move |
| Stable-cohort rate | crude rate on customers live during the whole window | week | removes onboarding effects |

**Pitfalls**: the control set excludes private browsing (no cookie), so the measured rates are optimistic when the
incognito share grows (event 7). Rates of small series are noisy: never read a rate under 200 control events. Daily
counts of the real ClickBench data are never compared (only 17 days, very uneven volumes): rates only.

## 3. Confidence score and calibration

- **Confidence score** = 1 - estimated probability of a false positive; 1.0 for a new visitor (Fingerprint's definition).
  It says nothing about false negatives.
- **Below-threshold share** = answers with an existing visitor whose confidence is under the customer's threshold
  / answers with an existing visitor. A customer often asks for an extra step (for example a one-time code) under its
  threshold, so this is the customer-visible "step-up rate".
- **Calibration**: within a score bin, the observed precision (1 - FP share) should equal the mean score.
  **Expected calibration error (ECE)** = sum over bins of (share of answers in the bin) x |mean score - observed precision|.

## 4. Customer-specific metrics (account ids sent as linkedId)

| Metric | Formula | Reads as |
|---|---|---|
| Accounts per visitor | distinct `linked_id` per `visitor_id` | high = possible merges (FP), shared family devices or internal agents |
| Visitors per account | distinct `visitor_id` per `linked_id` | high = several devices per person, splits (FN), incognito or robots |
| Share of visitors with > 5 accounts | | tail of the first metric |
| Internal traffic (suspected) | visitor with >= 20 distinct accounts AND main network shared by >= 5 such visitors | agents or support staff: exclude before concluding |

Each metric is reported in three scopes: `all`, `excl_bad_bots`, `excl_internal_and_bots` (`mart_linked_id_metrics`).

## 5. Traffic-mix metrics

| Metric | Formula |
|---|---|
| Control share | control events / human events |
| Incognito share | private-browsing human events / human events |
| Bad-robot share | events with `bot_result = 'bad'` / all events |
| New-visitor share | human events answered with a new visitor / human events (observable without any truth: rises with incognito traffic and with FN) |

## 6. Health status (weekly, per customer: `mart_customer_health`)

Baseline = the customer's own previous 4 weeks (pooled). Change test = quasi-binomial z-score
z = (k - n p0) / sqrt(phi n p0 (1 - p0)), phi = 2.0 (over-dispersion; estimated in `src/monitoring.py`).

| Status | Rule (first match wins) |
|---|---|
| grey | fewer than 2 weeks of history (no baseline) |
| red | FP or FN up with z > 3, or bad-robot share > 20%, or an open **critical** request |
| amber | FP or FN up with z > 2, or bad-robot share > 10%, or incognito share up > 5 points, or an open **high** request |
| green | otherwise |

The reasons are written in plain English next to the status (`health_reasons`).

## 7. Monitoring

See `docs/oncall_runbook.md`: per-series quasi-binomial z against a 28-day median with a weekday factor, Benjamini-Hochberg
over all series of the day (FDR 1%), alert after 2 consecutive significant days; Laney p'-chart and CUSUM on the global rate,
crude and mix-standardized; bad-robot share and next-morning row-count monitors.

## 8. Request queue

Priority = impact (1-4, simulated ARR at stake; POC prospects and platform-wide questions = 3) x urgency (1-4);
P1 >= 12, P2 >= 6, P3 >= 3, P4 otherwise; resolution targets 2 / 5 / 10 / 20 days. Rules in `docs/request_triage.md`.
