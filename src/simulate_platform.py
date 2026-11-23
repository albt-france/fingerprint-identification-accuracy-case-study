"""SIMULATED identification platform: 13 weeks (2026-08-24 to 2026-11-22), 12 customers + 2 prospects, ~15M events.

Nothing here is Fingerprint data. The platform, its customers (C01..C12, P01, P02), its error rates and its model
releases are fictional ("the simulated identification platform"). Only the browser release calendar
(data/processed/browser_releases.csv) and the version-adoption curves (Wikimedia) are real; every other number
is an assumption written in docs/assumptions.md.

How one event is generated
1. a TRUE device visits a customer (hidden: device_truth.true_device_id);
2. if the device was seen before AND keeps a cookie (depends on browser, never in incognito), the platform answers
   DETERMINISTICALLY (right visitor_id, by construction);
3. otherwise it answers PROBABILISTICALLY: right visitor (TP), another existing visitor (FP), a brand-new id for a
   returning device (FN) or a new id for a new device (TN), with segment-level probabilities;
4. for deterministic events, the probabilistic answer is ALSO drawn and stored in probabilistic_visitor_id: this is
   the test set of Fingerprint's published accuracy method (control = deterministic answer, test = the same event
   re-identified without the deterministic signal), so the measured accuracy can be computed like Fingerprint does,
   and the hidden truth shows how biased that measurement is.

Outputs in data/sim/ (never published, too large) + data/_hidden_truth.csv (removed before any push).

    python src/simulate_platform.py            # seed 42, ~3-5 minutes
"""
import datetime as dt
import json
import shutil
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT / "data" / "sim"
PROC = ROOT / "data" / "processed"
SEED = 42
START, END = dt.date(2026, 8, 24), dt.date(2026, 11, 22)
DAYS = pd.date_range(START, END, freq="D")
UTC = ZoneInfo("UTC")

# ----------------------------------------------------------------------------------------------- customers
# volume = average identification events per day (before weekly seasonality); arr = simulated ARR in USD.
CUSTOMERS = [
    # id,   sector,               use case,                 plan,         region, pod,     start,        thr,  arr,     vol,   tz,                    proxy, mix,           linked
    ("C01", "Online bank",        "Account takeover",       "Enterprise", "EU",    "POD-A", "2024-03-01", 0.90, 310000, 11200, "Europe/Paris",        True,  "desktop_bank", 0.5),
    ("C02", "Fintech app",        "Account takeover",       "Enterprise", "US",    "POD-A", "2024-09-15", 0.95, 420000, 15800, "America/New_York",    True,  "mobile_fin",   0.6),
    ("C03", "Subscription news",  "Paywall",                "Pro",        "US",    "POD-B", "2025-02-01", 0.80,  95000, 14000, "America/New_York",    False, "news",         0.0),
    ("C04", "Marketplace",        "Promo abuse",            "Enterprise", "EU",    "POD-B", "2023-11-20", 0.90, 380000, 17700, "Europe/Berlin",       True,  "marketplace",  0.3),
    ("C05", "Ticketing",          "Payment fraud",          "Enterprise", "EU",    "POD-C", "2024-05-10", 0.90, 260000, 13000, "Europe/London",       True,  "desktop_mix",  0.2),
    ("C06", "Crypto exchange",    "Account takeover",       "Enterprise", "APAC",  "POD-C", "2025-04-01", 0.97, 290000,  8400, "Asia/Singapore",      True,  "mobile_fin",   0.6),
    ("C07", "Online bank",        "Account takeover",       "Enterprise", "EU",    "POD-A", "2024-01-15", 0.90, 450000, 14900, "Europe/Madrid",       True,  "desktop_bank", 0.7),
    ("C08", "Travel",             "Payment fraud",          "Pro",        "EU",    "POD-B", "2025-06-01", 0.85, 120000, 10200, "Europe/Paris",        False, "desktop_mix",  0.1),
    ("C09", "Gaming",             "Promo abuse",            "Pro",        "US",    "POD-C", "2025-01-10", 0.85, 150000, 12100, "America/Los_Angeles", True,  "gaming",       0.3),
    ("C10", "B2B SaaS",           "Account sharing",        "Pro",        "US",    "POD-A", "2025-08-01", 0.90,  80000,  5600, "America/Chicago",     True,  "desktop_saas", 0.5),
    ("C11", "E-commerce",         "Payment fraud",          "Pro",        "LATAM", "POD-B", "2025-03-15", 0.85, 110000, 9300, "America/Sao_Paulo",   False, "marketplace",  0.1),
    ("C12", "Marketplace (mobile)", "Promo abuse",          "Enterprise", "APAC",  "POD-C", "2026-10-19", 0.90, 520000, 80000, "Asia/Tokyo",          True,  "mobile_market", 0.2),
    ("P01", "Fintech (prospect)", "Account takeover (POC)", "POC",        "EU",    "POD-A", "2026-10-26", 0.95,      0,  4000, "Europe/Paris",        True,  "mobile_fin",   0.8),
    ("P02", "E-commerce (prospect)", "Payment fraud (POC)", "POC",        "US",    "POD-B", "2026-11-02", 0.90,      0,  3000, "America/New_York",    True,  "marketplace",  0.1),
]
COLS = ["customer_id", "sector", "use_case", "plan", "region", "csm_pod", "start_date", "confidence_threshold",
        "arr_usd_simulated", "avg_daily_events", "timezone", "proxy_integration", "traffic_mix", "linked_id_share"]

# Browser mix per traffic profile (shares of devices). Calibrated on the Wikimedia browser shares of the last week
# (data/processed/wikimedia_browser_share.csv: Chrome Mobile 29%, Mobile Safari 21%, Chrome 19%, Edge 5%,
# Firefox 5%) and tilted per profile (banks more desktop, marketplaces more mobile). Assumption.
BROWSERS = ["Chrome", "Edge", "Firefox", "Safari", "Chrome Mobile", "Mobile Safari", "Samsung Internet", "Native iOS", "Native Android"]
MIX = {
    "desktop_bank":  [0.38, 0.12, 0.08, 0.07, 0.15, 0.14, 0.03, 0.02, 0.01],
    "desktop_mix":   [0.32, 0.09, 0.07, 0.06, 0.20, 0.19, 0.04, 0.02, 0.01],
    "desktop_saas":  [0.52, 0.15, 0.10, 0.10, 0.05, 0.06, 0.01, 0.005, 0.005],
    "news":          [0.27, 0.07, 0.06, 0.06, 0.25, 0.23, 0.06, 0.0, 0.0],
    "marketplace":   [0.24, 0.06, 0.05, 0.05, 0.26, 0.22, 0.05, 0.04, 0.03],
    "gaming":        [0.34, 0.06, 0.06, 0.03, 0.24, 0.17, 0.04, 0.03, 0.03],
    "mobile_fin":    [0.14, 0.05, 0.03, 0.04, 0.18, 0.26, 0.03, 0.16, 0.11],
    "mobile_market": [0.02, 0.005, 0.005, 0.01, 0.12, 0.80, 0.02, 0.015, 0.005],
}
OS_OF = {"Chrome": (["Windows", "macOS", "Linux", "ChromeOS"], [0.70, 0.20, 0.03, 0.07]), "Edge": (["Windows", "macOS"], [0.95, 0.05]),
         "Firefox": (["Windows", "macOS", "Linux"], [0.75, 0.15, 0.10]), "Safari": (["macOS"], [1.0]),
         "Chrome Mobile": (["Android"], [1.0]), "Mobile Safari": (["iOS"], [1.0]), "Samsung Internet": (["Android"], [1.0]),
         "Native iOS": (["iOS"], [1.0]), "Native Android": (["Android"], [1.0])}
# Illustrative error rates of the PROBABILISTIC answer for a returning device, and probability that a returning
# device still has its cookie (deterministic answer). Assumptions, never Fingerprint's figures.
#              fp      fn     cookie
SEG = {"Chrome": (0.005, 0.020, 0.80), "Edge": (0.005, 0.020, 0.80), "Firefox": (0.007, 0.028, 0.72),
       "Safari": (0.010, 0.035, 0.45), "Chrome Mobile": (0.010, 0.025, 0.70), "Mobile Safari": (0.024, 0.030, 0.40),
       "Samsung Internet": (0.012, 0.030, 0.65), "Native iOS": (0.0015, 0.004, 0.93), "Native Android": (0.0015, 0.004, 0.93)}
RISK_SIGMA = 0.35         # event-level spread of the FP risk around the device's own rate (lognormal, mean 1)
DEVICE_SIGMA_FP, DEVICE_SIGMA_FN = 0.8, 0.6   # device-level spread (lognormal, mean 1): clustering of errors
INCOGNITO = {"C09": 0.08}  # base incognito share, default below
DEFAULT_INCOGNITO = 0.06
VPN_DEVICE_SHARE = 0.04
BAD_BOT_SHARE, GOOD_BOT_SHARE = 0.025, 0.01
REGION_COUNTRIES = {"EU": (["FR", "DE", "ES", "GB", "IT", "NL", "PL"], [0.25, 0.2, 0.15, 0.15, 0.1, 0.1, 0.05]),
                    "US": (["US", "CA", "MX"], [0.88, 0.08, 0.04]), "APAC": (["JP", "SG", "KR", "AU", "IN"], [0.4, 0.2, 0.15, 0.15, 0.1]),
                    "LATAM": (["BR", "MX", "AR", "CL", "CO"], [0.5, 0.2, 0.12, 0.1, 0.08])}
HOURLY = np.array([2, 1.2, 0.8, 0.6, 0.6, 0.9, 1.8, 3.2, 4.5, 5.2, 5.6, 5.9, 6.3, 6.1, 5.8, 5.6, 5.5, 5.7, 6.0, 6.6, 6.9, 6.4, 5.0, 3.4])
HOURLY = HOURLY / HOURLY.sum()

# ----------------------------------------------------------------------------------------------- hidden events
CHROME_DRIFT = {"major": 155, "start": "2026-09-23", "fix": "2026-10-02", "fn_factor": 3.0}
IOS_ISSUE = {"major": 27, "start": "2026-09-14", "fix": "2026-10-07", "fp_mean": 0.05, "score_factor": 0.6}
C09_CAMPAIGN = {"date": "2026-10-12", "incognito_after": 0.22}
PIPELINE = {"dup_customer": "C05", "dup_date": "2026-10-27", "dup_share": 0.35, "late_date": "2026-10-28", "late_days": 2}
P01_BOTS = {"start": "2026-11-05", "end": "2026-11-12", "bad_share": 0.45}
C03_BLOCKED_SHARE = 0.09   # requests blocked by ad blockers without a proxy integration (assumption)
C07_AGENTS = {"devices": 40, "networks": 3, "events_per_day": 55}
MODEL_RELEASES = [
    ("m2026.08.31", "2026-08-31", "Routine retraining", None),
    ("m2026.10.02", "2026-10-02", "Fix: signal change in Chrome 155 caused returning visitors to be seen as new", "Chrome 155"),
    ("m2026.10.07", "2026-10-07", "Recalibration of the iOS 27 Mobile Safari segment (confidence and matching)", "iOS 27"),
    ("m2026.11.10", "2026-11-10", "Routine retraining", None),
]


def load_calendar():
    rel = pd.read_csv(PROC / "browser_releases.csv", dtype=str)
    rel = rel[~rel["first_stable_build"].str.contains("latest")]
    rel["release_date"] = pd.to_datetime(rel["release_date"])
    cal = json.loads((PROC / "adoption_calibration.json").read_text())
    return rel, cal


def uptake(days_since: np.ndarray, curve: dict) -> np.ndarray:
    """Share of a family already on a version (or newer) `days_since` days after its release: linear interpolation of
    the real Wikimedia median curve (week k measured at day 7k), flat after week 12."""
    weeks = np.array(sorted(int(k) for k in curve))
    vals = np.array([curve[str(k)] for k in weeks])
    return np.where(days_since < 0, 0.0, np.interp(days_since / 7.0, weeks, vals))


def version_for(dates: pd.Series, lag_u: np.ndarray, family: str, rel: pd.DataFrame, cal: dict) -> np.ndarray:
    """Major version of each event: the newest release whose uptake at that date exceeds the device's update lag u
    (u ~ U(0,1): u small = updates fast). Devices never updated stay on the version before the window."""
    if family in ("Chrome", "Chrome Mobile", "Edge"):
        r = rel[rel["browser"] == "Chrome"].sort_values("release_date"); curve = cal["Chrome"]["median_uptake_by_week"]
    elif family == "Firefox":
        r = rel[rel["browser"] == "Firefox"].sort_values("release_date"); curve = cal["Firefox"]["median_uptake_by_week"]
    elif family in ("Mobile Safari", "Safari", "Native iOS"):
        r = rel[(rel["browser"] == "iOS") & (rel["release_date"] >= "2024-01-01")].sort_values("release_date")
        curve = cal["Mobile Safari"]["median_uptake_by_week"]
    else:
        return np.full(len(dates), 29)  # Samsung Internet / Android apps: version not modelled (assumption)
    r = r[r["release_date"] <= pd.Timestamp(END)]
    out = np.full(len(dates), int(r.iloc[0]["major"]))
    d = dates.values.astype("datetime64[D]")
    for _, row in r.iterrows():
        since = (d - np.datetime64(row["release_date"].date())).astype(int)
        # Edge follows the Chromium milestone about 3 days later (assumption)
        if family == "Edge":
            since = since - 3
        # older versions (released > 12 weeks before) are treated as fully rolled out to their plateau
        on = uptake(since, curve) > lag_u
        out = np.where(on, int(row["major"]), out)
    return out


def hexids(rng, n, prefix):
    return pd.Series(rng.integers(0, 2**48, n, dtype=np.int64)).map(lambda x: f"{prefix}{x:012x}").values


def daily_volume(rng, cust, base):
    """Events per day: weekly seasonality (gaming peaks on weekends), small trend, noise, start date."""
    dow = DAYS.dayofweek.values
    if cust["sector"] == "Gaming":
        wf = np.array([0.92, 0.9, 0.92, 0.95, 1.05, 1.15, 1.11])
    else:
        wf = np.array([1.06, 1.07, 1.06, 1.04, 1.0, 0.89, 0.88])
    trend = 1 + 0.0006 * np.arange(len(DAYS))
    vol = base * wf[dow] * trend * rng.lognormal(0, 0.04, len(DAYS))
    start = pd.Timestamp(cust["start_date"])
    vol = np.where(DAYS < start, 0, vol)
    return np.round(vol).astype(int)


def simulate_customer(cust, rng, rel, cal, counters):
    cid = cust["customer_id"]
    vol = daily_volume(rng, cust, cust["avg_daily_events"])
    total = int(vol.sum())
    if total == 0:
        return None
    tz = ZoneInfo(cust["timezone"])
    established = pd.Timestamp(cust["start_date"]) < pd.Timestamp(START) - pd.Timedelta(days=60)

    # ---- device pool (humans)
    n_dev = max(2000, int(total / 7))
    fam = rng.choice(BROWSERS, n_dev, p=np.array(MIX[cust["traffic_mix"]]) / sum(MIX[cust["traffic_mix"]]))
    dev = pd.DataFrame({"fam": fam})
    dev["os"] = _vector_os(rng, fam)
    dev["weight"] = rng.lognormal(0, 1.1, n_dev)
    # persistent device-level difficulty (mean 1): a device in a crowd of look-alikes is mismatched again and again,
    # a device that wipes its storage is split again and again -> events of one device are correlated
    dev["fp_factor"] = rng.lognormal(-DEVICE_SIGMA_FP**2 / 2, DEVICE_SIGMA_FP, n_dev)
    dev["fn_factor"] = rng.lognormal(-DEVICE_SIGMA_FN**2 / 2, DEVICE_SIGMA_FN, n_dev)
    dev["lag_u"] = rng.uniform(0, 1, n_dev)
    dev["vpn"] = rng.random(n_dev) < VPN_DEVICE_SHARE
    dev["prior_seen"] = rng.random(n_dev) < (0.72 if established else 0.0)
    birth = rng.integers(0, len(DAYS), n_dev)
    start_idx = max(0, (pd.Timestamp(cust["start_date"]) - pd.Timestamp(START)).days)
    if not established:
        # a customer that goes live brings its existing users at once: 60% of devices show up in the first week
        early = rng.random(n_dev) < 0.6
        birth = np.where(early, start_idx + rng.integers(0, 7, n_dev), birth)
    birth = np.maximum(birth, start_idx)
    dev["birth"] = np.where(dev["prior_seen"], 0, birth)
    ctry, cp = REGION_COUNTRIES[cust["region"]]
    dev["country"] = rng.choice(ctry, n_dev, p=cp)
    dev["net"] = rng.integers(0, 2**40, n_dev)          # home /24 network (simulated), hashed later
    dev["tablet"] = (dev["fam"].isin(["Mobile Safari", "Native iOS"])) & (rng.random(n_dev) < 0.1)
    dev["kind"] = "human"
    # accounts: one owner account per device; some people use 2 devices (phone + laptop) -> pool smaller than devices
    n_acc = int(n_dev * 0.8)
    dev["account"] = rng.integers(0, n_acc, n_dev)
    dev["account2"] = -1
    if cid == "C07":
        fam_shared = rng.random(n_dev) < 0.06              # family devices: a second account logs in from them
        dev.loc[fam_shared, "account2"] = rng.integers(0, n_acc, fam_shared.sum())

    # ---- events of human devices, day by day
    parts = []
    for i, day in enumerate(DAYS):
        n = vol[i]
        if n == 0:
            continue
        n_bad = int(round(n * BAD_BOT_SHARE)); n_good = int(round(n * GOOD_BOT_SHARE))
        if cid == "P01" and P01_BOTS["start"] <= day.strftime("%Y-%m-%d") <= P01_BOTS["end"]:
            n_bad = int(round(n * P01_BOTS["bad_share"] / (1 - P01_BOTS["bad_share"])))
        n_h = n - int(round(n * BAD_BOT_SHARE)) - n_good
        active = np.flatnonzero(dev["birth"].values <= i)
        w = dev["weight"].values[active]
        idx = rng.choice(active, n_h, p=w / w.sum())
        hours = rng.choice(24, n_h, p=HOURLY)
        parts.append(pd.DataFrame({"dev": idx, "day_i": i, "hour": hours, "kind": 0}))
        parts.append(pd.DataFrame({"dev": -1, "day_i": i, "hour": rng.integers(0, 24, n_bad), "kind": 1}))
        parts.append(pd.DataFrame({"dev": -2, "day_i": i, "hour": rng.integers(0, 24, n_good), "kind": 2}))
    ev = pd.concat(parts, ignore_index=True)

    # ---- bots: their own small device pools (true devices), Chrome on Linux/Windows, data-centre networks
    n_botdev = 300
    nb, ng = (ev["kind"] == 1).sum(), (ev["kind"] == 2).sum()
    bot_dev = pd.DataFrame({"fam": "Chrome", "os": rng.choice(["Linux", "Windows"], 2 * n_botdev, p=[0.7, 0.3]),
                            "weight": 1.0, "fp_factor": 1.0, "fn_factor": 1.0, "lag_u": rng.uniform(0, 1, 2 * n_botdev), "vpn": rng.random(2 * n_botdev) < 0.6,
                            "prior_seen": False, "birth": 0, "country": rng.choice(ctry, 2 * n_botdev, p=cp),
                            "net": rng.integers(0, 50, 2 * n_botdev), "tablet": False,
                            "kind": ["bad"] * n_botdev + ["good"] * n_botdev,
                            "account": rng.integers(0, n_acc, 2 * n_botdev), "account2": -1})
    base_n = len(dev)
    dev = pd.concat([dev, bot_dev], ignore_index=True)
    ev.loc[ev["kind"] == 1, "dev"] = base_n + rng.integers(0, n_botdev, nb)
    ev.loc[ev["kind"] == 2, "dev"] = base_n + n_botdev + rng.integers(0, n_botdev, ng)

    # ---- C07 call-centre agents: 40 desktop devices on 3 office networks, logging into many customer accounts
    if cid == "C07":
        a = C07_AGENTS
        ag = pd.DataFrame({"fam": "Chrome", "os": "Windows", "weight": 1.0, "fp_factor": 1.0, "fn_factor": 1.0, "lag_u": rng.uniform(0, 1, a["devices"]),
                           "vpn": False, "prior_seen": True, "birth": 0, "country": "ES",
                           "net": 10**12 + rng.integers(0, a["networks"], a["devices"]), "tablet": False, "kind": "agent",
                           "account": -1, "account2": -1})
        ag_base = len(dev)
        dev = pd.concat([dev, ag], ignore_index=True)
        rows = []
        for i, day in enumerate(DAYS):
            if day.dayofweek >= 5:
                continue
            n = a["events_per_day"] * a["devices"]
            rows.append(pd.DataFrame({"dev": ag_base + rng.integers(0, a["devices"], n), "day_i": i,
                                      "hour": rng.choice(np.arange(8, 19), n), "kind": 3}))
        ev = pd.concat([ev, pd.concat(rows)], ignore_index=True)

    # ---- C03: sessions blocked by ad blockers (no proxy integration) exist on the customer side only
    if cid == "C03":
        ev["blocked"] = rng.random(len(ev)) < C03_BLOCKED_SHARE
    else:
        ev["blocked"] = False

    # ---- timestamps: local hour of the customer's time zone -> UTC
    n = len(ev)
    local_naive = DAYS.values[ev["day_i"].values] + ev["hour"].values.astype("timedelta64[h]") + rng.integers(0, 3600, n).astype("timedelta64[s]")
    ts = pd.DatetimeIndex(local_naive).tz_localize(tz, ambiguous=np.zeros(n, dtype=bool), nonexistent="shift_forward").tz_convert(UTC)
    ev["ts"] = ts
    ev = ev[ev["ts"].notna()]
    ev = ev[(ev["ts"] >= pd.Timestamp(START, tz=UTC)) & (ev["ts"] < pd.Timestamp(END + dt.timedelta(days=1), tz=UTC))]
    ev = ev.sort_values(["ts"]).reset_index(drop=True)
    n = len(ev)

    d = dev.iloc[ev["dev"].values].reset_index(drop=True)
    ev["fam"] = d["fam"].values
    ev["os"] = d["os"].values
    seq = ev.groupby("dev").cumcount().values
    ev["seen_before"] = d["prior_seen"].values | (seq > 0)
    date_utc = ev["ts"].dt.tz_localize(None).dt.normalize()
    ev["major"] = 0
    for f in ev["fam"].unique():
        m = (ev["fam"] == f).values
        ev.loc[m, "major"] = version_for(date_utc[m], d["lag_u"].values[m], f, rel, cal)

    kind = d["kind"].values
    is_bad, is_good, is_agent = kind == "bad", kind == "good", kind == "agent"
    inc_rate = np.full(n, INCOGNITO.get(cid, DEFAULT_INCOGNITO))
    if cid == "C09":
        camp = pd.Timestamp(C09_CAMPAIGN["date"], tz=UTC)
        ramp = np.clip((ev["ts"] - camp).dt.total_seconds().values / (2 * 86400), 0, 1)
        inc_rate = inc_rate + ramp * (C09_CAMPAIGN["incognito_after"] - inc_rate)
    incog = (rng.random(n) < inc_rate) & ~is_bad & ~is_good & ~is_agent & ~ev["fam"].str.startswith("Native").values
    vpn = d["vpn"].values & (rng.random(n) < 0.7)

    # ---- probabilities of the probabilistic answer
    fp_base = ev["fam"].map(lambda f: SEG[f][0]).values
    fn = ev["fam"].map(lambda f: SEG[f][1]).values.copy()
    cookie = ev["fam"].map(lambda f: SEG[f][2]).values.copy()
    ts_np = ev["ts"].dt.tz_localize(None).values
    # version age: in the first 7 days after a release the model is slightly less sure (normal adaptation, FN x1.25)
    age = version_age_days(ev, rel)
    fn = fn * np.where((age >= 0) & (age <= 7), 1.25, 1.0)
    in_chrome = ev["fam"].isin(["Chrome", "Chrome Mobile"]).values & (ev["major"].values == CHROME_DRIFT["major"])
    in_chrome_window = (ts_np >= np.datetime64(CHROME_DRIFT["start"])) & (ts_np < np.datetime64(CHROME_DRIFT["fix"]))
    fn = np.where(in_chrome & in_chrome_window, fn * CHROME_DRIFT["fn_factor"], fn)
    ios_seg = (ev["fam"].values == "Mobile Safari") & (ev["major"].values == IOS_ISSUE["major"])
    ios_window = (ts_np >= np.datetime64(IOS_ISSUE["start"])) & (ts_np < np.datetime64(IOS_ISSUE["fix"]))
    fp_mean = np.where(ios_seg & ios_window, IOS_ISSUE["fp_mean"], fp_base)
    fp_mean = fp_mean * np.where(incog, 1.5, 1.0) * np.where(vpn, 1.3, 1.0) * np.where(is_bad, 2.0, 1.0)
    fn = fn * np.where(incog, 3.0, 1.0) * np.where(vpn, 1.5, 1.0)
    fn = np.where(is_bad, 0.6, fn)
    risk = np.clip(fp_mean * d["fp_factor"].values * rng.lognormal(-RISK_SIGMA**2 / 2, RISK_SIGMA, n), 0, 0.6)
    fn = fn * d["fn_factor"].values
    fn = np.clip(fn, 0, 0.95 - risk)
    cookie = np.where(is_bad, 0.3, np.where(is_good, 0.1, cookie))
    cookie = np.where(is_agent, 0.97, cookie)

    deterministic = ev["seen_before"].values & ~incog & (rng.random(n) < cookie)
    u = rng.random(n)
    seen = ev["seen_before"].values
    out = np.where(seen, np.where(u < risk, "FP", np.where(u < risk + fn, "FN", "TP")), np.where(u < risk, "FP", "TN"))

    # ---- visitor ids: canonical id per true device; FP -> canonical id of another device of the same browser family
    canon = hexids(rng, len(dev), "V")
    dev_idx = ev["dev"].values
    prob_vid = canon[dev_idx].copy()
    fp_m = out == "FP"
    if fp_m.any():
        fams = ev["fam"].values
        human_by_fam = {f: np.flatnonzero((dev["fam"].values == f) & (dev["kind"].values == "human")) for f in BROWSERS}
        for f in np.unique(fams[fp_m]):
            m = fp_m & (fams == f)
            pool = human_by_fam.get(f)
            if pool is None or len(pool) < 2:
                pool = np.flatnonzero(dev["kind"].values == "human")
            pick = pool[rng.integers(0, len(pool), m.sum())]
            pick = np.where(pick == dev_idx[m], pool[(np.searchsorted(pool, pick) + 1) % len(pool)], pick)
            prob_vid[m] = canon[pick]
    # FN: a returning device gets a brand-new id (it is split off). TN: a genuinely new device gets ITS id, which the
    # platform then keeps returning on later visits (canonical id), so a TN does not create a second visitor.
    new_m = out == "FN"
    prob_vid[new_m] = hexids(rng, new_m.sum(), "V")
    prob_found = (out == "TP") | (out == "FP")

    # ---- confidence score = 1 - estimated FP probability (calibrated, except the iOS 27 segment before its fix)
    believed = np.where(ios_seg & ios_window, risk * IOS_ISSUE["score_factor"], risk)
    score = np.clip(1 - believed + rng.normal(0, 0.003, n), 0, 1)
    score = np.where(prob_found, score, 1.0)

    vid = np.where(deterministic, canon[dev_idx], prob_vid)
    found = np.where(deterministic, True, prob_found)
    # deterministic answers cannot be a false positive: confidence 1.0, as Fingerprint documents. (The draw below is
    # unused; it is kept so that the random stream of seed 42, and every later number, stays the same.)
    _unused = rng.normal(0.997, 0.002, n)
    conf = np.where(deterministic, 1.0, score)

    # ---- linked ids (customer account ids), sent on login-type events
    acc_prefix = f"ACC{cid[1:]}"
    has_link = rng.random(n) < cust["linked_id_share"]
    acc = d["account"].values.copy()
    acc2 = d["account2"].values
    acc = np.where((acc2 >= 0) & (rng.random(n) < 0.45), acc2, acc)
    acc = np.where(is_agent, rng.integers(0, n_dev, n), acc)                # agents open many customer accounts
    acc = np.where(is_bad, rng.integers(0, n_dev, n), acc)                  # robots try many accounts
    has_link = has_link | (is_agent & (cust["linked_id_share"] > 0)) | (is_bad & (cid == "P01"))
    linked = np.where(has_link & (acc >= 0), pd.Series(acc).map(lambda x: f"{acc_prefix}{x:07d}").values, None)

    bot_result = np.where(is_good, "good", np.where(is_bad & (rng.random(n) < 0.9), "bad", "notDetected"))
    net = d["net"].values
    vpn_net = rng.integers(0, 200, n) + 5 * 10**12
    ip_hash = pd.Series(np.where(vpn, vpn_net, net)).map(lambda x: f"IP{(x * 2654435761) % 2**40:010x}").values
    fam = ev["fam"].values
    sdk = np.where(fam == "Native iOS", "ios", np.where(fam == "Native Android", "android", "js"))
    sdk_version = np.where(sdk == "js", rng.choice(["js-3.11", "js-3.12"], n, p=[0.3, 0.7]),
                           np.where(sdk == "ios", "ios-2.8", "android-2.8"))
    device_type = np.where(fam_is_mobile(fam), np.where(d["tablet"].values, "tablet", "mobile"), "desktop")
    os_major = np.where(np.isin(fam, ["Mobile Safari", "Native iOS", "Safari"]), ev["major"].values, 0)

    ev_id = np.arange(counters["event"], counters["event"] + n)
    counters["event"] += n
    events = pd.DataFrame({
        "event_id": pd.Series(ev_id).map(lambda x: f"E{x:010d}").values,
        "ts_utc": ev["ts"].dt.tz_localize(None).values,
        "customer_id": cid,
        "visitor_id": vid,
        "visitor_found": found,
        "confidence_score": np.round(conf, 4),
        "method": np.where(deterministic, "deterministic", "probabilistic"),
        "probabilistic_visitor_id": np.where(deterministic, prob_vid, None),
        "probabilistic_visitor_found": np.where(deterministic, prob_found, None),
        "browser": fam,
        "browser_major": ev["major"].values.astype(int),
        "os": ev["os"].values,
        "os_major": os_major.astype(int),
        "device_type": device_type,
        "is_incognito": incog,
        "is_vpn": vpn,
        "bot_result": bot_result,
        "ip_hash": ip_hash,
        "country": np.where(vpn, rng.choice(["NL", "US", "DE", "SG"], n), d["country"].values),
        "sdk": sdk,
        "sdk_version": sdk_version,
        "proxy_integration": bool(cust["proxy_integration"]),
        "linked_id": linked,
        "is_internal_agent": None,   # never filled by the customer: has to be inferred (int_internal_traffic)
    })
    truth = pd.DataFrame({"event_id": events["event_id"].values, "true_device_id": pd.Series(dev_idx).map(lambda x: f"D{cid}{x:07d}").values,
                          "true_visitor_id": canon[dev_idx], "device_seen_before": seen, "true_outcome_probabilistic": out,
                          "true_is_internal_agent": is_agent, "true_is_bad_bot": is_bad})
    blocked = ev["blocked"].values
    return events, truth, blocked


def version_age_days(ev, rel):
    """Days between the event and the real release date of its browser major version (-1 when unknown)."""
    cal_of = {"Chrome": "Chrome", "Chrome Mobile": "Chrome", "Edge": "Chrome", "Firefox": "Firefox",
              "Mobile Safari": "iOS", "Safari": "iOS", "Native iOS": "iOS"}
    lookup = {(b, int(m)): d for b, m, d in zip(rel["browser"], rel["major"], rel["release_date"])}
    keys = zip(ev["fam"].map(cal_of).values, ev["major"].values)
    rd = pd.to_datetime(pd.Series([lookup.get((c, int(m))) for c, m in keys], dtype="object"))
    age = (ev["ts"].dt.tz_localize(None).dt.normalize().values - rd.values).astype("timedelta64[D]").astype(float)
    return np.nan_to_num(age, nan=-1.0)


def fam_is_mobile(fam):
    return np.isin(fam, ["Chrome Mobile", "Mobile Safari", "Samsung Internet", "Native iOS", "Native Android"])


def _vector_os(rng, fam):
    out = np.empty(len(fam), dtype=object)
    for f, (oss, ps) in OS_OF.items():
        m = fam == f
        out[m] = rng.choice(oss, m.sum(), p=ps)
    return out


def write_partitions(events, truth, rng, ingestion):
    events["event_date"] = events["ts_utc"].dt.normalize()
    truth = truth.assign(event_date=events["event_date"].values)   # same row order as events
    cid = events["customer_id"].iloc[0]
    for day, g in events.groupby("event_date"):
        dstr = day.strftime("%Y-%m-%d")
        g = g.copy()
        batch_loaded = day + pd.Timedelta(days=1, hours=2, minutes=int(rng.integers(0, 50)))
        if dstr == PIPELINE["late_date"]:
            batch_loaded = batch_loaded + pd.Timedelta(days=PIPELINE["late_days"])
        g["loaded_at"] = batch_loaded
        rows_sent = len(g)
        if cid == PIPELINE["dup_customer"] and dstr == PIPELINE["dup_date"]:
            dup = g.sample(frac=PIPELINE["dup_share"], random_state=SEED).copy()
            dup["loaded_at"] = batch_loaded + pd.Timedelta(hours=3, minutes=40)   # re-sent after an upstream error
            g = pd.concat([g, dup], ignore_index=True)
        out = SIM / "identification_events" / f"event_date={dstr}"
        out.mkdir(parents=True, exist_ok=True)
        g.drop(columns=["event_date"]).to_parquet(out / f"{cid}.parquet", index=False)
        tout = SIM / "device_truth" / f"event_date={dstr}"
        tout.mkdir(parents=True, exist_ok=True)
        truth[truth["event_date"] == day].drop(columns=["event_date"]).to_parquet(tout / f"{cid}.parquet", index=False)
        ingestion.append({"partition_date": dstr, "customer_id": cid, "rows_sent": rows_sent, "rows_loaded": len(g),
                          "loaded_at": g["loaded_at"].max()})


def request_queue(rng, customers):
    """140 internal requests to the accuracy analyst over the 13 weeks (CS 60%, SE 25%, Product 15%)."""
    arr = dict(zip(customers["customer_id"], customers["arr_usd_simulated"]))
    seeded = [  # requests tied to the hidden events (opened a few days after the symptom appears)
        ("2026-09-28", "CS", "false_positive", "C02", "Our users receive more one-time codes since mid-September", "high", "investigation"),
        ("2026-09-29", "SE", "false_negative", "C05", "Returning customers flagged as new visitors on Chrome", "medium", "investigation"),
        ("2026-10-14", "CS", "false_positive", "C07", "One visitor ID groups hundreds of our accounts", "high", "custom_metric"),
        ("2026-10-21", "Product", "method_question", None, "Weekly FP rate is up 30% on the global dashboard: model regression?", "critical", "investigation"),
        ("2026-10-23", "CS", "false_negative", "C09", "Accuracy looks worse since our acquisition campaign", "medium", "investigation"),
        ("2026-10-30", "CS", "report", "C05", "Daily volume chart shows a hole then a spike for late October", "medium", "investigation"),
        ("2026-11-04", "CS", "reconciliation", "C03", "Our session count is far above your billed identifications", "high", "reconciliation"),
        ("2026-11-10", "SE", "poc", "P01", "POC: visitors per account exploded this week, is identification failing?", "critical", "poc_report"),
    ]
    rows = []
    for o, team, typ, cid, title, urg, tmpl in seeded:
        rows.append({"opened_at": pd.Timestamp(o) + pd.Timedelta(hours=int(rng.integers(8, 18))), "requesting_team": team,
                     "request_type": typ, "customer_id": cid, "title": title, "urgency": urg, "question_template": tmpl,
                     "linked_hidden_event": True})
    teams = rng.choice(["CS", "SE", "Product"], 132, p=[0.60, 0.25, 0.15])
    templates = {
        "CS": (["standard_accuracy_question", "trend_question", "investigation", "custom_metric", "report"], [0.35, 0.2, 0.2, 0.1, 0.15]),
        "SE": (["poc_report", "standard_accuracy_question", "investigation", "custom_metric"], [0.4, 0.3, 0.2, 0.1]),
        "Product": (["trend_question", "method_question", "investigation", "report"], [0.3, 0.35, 0.2, 0.15]),
    }
    type_of = {"standard_accuracy_question": ["report", "method_question"], "trend_question": ["report", "false_positive", "false_negative"],
               "investigation": ["false_positive", "false_negative"], "custom_metric": ["report"], "report": ["report"],
               "poc_report": ["poc"], "method_question": ["method_question"], "reconciliation": ["reconciliation"]}
    custs = customers["customer_id"].tolist()
    for t in teams:
        tmpl = rng.choice(templates[t][0], p=templates[t][1])
        typ = rng.choice(type_of[tmpl])
        cid = None if (t == "Product" and rng.random() < 0.6) else rng.choice(custs[:12] if tmpl != "poc_report" else ["P01", "P02"])
        opened = pd.Timestamp(START) + pd.Timedelta(minutes=int(rng.integers(0, 91 * 24 * 60)))
        if cid in ("P01", "P02"):
            opened = max(opened, pd.Timestamp(customers.set_index("customer_id").loc[cid, "start_date"]))
        if cid == "C12":
            opened = max(opened, pd.Timestamp("2026-10-19"))
        urg = rng.choice(["low", "medium", "high", "critical"], p=[0.3, 0.42, 0.22, 0.06])
        rows.append({"opened_at": opened, "requesting_team": t, "request_type": typ, "customer_id": cid,
                     "title": f"{tmpl.replace('_', ' ').capitalize()}", "urgency": urg, "question_template": tmpl, "linked_hidden_event": False})
    q = pd.DataFrame(rows).sort_values("opened_at").reset_index(drop=True)
    q["request_id"] = [f"REQ-{i + 1:03d}" for i in range(len(q))]
    effort_med = {"standard_accuracy_question": 1.0, "trend_question": 2.0, "investigation": 6.0, "custom_metric": 5.0,
                  "report": 3.0, "poc_report": 8.0, "method_question": 1.5, "reconciliation": 7.0}
    q["effort_hours"] = np.round(q["question_template"].map(effort_med) * rng.lognormal(0, 0.45, len(q)), 1)
    wait_med = {"critical": 0.3, "high": 1.0, "medium": 3.0, "low": 6.0}
    days = q["urgency"].map(wait_med) * rng.lognormal(0, 0.6, len(q)) + q["effort_hours"] / 6
    q["resolved_at"] = q["opened_at"] + pd.to_timedelta(np.round(days * 24, 1), unit="h")
    q.loc[q["resolved_at"] > pd.Timestamp(END) + pd.Timedelta(hours=23), "resolved_at"] = pd.NaT
    q["arr_at_stake_usd"] = q["customer_id"].map(arr).fillna(0).astype(int)
    return q[["request_id", "opened_at", "resolved_at", "requesting_team", "request_type", "question_template", "customer_id",
              "arr_at_stake_usd", "urgency", "effort_hours", "title", "linked_hidden_event"]]


def main():
    rng = np.random.default_rng(SEED)
    if SIM.exists():
        shutil.rmtree(SIM)
    SIM.mkdir(parents=True)
    rel, cal = load_calendar()
    customers = pd.DataFrame(CUSTOMERS, columns=COLS)
    customers.drop(columns=["avg_daily_events", "traffic_mix"]).to_parquet(SIM / "customers.parquet", index=False)
    counters = {"event": 1}
    ingestion = []
    c03_local = None
    c07_pairs = None
    n_total = 0
    for _, cust in customers.iterrows():
        res = simulate_customer(cust, rng, rel, cal, counters)
        if res is None:
            continue
        events, truth, blocked = res
        if cust["customer_id"] == "C03":
            # the customer's own export counts every session, including those whose identification request was
            # blocked (no proxy integration), by LOCAL day; blocked requests never reach the platform
            tz = ZoneInfo(cust["timezone"])
            local_day = events["ts_utc"].dt.tz_localize(UTC).dt.tz_convert(tz).dt.date
            ex = pd.DataFrame({"local_date": local_day, "has_vid": ~blocked})
            exp = ex.groupby("local_date").agg(sessions=("has_vid", "size"), sessions_with_visitor_id=("has_vid", "sum")).reset_index()
            # their sessions table double-counts a few page reloads (unexplained residual, ~0.15%)
            extra = rng.binomial(exp["sessions_with_visitor_id"], 0.0015)
            exp["sessions"] += extra
            exp["sessions_with_visitor_id"] += extra
            c03_local = exp
            events, truth = events[~blocked].reset_index(drop=True), truth[~blocked].reset_index(drop=True)
        if cust["customer_id"] == "C07":
            lk = events[events["linked_id"].notna()]
            c07_pairs = lk.groupby(["linked_id", "visitor_id"]).agg(first_seen=("ts_utc", "min"), last_seen=("ts_utc", "max"),
                                                                      logins=("event_id", "size")).reset_index()
            c07_pairs = c07_pairs.rename(columns={"linked_id": "account_id"})
        write_partitions(events, truth, rng, ingestion)
        n_total += len(events)
        print(f"{cust['customer_id']}: {len(events):,} events")

    pd.DataFrame(ingestion).to_parquet(SIM / "ingestion_log.parquet", index=False)
    pd.DataFrame(MODEL_RELEASES, columns=["model_version", "release_date", "change", "segment"]).to_parquet(SIM / "model_releases.parquet", index=False)
    br = pd.read_csv(PROC / "browser_releases.csv", dtype=str)
    br.to_parquet(SIM / "browser_releases.parquet", index=False)
    request_queue(rng, customers).to_parquet(SIM / "request_queue.parquet", index=False)
    ex_dir = SIM / "customer_exports"
    ex_dir.mkdir(exist_ok=True)
    c03_local.to_csv(ex_dir / "C03_sessions_export.csv", index=False)
    c07_pairs.to_csv(ex_dir / "C07_accounts_export.csv", index=False)

    hidden = pd.DataFrame([
        (1, "Chrome drift", "all", f"FN x{CHROME_DRIFT['fn_factor']:.0f} on Chrome/Chrome Mobile {CHROME_DRIFT['major']}", CHROME_DRIFT["start"], CHROME_DRIFT["fix"], "real Chrome 155 stable date (chromiumdash); fix = model m2026.10.02"),
        (2, "iOS 27 false positives", "C02 (and all iPhone Safari traffic)", "true FP ~5% on Mobile Safari iOS 27, confidence overstated (x0.6 of the risk)", IOS_ISSUE["start"], IOS_ISSUE["fix"], "real iOS 27 date (endoflife.date); fix = model m2026.10.07"),
        (3, "Shared devices and call-centre agents", "C07", f"{C07_AGENTS['devices']} agent devices on {C07_AGENTS['networks']} networks + 6% family devices", "2026-08-24", "2026-11-22", "not a false positive"),
        (4, "Reconciliation", "C03", f"no proxy integration: {C03_BLOCKED_SHARE:.0%} of requests blocked; export by local day (America/New_York, DST change 2026-11-01)", "2026-08-24", "2026-11-22", "customer export in data/sim/customer_exports"),
        (5, "Pipeline issues", "C05 + all", f"C05 {PIPELINE['dup_share']:.0%} duplicated on {PIPELINE['dup_date']}; partition {PIPELINE['late_date']} loaded {PIPELINE['late_days']} days late", PIPELINE["dup_date"], "2026-10-30", "caught by dbt tests, fixed by incremental lookback"),
        (6, "Robots in a POC", "P01", f"bad robots = {P01_BOTS['bad_share']:.0%} of P01 traffic", P01_BOTS["start"], P01_BOTS["end"], "segment bots in POC reports"),
        (7, "Incognito mix shift", "C09", f"incognito share {INCOGNITO['C09']:.0%} -> {C09_CAMPAIGN['incognito_after']:.0%}", C09_CAMPAIGN["date"], "2026-11-22", "measurement bias: control set excludes incognito"),
        (8, "FALSE SIGNAL: new customer mix", "C12", "C12 (mobile marketplace) starts; per-segment rates unchanged", "2026-10-19", "2026-11-22", "do not open a model incident"),
    ], columns=["event_no", "name", "customers", "mechanism", "start", "end", "note"])
    hidden.to_csv(ROOT / "data" / "_hidden_truth.csv", index=False)
    print(f"total events: {n_total:,}")


if __name__ == "__main__":
    main()
