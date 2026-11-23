"""Turn the cached raw public files (data/raw/, never published) into small, publishable extracts in data/processed/.

Called by `python src/fetch_public.py` after the downloads. No network access here.

Outputs
- browser_releases.csv            real release calendar (Chrome first stable build per milestone, Firefox majors, iOS)
- browser_release_checks.json     consistency checks of the Chrome feed (version vs milestone vs date, repeated builds)
- wikimedia_browser_share.csv     browser-family shares of Wikimedia page views, last available week
- wikimedia_adoption_curves.csv   share of a new major version among its family, by week since the official release
- adoption_calibration.json       median uptake curve (share on version >= v) per family + logistic fit (used by simulate_platform.py)
- wikimedia_unique_devices.csv    daily unique devices on en.wikipedia (cookie-based count + offset correction)
- fingerprint_public_facts.json   facts from the job post, careers API and the open-source repository
- fingerprintjs_releases_per_year.csv  releases of the open-source library per year (GitHub API)
"""
import datetime as dt
import html
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
READ_ON = "2026-11-23"


def load_json(name):
    return json.loads((RAW / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- release calendars
def chrome_releases():
    rows = pd.DataFrame(load_json("chrome_releases.json"))
    rows["released_at"] = pd.to_datetime(rows["time"], unit="ms", utc=True)
    rows["major_from_version"] = rows["version"].str.split(".").str[0].astype(int)
    checks = {
        "builds_in_feed": int(len(rows)),
        "milestone_equals_version_major": bool((rows["milestone"] == rows["major_from_version"]).all()),
        "repeated_version_strings": int(rows["version"].duplicated().sum()),
        "first_build": rows.sort_values("released_at").iloc[0]["version"],
        "last_build": rows.sort_values("released_at").iloc[-1]["version"],
    }
    # a newer milestone must never be released before an older one (first stable build per milestone)
    first = rows.sort_values("released_at").groupby("milestone", as_index=False).first()
    checks["first_build_dates_increase_with_milestone"] = bool(first.sort_values("milestone")["released_at"].is_monotonic_increasing)
    # the feed starts mid-way through the oldest milestone: its "first" build is not its real release
    checks["oldest_milestone_dropped_as_incomplete"] = int(first["milestone"].min())
    first = first[first["milestone"] > first["milestone"].min()]
    out = pd.DataFrame({"browser": "Chrome", "major": first["milestone"].astype(str),
                        "release_date": first["released_at"].dt.date.astype(str),
                        "first_stable_build": first["version"],
                        "source": "chromiumdash.appspot.com fetch_releases (Stable, Windows)"})
    return out, checks


def firefox_releases():
    d = load_json("firefox_major.json")
    out = pd.DataFrame({"browser": "Firefox", "major": [k.split(".")[0] for k in d], "release_date": list(d.values()),
                        "first_stable_build": list(d.keys()), "source": "product-details.mozilla.org"})
    return out


def ios_releases():
    rel = load_json("ios.json")["result"]["releases"]
    rows = []
    for r in rel:
        rows.append({"browser": "iOS", "major": r["name"], "release_date": r["releaseDate"], "first_stable_build": r["name"] + ".0",
                     "source": "endoflife.date api v1"})
        if r.get("latest") and r["latest"]["name"] != r["name"]:
            rows.append({"browser": "iOS", "major": r["name"], "release_date": r["latest"]["date"],
                         "first_stable_build": r["latest"]["name"] + " (latest)", "source": "endoflife.date api v1 (latest)"})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- Wikimedia
FAMILY_FOR_CURVE = {"Chrome": "Chrome", "Firefox": "Firefox", "iOS": "Mobile Safari"}


def wikimedia(releases: pd.DataFrame):
    w = pd.read_csv(RAW / "wikimedia_browsers.tsv", sep="\t", dtype={"browser_major": str, "os_major": str})
    w["date"] = pd.to_datetime(w["date"])
    last = w["date"].max()
    lw = w[w["date"] == last].groupby("browser_family")["view_count"].sum().sort_values(ascending=False)
    share = (lw / lw.sum()).rename("share").reset_index()
    top = share.head(8).copy()
    other = pd.DataFrame({"browser_family": ["Other"], "share": [1 - top["share"].sum()]})
    share_out = pd.concat([top, other], ignore_index=True)
    share_out["week_start"] = last.date().isoformat()

    curves = []
    for rel_browser, family in FAMILY_FOR_CURVE.items():
        fam = w[w["browser_family"] == family]
        tot = fam.groupby("date")["view_count"].sum()
        fam = fam.assign(major_num=pd.to_numeric(fam["browser_major"], errors="coerce"))  # 'Redacted' / '-' -> NaN
        rels = releases[(releases["browser"] == rel_browser) & (~releases["first_stable_build"].str.contains("latest"))].copy()
        rels["release_date"] = pd.to_datetime(rels["release_date"])
        rels = rels[(rels["release_date"] >= "2023-01-01") & (rels["release_date"] <= last)]
        for _, r in rels.iterrows():
            for k in range(0, 13):
                wk = r["release_date"] + pd.Timedelta(days=7 * k)
                # Wikimedia weeks are labelled by their first day: take the week that contains release_date + 7k days
                week = tot.index[(tot.index <= wk) & (tot.index > wk - pd.Timedelta(days=7))]
                if len(week) == 0:
                    continue
                week = week[0]
                wk_rows = fam[fam["date"] == week]
                v = wk_rows.loc[wk_rows["major_num"] == int(r["major"]), "view_count"].sum()
                # "uptake" = share of the family already on this version OR A NEWER ONE: it only goes up, unlike the
                # share of the exact version, which falls again when the next release replaces it
                ge = wk_rows.loc[wk_rows["major_num"] >= int(r["major"]), "view_count"].sum()
                curves.append({"family": family, "major": r["major"], "release_date": r["release_date"].date().isoformat(),
                               "weeks_since_release": k, "week_start": week.date().isoformat(),
                               "share_of_family": v / tot[week], "uptake_share": ge / tot[week]})
    curves = pd.DataFrame(curves)

    def logistic(t, smax, t50, tau):
        return smax / (1 + np.exp(-(t - t50) / tau))

    calib = {}
    for fam, g in curves.groupby("family"):
        med = g.groupby("weeks_since_release")["uptake_share"].median()
        try:
            p, _ = curve_fit(logistic, med.index.values.astype(float), med.values, p0=[0.8, 2.0, 1.0], maxfev=20000)
            fit = {"smax": round(float(p[0]), 4), "t50_weeks": round(float(p[1]), 3), "tau_weeks": round(float(p[2]), 3)}
        except RuntimeError:
            fit = None
        if fit and not (0 < fit["smax"] <= 1):
            fit = None  # no plateau within 12 weeks (iOS updates slowly): use the median curve itself

        calib[fam] = {"versions": int(g["major"].nunique()),
                      "median_uptake_by_week": {int(k): round(float(v), 4) for k, v in med.items()},
                      "logistic_fit": fit}
    return share_out, curves, calib


def unique_devices():
    items = load_json("wikimedia_unique_devices.json")["items"]
    d = pd.DataFrame(items)[["timestamp", "devices", "offset", "underestimate"]]
    d["date"] = pd.to_datetime(d["timestamp"], format="%Y%m%d").dt.date.astype(str)
    d["offset_share"] = d["offset"] / d["devices"]
    return d[["date", "devices", "underestimate", "offset", "offset_share"]]


# ---------------------------------------------------------------- Fingerprint public facts
def fingerprint_facts():
    job = load_json("job.json")
    text = re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", html.unescape(job["content"])))
    jobs = load_json("jobs_list.json")["jobs"]
    repo = load_json("gh_repo.json")
    rel = load_json("gh_releases.json")
    rel_dates = sorted(r["published_at"][:10] for r in rel if not r.get("draft"))
    m = re.search(r"approximately ([0-9.,]+ (?:billion|million)) requests per month", text)
    sal = re.search(r"\$(\d+)k\s*-\s*\$(\d+)k", text)
    return {
        "read_on": READ_ON,
        "job": {"title": job["title"], "requisition_id": job.get("requisition_id"), "location": job["location"]["name"],
                "department": job["departments"][0]["name"], "first_published": job["first_published"],
                "updated_at": job["updated_at"], "url": "https://fingerprint.com/careers/jobs/apply/?gh_jid=6266169004",
                "api": "https://boards-api.greenhouse.io/v1/boards/fingerprint/jobs/6266169004",
                "requests_per_month_as_stated": m.group(1) if m else None,
                "us_salary_range_usd_k": [int(sal.group(1)), int(sal.group(2))] if sal else None,
                "years_experience_required": "3+" if "3+ years" in text else None,
                "on_call": "shared on-call rotation" in text},
        "careers": {"open_roles": len(jobs), "all_remote": all(j["location"]["name"].lower().startswith("remote") for j in jobs),
                    "titles": sorted(j["title"] for j in jobs)},
        "oss_repo": {"name": repo["full_name"], "stars": repo["stargazers_count"], "forks": repo["forks_count"],
                     "license": repo["license"]["spdx_id"], "releases": len(rel_dates), "first_release": rel_dates[0],
                     "latest_release": rel[0]["tag_name"], "latest_release_date": rel[0]["published_at"][:10],
                     "releases_last_12_months": sum(1 for d in rel_dates if d >= "2025-11-23")},
        "docs_read": {
            "accuracy": "https://docs.fingerprint.com/docs/identification-accuracy-and-confidence",
            "linked_id": "https://docs.fingerprint.com/docs/identify-visitors",
            "mcp_server": "https://docs.fingerprint.com/ai/mcp-server"},
    }


def main():
    PROC.mkdir(parents=True, exist_ok=True)
    chrome, checks = chrome_releases()
    releases = pd.concat([chrome, firefox_releases(), ios_releases()], ignore_index=True)
    releases.to_csv(PROC / "browser_releases.csv", index=False)
    (PROC / "browser_release_checks.json").write_text(json.dumps(checks, indent=2, default=str))
    share, curves, calib = wikimedia(releases)
    share.to_csv(PROC / "wikimedia_browser_share.csv", index=False)
    curves.to_csv(PROC / "wikimedia_adoption_curves.csv", index=False)
    (PROC / "adoption_calibration.json").write_text(json.dumps(calib, indent=2))
    unique_devices().to_csv(PROC / "wikimedia_unique_devices.csv", index=False)
    (PROC / "fingerprint_public_facts.json").write_text(json.dumps(fingerprint_facts(), indent=2))
    rel = pd.DataFrame(load_json("gh_releases.json"))
    rel = rel[~rel["draft"]].assign(year=lambda d: d["published_at"].str[:4])
    rel.groupby("year").size().rename("releases").reset_index().to_csv(PROC / "fingerprintjs_releases_per_year.csv", index=False)
    print("extracts written:", len(releases), "releases,", len(curves), "curve points")


if __name__ == "__main__":
    main()
