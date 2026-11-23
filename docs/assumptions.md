# Assumptions of the simulation

The simulated identification platform is fictional. Its error rates are **illustrative assumptions**, chosen to be
plausible and to make the analytical problems visible. They are **not** Fingerprint's figures and must never be read
as such. Seed 42, `src/simulate_platform.py`.

## Calibrated on real public data

| Element | Real source | How it is used |
|---|---|---|
| Release dates of Chrome 152-159, Firefox 154-160, iOS 27 | Chromium Dash, Mozilla product-details, endoflife.date | versions appear on their real dates; the two drifts are placed on real releases (Chrome 155 on 2026-09-23, iOS 27 on 2026-09-14) |
| Speed of adoption of a new major version | Wikimedia weekly browser shares, median "uptake" (share already on the version or newer) over the 2023-2026 releases | each simulated device has an update lag u ~ U(0,1); it runs the newest version whose uptake exceeds u |
| Browser mix | Wikimedia shares of the last week (Chrome Mobile, Mobile Safari, Chrome, Edge, Firefox...) | profiles tilted per customer type (banks more desktop, marketplaces more mobile) |
| Volume | the job post states about 1 billion requests per month for the Identification API | the simulation has ~15M events in 13 weeks, roughly 1/190 of the same period at that rate (`findings.json` `sim.volume.scale_vs_1bn_per_month`) (scale only, no other link) |

## Pure assumptions (illustrative)

| Assumption | Value |
|---|---|
| FP rate of the probabilistic answer for a returning device | Chrome / Edge 0.5%, Firefox 0.7%, Safari desktop 1.0%, Chrome Mobile 1.0%, Mobile Safari 2.4% (look-alike iPhones), Samsung Internet 1.2%, native apps 0.15% |
| FN rate of the probabilistic answer | 2.0% to 3.5% for browsers, 0.4% for native apps |
| Probability that a returning device still has its cookie (deterministic answer) | Chrome / Edge 80%, Firefox 72%, Chrome Mobile 70%, Samsung 65%, Safari 45%, Mobile Safari 40%, native apps 93%; 0 in private browsing |
| Device-level persistence of errors | lognormal factor per device (sigma 0.8 for FP, 0.6 for FN, mean 1): some devices are mismatched again and again |
| Event-level spread of the FP risk | lognormal (sigma 0.35, mean 1) |
| Private browsing | 6% of human events (C09: 8% then 22% after its campaign) ; FP x1.5 and FN x3 |
| VPN | 4% of devices, 70% of their events; FP x1.3, FN x1.5 |
| Robots | bad 2.5% of events (90% flagged `bad`, 10% `notDetected`), good 1%; bad robots: FN 60%, cookie 30% |
| New browser version | FN x1.25 during the first 7 days (normal adaptation) |
| Confidence score | 1 - per-event FP risk + small noise (calibrated), except iOS 27 Mobile Safari before the fix: announces 0.6 x the real risk |
| Seasonality | weekdays +6%, weekends -12% (gaming the other way round); diurnal profile in the customer's time zone |
| Daily batch | a day is loaded the next day around 02:00-03:00 UTC |
| Customers | 12 customers + 2 POC prospects, sectors, thresholds and simulated ARR are invented |
| Edge versions | follow the Chromium milestone about 3 days later (Edge is not in the release feeds used) |
| Samsung Internet / Android apps | version not modelled (constant) |

## The 8 hidden events (verified one by one in the notebook and the report)

1. Chrome 155: FN x3 for 9 days until a model fix (2026-09-23 to 2026-10-02).
2. iOS 27 Mobile Safari: real FP about 5% with an overconfident score (2026-09-14 to 2026-10-07); C02 sees more step-ups.
3. C07: 40 call-centre agent devices on 3 office networks + 6% family devices: not false positives.
4. C03: no proxy integration (9% of requests blocked) and an export in local time (New York, DST change on 2026-11-01).
5. Pipeline: 35% of C05 rows re-sent on 2026-10-27; the 2026-10-28 partition loaded two days late.
6. P01 POC: bad robots reach 45% of traffic from 2026-11-05 to 2026-11-12.
7. C09: private browsing from 8% to 22% after 2026-10-12; the control set excludes it.
8. FALSE SIGNAL: C12 (mobile marketplace) goes live on 2026-10-19; per-segment rates unchanged.
