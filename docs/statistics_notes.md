# Statistics notes

How the project tells a real change from noise. Every method is implemented in `src/metrics.py` (unit-tested in
`tests/test_metrics.py`) or in `src/monitoring.py`; the numbers are in `data/processed/findings.json`.

## 1. Intervals for rates: Wilson

A false-positive rate is a small proportion (often under 1%). The textbook normal interval p +- 1.96 sqrt(p(1-p)/n)
can go below 0 and is too narrow for small n. The **Wilson score interval** stays in [0, 1] and is accurate for small
rates:

centre = (p + z^2/2n) / (1 + z^2/n), half-width = z sqrt(p(1-p)/n + z^2/4n^2) / (1 + z^2/n), z = 1.96.

Used in every mart (`wilson_lower` / `wilson_upper` dbt macros) and tool.

## 2. Events of one device are not independent: cluster bootstrap

The same device tends to be misidentified again and again (it sits in a crowd of look-alike devices, or it wipes its
storage). Treating its 20 events as 20 independent trials overstates the information, so the binomial (and Wilson)
interval is **too narrow**.

**Cluster bootstrap**: resample **visitors** with replacement (keeping all their events), recompute the rate, repeat
1,000 times, take the 2.5% and 97.5% percentiles. The ratio of the clustered variance to the binomial variance is the
**design effect**; it is also the over-dispersion factor phi used in the tests below. Example in the report: C04, last
4 weeks (`sim.stats.c04`).

## 3. Is a change real? Quasi-binomial test

Two periods, k1/n1 and k2/n2. z = (p2 - p1) / sqrt(phi p(1-p)(1/n1 + 1/n2)) with the pooled p. phi > 1 widens the
test for over-dispersion. A change is called real at p < 0.01, and only after checking that **one segment** (a browser
version, a customer, incognito traffic) does not explain it on its own.

## 4. How much data do we need? Minimal detectable effect

To detect an absolute change delta of a rate p0 with a two-sided 5% test and 80% power, each period needs

n = (1.96 + 0.84)^2 x phi x 2 p0 (1 - p0) / delta^2 control events.

Divided by the customer's daily control events, this gives the number of **days** to wait before a change of that size
can be confirmed ("to see +0.2 points of FP at C04 we need N events, about X days per period").

## 5. Mix effects (Simpson's paradox) and direct standardization

A platform-wide rate is a weighted average of segment rates, weighted by the traffic mix. If a new customer brings a
lot of high-error segments (look-alike mobile devices), the platform rate rises **although no segment got worse**.
**Direct standardization** recomputes the rate at a fixed reference mix:

standardized rate = sum over segments s of w_s x rate_s, with w_s fixed (here: browser x device type shares before 2026-10-19).

If the crude rate jumps and the standardized rate does not, the change is mix, not model. A second check: the
**stable cohort** (customers live during the whole window).

## 6. Many series at once: Benjamini-Hochberg

The monitor tests hundreds of series a day (customer x browser x version). At a 1% level, a few would fire by chance
every day. Benjamini-Hochberg sorts the p-values and keeps those under q x rank / m, which controls the **false
discovery rate** (q = 1%: about 1 alert in 100 is expected to be noise).

## 7. Control charts: Laney p'-chart and CUSUM

- **p-chart** with variable n: limits p-bar +- 3 sqrt(p-bar(1-p-bar)/n_t). With very large daily n, the binomial limits are
  so tight that ordinary day-to-day variation breaches them. **Laney's p'-chart** multiplies the limits by sigma_z,
  the moving-range spread of the daily z-scores in the reference phase, which absorbs that extra variation.
- **CUSUM**: S_t = max(0, S_{t-1} + z_t - k), signal when S_t > h (k = 0.5, h = 5). Sensitive to small persistent shifts
  that a 3-sigma chart misses.

## 8. Precision, recall and the confidence threshold

From the customer's point of view, a step-up (one-time code) under the threshold is a "flag". Precision of the flags =
share of flagged answers that were really false positives; recall = share of false positives that were flagged.
Raising the threshold flags more answers (more friction for good users) and catches more false positives. The report
shows this curve for C02 on simulated truth.

## 9. Calibration

A confidence score is calibrated when, among answers with score s, a share 1 - s are false positives. Reliability
curve: mean score vs observed precision per score bin; **expected calibration error** = weighted mean gap. Calibration
can hold globally and fail in one segment (iOS 27 before its fix), so it is checked per segment.
