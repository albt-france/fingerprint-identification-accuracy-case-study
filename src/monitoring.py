"""Accuracy monitoring and anomaly detection, with a back-test against the hidden simulated events.

Reads the dbt marts (dbt/fingerprint.duckdb, read-only) and the raw landing files (row counts only).

Detector (one series = one customer x browser x major version, or the same across all customers):
  1. daily measured FP and FN rates on the control set (bad robots excluded);
  2. reference rate = pooled rate of the previous 28 days of the series (sum of errors / sum of events), times a
     day-of-week factor; a new browser version is compared with the rest of its family until it has history;
  3. quasi-binomial z-score  z = (k - n p0) / sqrt(phi n p0 (1 - p0)); phi (over-dispersion) is estimated on the
     first 4 weeks as the mean squared Pearson residual: events of one device are not independent, so the plain
     binomial variance is too small and would raise false alerts;
  4. persistence: day t and day t-1 are tested TOGETHER (exact one-sided binomial tail on phi-deflated counts) and
     both days must be above the reference;
  5. Benjamini-Hochberg correction over ALL series tested the same day (false discovery rate 1%) -> ALERT.
Platform-level views: a Laney p'-chart (control chart with variable sample size, corrected for over-dispersion)
and a CUSUM on the global daily FP rate, crude and mix-standardized.
Extra monitors: bad-robot share per customer and daily row counts as visible at 06:00 UTC the next morning.

The same detector is applied to a REAL series (Wikimedia unique devices, en.wikipedia): alerts are listed without
any claimed cause.

    python src/monitoring.py
"""
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "dbt" / "fingerprint.duckdb"
PROC = ROOT / "data" / "processed"
HIDDEN = ROOT / "data" / "_hidden_truth.csv"
FDR = 0.01
MIN_N, MIN_EXPECTED = 30, 3.0       # MIN_EXPECTED is only used to estimate phi
MIN_OWN_HISTORY = 3000               # control events in the previous 28 days needed to trust a series' own history
WINDOW_START = pd.Timestamp("2026-08-24")
WEEKS = 13


def load_daily(con) -> pd.DataFrame:
    return con.sql("""
        select event_date, customer_id, browser, browser_major, sum(control_events) as n, sum(fp) as fp, sum(fn) as fn,
               sum(events) as events, sum(bad_bot_events) as bad_bot_events
        from fct_accuracy_daily group by all
    """).df().assign(event_date=lambda d: pd.to_datetime(d["event_date"]))


def dow_factors(daily: pd.DataFrame, metric: str) -> pd.Series:
    """Day-of-week factor of a platform rate = rate on that weekday / overall rate (first 4 weeks only)."""
    d = daily[daily["event_date"] < WINDOW_START + pd.Timedelta(days=28)]
    g = d.groupby(d["event_date"].dt.dayofweek)[[metric, "n"]].sum()
    r = g[metric] / g["n"]
    return r / (d[metric].sum() / d["n"].sum())


def score_series(df: pd.DataFrame, keys: list, metric: str, dowf: pd.Series) -> pd.DataFrame:
    """Add p0 (reference rate), z and one-sided p-value to every (series, day) row.

    Reference = pooled rate of the previous 28 days of the same series. A NEW browser version has no history of
    its own (that is exactly when drifts happen), so until it has 14 days of data it is compared with the rest of
    its family (same customer and browser, all other versions) over the previous 28 days."""
    df = df.sort_values(keys + ["event_date"]).copy()
    df["rate"] = df[metric] / df["n"].where(df["n"] > 0)
    # previous 28 daily rates of the same series (the current day is excluded by shift(1))
    # pooled rate of the previous 28 days of the same series: sum(errors) / sum(control events), current day excluded.
    # (A median of daily rates collapses to 0 on small series where most days have no error at all.)
    roll = lambda s: s.shift(1).rolling(28, min_periods=14).sum()
    roll_own = lambda s: s.shift(1).rolling(28, min_periods=28).sum()   # a version needs 4 full weeks of its own
    hist_k = df.groupby(keys)[metric].transform(roll_own)
    hist_n = df.groupby(keys)["n"].transform(roll_own)
    df["ref_own"] = hist_k / hist_n
    # the first days of a version come from a few early adopters: not a representative baseline
    df.loc[~(hist_n >= MIN_OWN_HISTORY), "ref_own"] = np.nan
    fam_keys = [k for k in keys if k != "browser_major"]
    fam = df.groupby(fam_keys + ["event_date"], as_index=False)[[metric, "n"]].sum().sort_values(fam_keys + ["event_date"])
    fk = fam.groupby(fam_keys)[metric].transform(roll)
    fn_ = fam.groupby(fam_keys)["n"].transform(roll)
    fam["ref_family"] = fk / fn_
    df = df.merge(fam[fam_keys + ["event_date", "ref_family"]], on=fam_keys + ["event_date"], how="left")
    df["ref_median"] = df["ref_own"].fillna(df["ref_family"])
    df["ref_source"] = np.where(df["ref_own"].notna(), "own history", np.where(df["ref_family"].notna(), "rest of family", None))
    df["p0"] = (df["ref_median"] * df["event_date"].dt.dayofweek.map(dowf)).clip(1e-5, 0.5)
    var = df["n"] * df["p0"] * (1 - df["p0"])
    df["pearson"] = (df[metric] - df["n"] * df["p0"]) / np.sqrt(var)
    return df


def estimate_phi(df: pd.DataFrame) -> float:
    """Quasi-binomial dispersion: mean squared Pearson residual over the first 4 weeks of scored rows (>= 1)."""
    early = df[(df["event_date"] < WINDOW_START + pd.Timedelta(days=42)) & df["pearson"].notna() & (df["n"] * df["p0"] >= MIN_EXPECTED)]
    return float(max(1.0, (early["pearson"] ** 2).mean())) if len(early) else 1.0


def exact_tail(k, n, p0, phi):
    """One-sided P(X >= k), X ~ Binomial(n, p0), on over-dispersion-deflated counts (k / phi, n / phi).
    Exact for the small counts of a brand-new browser version, where the normal approximation is not valid.
    P(X >= k) equals the Beta(k, n - k + 1) CDF at p0, which also works for non-integer k and n."""
    k_eff, n_eff = np.asarray(k, float) / phi, np.asarray(n, float) / phi
    with np.errstate(all="ignore"):
        return np.where(k_eff > 0, stats.beta.cdf(p0, k_eff, n_eff - k_eff + 1), 1.0)


def bh(p: np.ndarray, q: float) -> np.ndarray:
    """Benjamini-Hochberg: boolean mask of the p-values declared significant at false discovery rate q."""
    m = len(p)
    order = np.argsort(p)
    passed = p[order] <= q * np.arange(1, m + 1) / m
    k = np.max(np.nonzero(passed)[0]) + 1 if passed.any() else 0
    sig = np.zeros(m, dtype=bool)
    sig[order[:k]] = True
    return sig


def flag(df: pd.DataFrame, keys: list, phi: float) -> pd.DataFrame:
    """Persistence rule: a series alerts on day t when the errors of days t-1 and t TOGETHER are significantly above
    the reference (exact tail, BH over all series of the day) and each of the two days is above the reference."""
    metric = [c for c in ("fp", "fn") if c in df.columns][0]
    df = df.sort_values(keys + ["event_date"]).copy()
    df["z"] = np.where(df["p0"].notna() & (df["n"] >= MIN_N), df["pearson"] / np.sqrt(phi), np.nan)
    g = df.groupby(keys)
    consecutive = (df["event_date"] - g["event_date"].shift(1)).dt.days == 1
    k2 = df[metric] + g[metric].shift(1)
    n2 = df["n"] + g["n"].shift(1)
    exp2 = df["n"] * df["p0"] + g["n"].shift(1) * g["p0"].shift(1)
    p0_2 = exp2 / n2                                        # reference rate of the two days together
    both_up = (df["rate"] > df["p0"]) & (g["rate"].shift(1) > g["p0"].shift(1))
    ok = consecutive & df["p0"].notna() & g["p0"].shift(1).notna() & (n2 >= MIN_N)
    df["p"] = np.where(ok, exact_tail(k2, n2, p0_2, phi), np.nan)
    df["bh_sig"] = False
    for day, gg in df[ok].groupby("event_date"):
        df.loc[gg.index[bh(gg["p"].values, FDR)], "bh_sig"] = True
    df["alert"] = df["bh_sig"] & both_up.fillna(False)
    return df


def run_rate_monitor(daily: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    out, phis = [], {}
    for level, keys in [("customer_segment", ["customer_id", "browser", "browser_major"]), ("platform_segment", ["browser", "browser_major"])]:
        # platform series = production customers only: POC prospects have their own traffic quirks (robots, tests)
        # and are watched by the customer-level series and the robot monitor
        prod = daily[~daily["customer_id"].str.startswith("P")]
        base = daily if level == "customer_segment" else prod.groupby(["event_date", "browser", "browser_major"], as_index=False)[["n", "fp", "fn"]].sum()
        for metric in ["fp", "fn"]:
            s = score_series(base[keys + ["event_date", "n", metric]], keys, metric, dow_factors(daily, metric))
            phi = estimate_phi(s)
            phis[f"{level}_{metric}"] = round(phi, 3)
            f = flag(s, keys, phi)
            f["level"], f["metric"] = level, metric
            out.append(f)
    res = pd.concat(out, ignore_index=True)
    return res, phis


def laney_p_chart(daily: pd.DataFrame, value_col: str) -> pd.DataFrame:
    """Laney p'-chart. Phase I (first 4 weeks) fixes p-bar and sigma_z; points above the upper limit are signals.
    sigma_z = average moving range of the z-scores / 1.128 corrects the binomial limits for over-dispersion."""
    d = daily.sort_values("event_date").copy()
    phase1 = d[d["event_date"] < WINDOW_START + pd.Timedelta(days=28)]
    pbar = phase1["k"].sum() / phase1["n"].sum()
    sig = np.sqrt(pbar * (1 - pbar) / d["n"])
    z1 = (phase1["k"] / phase1["n"] - pbar) / np.sqrt(pbar * (1 - pbar) / phase1["n"])
    sigma_z = np.abs(np.diff(z1.values)).mean() / 1.128
    d["rate"] = d["k"] / d["n"]
    d["center"] = pbar
    d["ucl"] = pbar + 3 * sig * sigma_z
    d["lcl"] = (pbar - 3 * sig * sigma_z).clip(lower=0)
    d["signal"] = d["rate"] > d["ucl"]
    d["sigma_z"] = sigma_z
    d["series"] = value_col
    return d


def cusum(rate: pd.Series, n: pd.Series, p0: float, k: float = 0.5, h: float = 5.0, sigma_z: float = 1.0) -> pd.Series:
    """Upper CUSUM on standardized daily rates: S_t = max(0, S_{t-1} + z_t - k), signal when S_t > h."""
    z = (rate - p0) / np.sqrt(p0 * (1 - p0) / n) / sigma_z
    s, out = 0.0, []
    for v in z:
        s = max(0.0, s + v - k)
        out.append(s)
    return pd.Series(out, index=rate.index)


def platform_views(con) -> pd.DataFrame:
    """Daily global FP: crude (all customers) and mix-standardized (reference segment mix before 2026-10-19)."""
    seg = con.sql("""
        select event_date, browser, device_type, sum(control_events) as n, sum(fp) as fp
        from fct_accuracy_daily group by all
    """).df().assign(event_date=lambda d: pd.to_datetime(d["event_date"]))
    ref = seg[seg["event_date"] < "2026-10-19"].groupby(["browser", "device_type"])["n"].sum()
    w = ref / ref.sum()
    seg = seg.join(w.rename("w"), on=["browser", "device_type"])
    crude = seg.groupby("event_date").agg(n=("n", "sum"), k=("fp", "sum")).reset_index()
    seg["r"] = seg["fp"] / seg["n"]
    std = seg[seg["n"] > 0].groupby("event_date").apply(lambda g: (g["w"] * g["r"]).sum() / g["w"].sum(), include_groups=False).rename("std_rate").reset_index()
    out = crude.merge(std, on="event_date")
    out["k_std"] = out["std_rate"] * out["n"]          # standardized rate expressed on the same n
    return out


def volume_monitor(con_raw) -> pd.DataFrame:
    """Rows of day D visible at 06:00 UTC on D+1 (what a naive morning dashboard shows), per customer."""
    v = con_raw.sql("""
        select cast(ts_utc as date) as event_date, customer_id,
               count(*) filter (where loaded_at <= cast(ts_utc as date) + interval 1 day + interval 6 hour) as rows_next_morning,
               count(distinct event_id) as rows_final
        from read_parquet('data/sim/identification_events/*/*.parquet', hive_partitioning = true)
        group by all
    """).df().assign(event_date=lambda d: pd.to_datetime(d["event_date"]))
    v = v.sort_values(["customer_id", "event_date"])
    v["dow"] = v["event_date"].dt.dayofweek
    # reference = median of the same weekday over the previous 4 weeks (log scale, robust)
    v["ref"] = v.groupby(["customer_id", "dow"])["rows_final"].transform(lambda s: s.shift(1).rolling(4, min_periods=3).median())
    v["log_ratio"] = np.log((v["rows_next_morning"] + 1) / (v["ref"] + 1))
    v["alert"] = v["ref"].notna() & (v["log_ratio"].abs() > np.log(1.25))   # +-25% vs usual weekday volume
    return v


def bot_monitor(daily: pd.DataFrame) -> pd.DataFrame:
    b = daily.groupby(["event_date", "customer_id"], as_index=False)[["events", "bad_bot_events"]].sum().sort_values(["customer_id", "event_date"])
    b["share"] = b["bad_bot_events"] / b["events"]
    b["ref"] = b.groupby("customer_id")["share"].transform(lambda s: s.shift(1).rolling(28, min_periods=3).median())
    b["ref"] = b["ref"].fillna(0.025)   # a brand-new POC is compared with the typical robot share
    sd = np.sqrt(b["ref"] * (1 - b["ref"]) / b["events"]) * 3        # generous over-dispersion allowance
    b["alert"] = (b["share"] > b["ref"] + 3 * sd) & (b["share"] > 2 * b["ref"]) & (b["share"] > 0.08)
    return b


def backtest(rates, vol, bots, pchart_crude, pchart_std, hidden) -> dict:
    """Compare alerts with the hidden events. An alert is 'true' when it hits the event's segment between its start
    and 3 days after its end; anything else is a false alert (on-call load)."""
    h = hidden.set_index("event_no")
    def win(no):
        return pd.Timestamp(h.loc[no, "start"]), pd.Timestamp(h.loc[no, "end"]) + pd.Timedelta(days=3)
    alerts = rates[rates["alert"]].copy()
    res = {}
    s1, e1 = win(1)
    m1 = (alerts["metric"] == "fn") & alerts["browser"].isin(["Chrome", "Chrome Mobile"]) & (alerts["browser_major"] == 155) & alerts["event_date"].between(s1, e1)
    s2, e2 = win(2)
    m2 = (alerts["metric"] == "fp") & (alerts["browser"] == "Mobile Safari") & (alerts["browser_major"] == 27) & alerts["event_date"].between(s2, e2)
    s6r, e6r = win(6)
    # undetected robots (10% of the bad robots are not flagged) leak into the measured FN rate of the POC
    m6r = (alerts["customer_id"] == "P01") & alerts["event_date"].between(s6r, e6r)
    alerts["true_alert"] = m1 | m2 | m6r
    alerts["matched_event"] = np.select([m1, m2, m6r], ["1", "2", "6"], default="")
    for no, m in [(1, m1), (2, m2)]:
        first = alerts.loc[m, "event_date"].min()
        res[f"event_{no}"] = {"detected": bool(m.any()), "first_alert": None if pd.isna(first) else str(first.date()),
                              "delay_days": None if pd.isna(first) else int((first - win(no)[0]).days),
                              "alerting_series": int(alerts.loc[m].drop_duplicates(["level", "customer_id", "browser", "browser_major", "metric"]).shape[0])}
    va = vol[vol["alert"]]
    s5, e5 = win(5)
    m5 = va["event_date"].between(s5, e5) & (((va["customer_id"] == "C05") & (va["event_date"] == "2026-10-27")) | (va["event_date"] == "2026-10-28"))
    m6v = (va["customer_id"] == "P01") & va["event_date"].between(*win(6))     # robot wave also inflates volume
    res["event_5"] = {"detected": bool(m5.any()), "alerts": int(m5.sum()), "robot_wave_volume_alerts": int(m6v.sum()),
                      "false_volume_alerts": int((~m5 & ~m6v).sum())}
    ba = bots[bots["alert"]]
    s6, e6 = win(6)
    m6 = (ba["customer_id"] == "P01") & ba["event_date"].between(s6, e6)
    res["event_6"] = {"detected": bool(m6.any()), "first_alert": str(ba.loc[m6, "event_date"].min().date()) if m6.any() else None,
                      "false_bot_alerts": int((~m6).sum())}
    s8 = pd.Timestamp(h.loc[8, "start"])
    res["event_8"] = {
        "naive_global_signal_days_after_start": int(pchart_crude.loc[pchart_crude["event_date"] >= s8, "signal"].sum()),
        "naive_global_signal_days_before_start": int(pchart_crude.loc[pchart_crude["event_date"] < s8, "signal"].sum()),
        "standardized_signal_days_after_start": int(pchart_std.loc[pchart_std["event_date"] >= s8, "signal"].sum()),
        "segment_alerts_after_start_excluding_events_1_2": int(alerts.loc[(alerts["event_date"] >= s8) & ~alerts["true_alert"]].shape[0]),
    }
    seg_alerts = alerts.drop_duplicates(["level", "customer_id", "browser", "browser_major", "metric", "event_date"])
    n_true = int(seg_alerts["true_alert"].sum()); n_all = len(seg_alerts)
    res["segment_alerts"] = {"alert_days_total": n_all, "true_alert_days": n_true,
                             "precision": round(n_true / n_all, 3) if n_all else None,
                             "false_alert_days_per_week": round((n_all - n_true) / WEEKS, 2),
                             "recall_events_1_2": sum(res[f"event_{k}"]["detected"] for k in (1, 2)) / 2}
    detected = [res["event_1"]["detected"], res["event_2"]["detected"], res["event_5"]["detected"], res["event_6"]["detected"]]
    res["recall_events_1_2_5_6"] = sum(detected) / 4
    false_total = (n_all - n_true) + res["event_5"]["false_volume_alerts"] + res["event_6"]["false_bot_alerts"]
    res["false_alerts_per_week_all_monitors"] = round(false_total / WEEKS, 2)
    return res, alerts


def wikimedia_detector() -> pd.DataFrame:
    """Same logic on a REAL count series: log(devices) vs the median of the previous 28 days x weekday factor;
    robust z = residual / (1.4826 x MAD of residuals over the previous 56 days); alert = |z| > 4 two days in a row."""
    w = pd.read_csv(PROC / "wikimedia_unique_devices.csv", parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    y = np.log(w["devices"])
    ref = y.shift(1).rolling(28, min_periods=21).median()
    resid0 = y - ref
    dow = resid0.groupby(w["date"].dt.dayofweek).transform(lambda s: s.shift(7).rolling(8, min_periods=4).median())
    resid = resid0 - dow
    mad = resid.shift(1).rolling(56, min_periods=28).apply(lambda s: np.median(np.abs(s - np.median(s))), raw=True)
    w["z"] = resid / (1.4826 * mad)
    big = w["z"].abs() > 4
    w["alert"] = big & big.shift(1, fill_value=False)
    return w


def main():
    con = duckdb.connect(str(DB), read_only=True)
    daily = load_daily(con)
    rates, phis = run_rate_monitor(daily)
    pv = platform_views(con)
    p_crude = laney_p_chart(pv[["event_date", "n", "k"]], "fp_rate_crude")
    p_std = laney_p_chart(pv[["event_date", "n"]].assign(k=pv["k_std"]), "fp_rate_standardized")
    p_crude["cusum"] = cusum(p_crude["rate"], p_crude["n"], p_crude["center"].iloc[0], sigma_z=p_crude["sigma_z"].iloc[0]).values
    p_std["cusum"] = cusum(p_std["rate"], p_std["n"], p_std["center"].iloc[0], sigma_z=p_std["sigma_z"].iloc[0]).values
    con_raw = duckdb.connect()
    import os
    os.chdir(ROOT)
    vol = volume_monitor(con_raw)
    bots = bot_monitor(daily)
    hidden = pd.read_csv(HIDDEN)
    res, alerts = backtest(rates, vol, bots, p_crude, p_std, hidden)
    res["phi"] = phis
    res["parameters"] = {"fdr": FDR, "min_control_events": MIN_N, "min_expected_count": MIN_EXPECTED, "consecutive_days": 2, "reference_days": 28}
    wk = wikimedia_detector()
    res["wikimedia_alert_days"] = wk.loc[wk["alert"], "date"].dt.strftime("%Y-%m-%d").tolist()
    PROC.mkdir(exist_ok=True)
    alerts[["level", "metric", "customer_id", "browser", "browser_major", "event_date", "n", "rate", "p0", "ref_source", "z", "p", "true_alert", "matched_event"]].to_csv(PROC / "monitoring_alerts.csv", index=False)
    pd.concat([p_crude, p_std])[["series", "event_date", "n", "rate", "center", "ucl", "lcl", "signal", "cusum"]].to_csv(PROC / "monitoring_pchart.csv", index=False)
    vol[["event_date", "customer_id", "rows_next_morning", "rows_final", "ref", "alert"]].to_csv(PROC / "monitoring_volume.csv", index=False)
    bots[["event_date", "customer_id", "events", "share", "ref", "alert"]].to_csv(PROC / "monitoring_bots.csv", index=False)
    wk[["date", "devices", "z", "alert"]].to_csv(PROC / "wikimedia_detector.csv", index=False)
    # platform-segment series of the two drift events, for charts
    keep = rates[(rates["level"] == "platform_segment") & (((rates["browser"] == "Chrome") & (rates["browser_major"].isin([154, 155, 156])) & (rates["metric"] == "fn"))
                 | ((rates["browser"] == "Mobile Safari") & (rates["browser_major"].isin([26, 27])) & (rates["metric"] == "fp")))]
    keep[["metric", "browser", "browser_major", "event_date", "n", "rate", "p0", "ref_source", "z", "p", "bh_sig", "alert"]].to_csv(PROC / "monitoring_drift_series.csv", index=False)
    (PROC / "monitoring_backtest.json").write_text(json.dumps(res, indent=2, default=str))
    print(json.dumps({k: res[k] for k in ["event_1", "event_2", "event_5", "event_6", "event_8", "segment_alerts", "recall_events_1_2_5_6", "false_alerts_per_week_all_monitors", "phi"]}, indent=1, default=str))


if __name__ == "__main__":
    main()
