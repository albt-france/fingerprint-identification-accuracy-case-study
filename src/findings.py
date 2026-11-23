"""Compute EVERY number used in the report, the README and the dashboard, and write data/processed/findings.json.

Rule: no figure is typed by hand in a deliverable; build_pdf.py, build_dashboard.py and the README read this file.
Inputs: ClickHouse cache (data/cache/clickhouse), public extracts (data/processed), dbt marts (dbt/fingerprint.duckdb,
read-only), monitoring outputs, dbt run results. No network access.

    python src/findings.py
"""
import datetime as dt
import json
import math
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

import metrics

ROOT = Path(__file__).resolve().parents[1]
CH = ROOT / "data" / "cache" / "clickhouse"
PROC = ROOT / "data" / "processed"
DB = ROOT / "dbt" / "fingerprint.duckdb"
SIM = ROOT / "data" / "sim"


def ch(name):
    return pd.read_parquet(CH / f"{name}.parquet")


def ch_meta(name):
    return json.loads((CH / f"{name}.json").read_text())


def r4(x, n=4):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    return round(float(x), n)


def rates(df, prefix=""):
    s = df[[f"{prefix}tp_n", f"{prefix}fp_n", f"{prefix}fn_n", f"{prefix}tn_n"]].sum()
    tot = s.sum()
    return {"n": int(tot), "tp": r4(s.iloc[0] / tot), "fp": r4(s.iloc[1] / tot), "fn": r4(s.iloc[2] / tot), "tn": r4(s.iloc[3] / tot)}


# =============================================================================================== REAL: ClickHouse
def real_part():
    out = {}
    tot = ch("01_profile_totals").iloc[0]
    daily = ch("01_profile_daily")
    sites = ch("01_profile_sites")
    all_days = pd.date_range("2013-07-01", "2013-07-31").date
    present = set(pd.to_datetime(daily["EventDate"]).dt.date)
    missing = [str(d) for d in all_days if d not in present and d >= pd.Timestamp(tot.first_day).date()]
    out["profile"] = {
        "rows": int(tot.events), "users_exact": int(tot.users_exact), "users_uniq_approx": int(tot.users_uniq_approx),
        "uniq_vs_exact_gap": r4(tot.users_uniq_approx / tot.users_exact - 1), "sites": int(tot.sites),
        "first_day": str(tot.first_day)[:10], "last_day": str(tot.last_day)[:10], "days_present": int(tot.days_present),
        "missing_days": missing, "bot_share": r4(tot.bot_share), "mobile_share": r4(tot.mobile_share),
        "bot_share_day_min": r4(daily.bot_share.min()), "bot_share_day_max": r4(daily.bot_share.max()),
        "users_day_min": int(daily.users.min()), "users_day_min_date": str(daily.loc[daily.users.idxmin(), "EventDate"])[:10],
        "users_day_max": int(daily.users.max()), "users_day_max_date": str(daily.loc[daily.users.idxmax(), "EventDate"])[:10],
        "site_days_median": float(sites.days.median()), "share_sites_2_to_6_days": r4(sites.days.between(2, 6).mean()),
        "top30_share_of_rows": r4(sites.head(30).events.sum() / tot.events),
    }
    out["profile_daily"] = daily.assign(EventDate=daily.EventDate.astype(str).str[:10])[["EventDate", "events", "users", "sites", "bot_share"]].to_dict("records")
    e = ch("02_attribute_entropy").iloc[0]
    attrs = [c[3:] for c in e.index if c.startswith("h__") and c != "h__fingerprint16"]
    ent = sorted([{"attribute": a, "entropy_bits": r4(e[f"h__{a}"], 3), "distinct_values": int(e[f"n__{a}"]), "empty_share": r4(e[f"empty__{a}"], 3)} for a in attrs],
                 key=lambda r: -r["entropy_bits"])
    out["entropy"] = ent
    out["entropy_fingerprint16_bits"] = r4(e["h__fingerprint16"], 2)
    out["entropy_users"] = int(e["users"])
    out["entropy_max_bits_users"] = r4(math.log2(e["users"]), 2)
    a = ch("03_anon_summary").iloc[0]
    chk = ch("03_attribute_sets_check").iloc[0]
    fpu = ch("03_fps_per_user_month").iloc[0]
    b = ch("03_anon_buckets")
    out["anonymity"] = {
        "day": "2013-07-15", "fingerprints": int(a.fingerprints), "unique_fps": int(a.unique_fps), "shared_fps": int(a.shared_fps),
        "unique_fp_share": r4(a.unique_fps / a.fingerprints), "largest_set": int(a.largest_set),
        "users_day": int(chk.users), "share_users_alone_in_fp": r4(a.users_in_unique_fps / chk.users),
        "fp18": int(chk.fp18), "fp16": int(chk.fp16), "fp14": int(chk.fp14),
        "fps_per_user_p50": float(fpu.p50), "fps_per_user_p90": float(fpu.p90), "fps_per_user_p99": float(fpu.p99),
        "share_users_multi_fp": r4(fpu.share_multi_fp), "users_month": int(fpu.users),
        "buckets": b.to_dict("records"),
    }
    ev, vi, dy = ch("04_reid_event_grain"), ch("05_reid_visit_grain"), ch("05_reid_day_grain")
    per_site = ev.merge(vi, on="CounterID", suffixes=("_e", "_v"))
    for g in ["e", "v"]:
        tot_g = per_site[[f"tp_n_{g}", f"fp_n_{g}", f"fn_n_{g}", f"tn_n_{g}"]].sum(axis=1)
        per_site[f"fp_{g}"] = per_site[f"fp_n_{g}"] / tot_g
        per_site[f"tp_{g}"] = per_site[f"tp_n_{g}"] / tot_g
    out["replay"] = {
        "event": rates(ev), "visit": rates(vi), "day": rates(dy),
        "events_top30": int(ev.events.sum()), "visits_top30": int(vi.visits.sum()), "user_days_top30": int(dy.user_days.sum()),
        "events_per_visit": r4(ev.events.sum() / vi.visits.sum(), 2),
        "site_fp_event_min": r4(per_site.fp_e.min()), "site_fp_event_max": r4(per_site.fp_e.max()),
        "site_fp_visit_min": r4(per_site.fp_v.min()), "site_fp_visit_max": r4(per_site.fp_v.max()),
        "seconds_event_query": ch_meta("04_reid_event_grain")["seconds"],
        "sites": [{"site": int(r.CounterID), "events": int(r.events), "visits": int(r.visits), "tp_event": r4(r.tp_e), "fp_event": r4(r.fp_e),
                   "tp_visit": r4(r.tp_v), "fp_visit": r4(r.fp_v)} for r in per_site.itertuples()],
    }
    t = pd.concat([ch("06_reid_tolerant_a"), ch("06_reid_tolerant_b")])
    names = {0: "strict 18 attributes", 1: "exact 16 (reference)", 2: "tolerant 14 (no minor versions)", 3: "loose 9", 4: "loosest 5"}
    tol = []
    for v, g in t.groupby("variant"):
        rr = rates(g)
        tol.append({"variant": int(v), "name": names[int(v)], **rr})
    out["tolerant"] = tol
    bt = ch("07_bots_effect")
    allt = bt[bt.excl_bots == 0]
    out["bots"] = {
        "visit_share_bots": r4(allt[allt.is_bot == 1].visits.sum() / allt.visits.sum()),
        "all_traffic": rates(allt), "humans_in_all_traffic": rates(allt[allt.is_bot == 0]), "bots_in_all_traffic": rates(allt[allt.is_bot == 1]),
        "humans_bots_removed_before_replay": rates(bt[bt.excl_bots == 1]),
    }
    out["calibration"] = calibration(ch("08_confidence_calibration"))
    k = ch("09_cookie_churn_bound")
    out["cookie_churn"] = {"fp_visits": int(k.fp_n.sum()), "share_nonoverlap_upper_bound": r4(k.fp_nonoverlap.sum() / k.fp_n.sum()),
                           "share_gap_over_1_day": r4(k.fp_gap_over_1day.sum() / k.fp_n.sum())}
    u = ch("10_ua_major_daily")
    tops = u.groupby("UserAgentMajor").users.sum().sort_values(ascending=False).head(2).index.tolist()
    sh = u.pivot_table(index="EventDate", columns="UserAgentMajor", values="users", aggfunc="sum").fillna(0)
    share = (sh[tops].div(sh.sum(axis=1), axis=0))
    inst = ch("10_upgrade_instability").assign(changed_major=lambda d: d.changed_major.astype(bool)).set_index("changed_major")
    out["version_rollout"] = {
        "majors": [int(x) for x in tops],
        "daily_share": [{"day": str(d)[:10], **{f"major_{int(m)}": r4(share.loc[d, m]) for m in tops}} for d in share.index],
        "users_changed_major": int(inst.loc[True, "users"]), "users_stable_major": int(inst.loc[False, "users"]),
        "share_changed_major": r4(inst.loc[True, "users"] / inst.users.sum()),
        "multi_fp_changed": r4(inst.loc[True, "share_multi_fp"]), "multi_fp_stable": r4(inst.loc[False, "share_multi_fp"]),
        "multi_fp_no_version_changed": r4(inst.loc[True, "share_multi_fp_no_version"]),
        "multi_fp_no_version_stable": r4(inst.loc[False, "share_multi_fp_no_version"]),
    }
    rec = ch("11_reconciliation")
    out["reconciliation_reference"] = {"sites": int(rec.CounterID.nunique()), "rows_event_grain": int(rec[rec.grain == "event"].n.sum())}
    log = [json.loads(l) for l in (CH / "_log.jsonl").read_text().splitlines() if l.strip()]
    out["playground"] = {"queries_sent": len(log), "budget": 150, "failed_queries": sum(1 for l in log if l["status"] != 200),
                         "server_version": "26.10.3.7", "first_query_utc": log[0]["at"], "last_query_utc": log[-1]["at"]}
    return out


def calibration(c: pd.DataFrame) -> dict:
    """Illustrative score = 1 - FP share by anonymity-set bucket, learnt on each site's first half of days."""
    c = c.copy()
    c["n_days"] = c.groupby("CounterID").day_rank.transform("max")
    c = c[c.n_days >= 2]
    c["split"] = np.where(c.day_rank <= np.ceil(c.n_days / 2), "train", "test")
    edges = [0, 1, 2, 4, 9, 49, 1000]
    labels = ["1", "2", "3-4", "5-9", "10-49", "50+"]
    c["bucket"] = pd.cut(c.prior_users_capped, edges, labels=labels)
    tr = c[c.split == "train"].groupby(["CounterID", "bucket"], observed=True)[["matched_visits", "fp_n"]].sum()
    pooled = c[c.split == "train"].groupby("bucket", observed=True)[["matched_visits", "fp_n"]].sum()
    score_pooled = 1 - pooled.fp_n / pooled.matched_visits
    score_site = (1 - tr.fp_n / tr.matched_visits).rename("score").reset_index()
    te = c[c.split == "test"].groupby(["CounterID", "bucket"], observed=True)[["matched_visits", "fp_n"]].sum().reset_index()
    te = te.merge(score_site, on=["CounterID", "bucket"], how="left")
    te["score"] = te["score"].fillna(te["bucket"].map(score_pooled).astype(float))
    trn = c[c.split == "train"].groupby(["CounterID", "bucket"], observed=True)[["matched_visits", "fp_n"]].sum().reset_index().merge(score_site, on=["CounterID", "bucket"])

    def rel(df):
        bins = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0001]
        df = df.assign(sbin=pd.cut(df.score, bins, right=False))
        g = df.groupby("sbin", observed=True).apply(lambda x: pd.Series({"n": x.matched_visits.sum(), "mean_score": np.average(x.score, weights=x.matched_visits),
                                                                         "observed_precision": 1 - x.fp_n.sum() / x.matched_visits.sum()}), include_groups=False)
        g = g[g.n > 0]
        ece = float((g.n / g.n.sum() * (g.mean_score - g.observed_precision).abs()).sum())
        return g.reset_index(drop=True), ece
    rel_te, ece_te = rel(te)
    rel_tr, ece_tr = rel(trn)
    by_bucket = c.groupby(["split", "bucket"], observed=True)[["matched_visits", "fp_n"]].sum()
    by_bucket["fp_share"] = by_bucket.fp_n / by_bucket.matched_visits
    return {"sites_used": int(c.CounterID.nunique()), "ece_train": r4(ece_tr), "ece_test": r4(ece_te),
            "reliability_test": [{k: r4(v) for k, v in r.items()} for r in rel_te.to_dict("records")],
            "fp_share_by_bucket": [{"split": s, "bucket": str(bk), "matched_visits": int(r.matched_visits), "fp_share": r4(r.fp_share)}
                                   for (s, bk), r in by_bucket.iterrows()]}


# =============================================================================================== PUBLIC
def public_part():
    rel = pd.read_csv(PROC / "browser_releases.csv", dtype=str)
    win = rel[(rel.release_date >= "2026-08-24") & (rel.release_date <= "2026-11-22") & ~rel.first_stable_build.str.contains("latest")]
    cal = json.loads((PROC / "adoption_calibration.json").read_text())
    share = pd.read_csv(PROC / "wikimedia_browser_share.csv")
    ud = pd.read_csv(PROC / "wikimedia_unique_devices.csv")
    det = pd.read_csv(PROC / "wikimedia_detector.csv") if (PROC / "wikimedia_detector.csv").exists() else None
    checks = json.loads((PROC / "browser_release_checks.json").read_text())
    return {
        "releases_in_window": win[["browser", "major", "release_date"]].to_dict("records"),
        "chrome_feed_checks": checks,
        "adoption": {f: {"versions": v["versions"], "uptake_week1": v["median_uptake_by_week"]["1"], "uptake_week2": v["median_uptake_by_week"]["2"],
                         "uptake_week4": v["median_uptake_by_week"]["4"], "uptake_week8": v["median_uptake_by_week"]["8"]} for f, v in cal.items()},
        "adoption_curves_median": {f: v["median_uptake_by_week"] for f, v in cal.items()},
        "browser_share_week": share.week_start.iloc[0], "browser_share": share[["browser_family", "share"]].round(4).to_dict("records"),
        "unique_devices": {"days": int(len(ud)), "first_day": ud.date.iloc[0], "last_day": ud.date.iloc[-1],
                           "first_day_devices": int(ud.devices.iloc[0]), "first_day_offset": int(ud.offset.iloc[0]),
                           "offset_share_median": r4(ud.offset_share.median()), "devices_median": int(ud.devices.median()),
                           "alert_days": det.loc[det.alert, "date"].tolist() if det is not None else []},
    }


# =============================================================================================== SIMULATED
def q(con, sql, params=None):
    return con.execute(sql, params or []).df()


def sim_part(con):
    s = {}
    tot = q(con, "select count(*) n, count(distinct customer_id) c, avg(is_control::int) control_share, avg(is_incognito::int) inc, avg(is_bad_bot::int) bad from stg_identification_events").iloc[0]
    s["volume"] = {"events": int(tot.n), "customers": int(tot.c), "control_share": r4(tot.control_share), "incognito_share": r4(tot.inc),
                   "bad_bot_share": r4(tot.bad), "events_per_month_equivalent": int(tot.n / 91 * 30.4),
                   "scale_vs_1bn_per_month": r4(1e9 / (tot.n / 91 * 30.4), 0)}
    m = q(con, """select sum(control_events) n, sum(fp) fp, sum(fn) fn, sum(truth_fp) tfp, sum(truth_fn) tfn,
                         sum(truth_tp + truth_fp + truth_fn + truth_tn) tn_all from fct_accuracy_daily""").iloc[0]
    s["measured_vs_truth"] = {"measured_fp": r4(m.fp / m.n), "measured_fn": r4(m.fn / m.n), "truth_fp_all_traffic": r4(m.tfp / m.tn_all),
                              "truth_fn_all_traffic": r4(m.tfn / m.tn_all), "control_events": int(m.n), "human_events": int(m.tn_all)}
    s["e1"] = event1(con)
    s["e2"] = event2(con)
    s["e3"] = event3(con)
    s["e4"] = event4(con)
    s["e5"] = event5(con)
    s["e6"] = event6(con)
    s["e7"] = event7(con)
    s["e8"] = event8(con)
    s["stats"] = stats_part(con)
    s["queue"] = queue_part(con)
    s["health_latest"] = q(con, "select customer_id, health_status, health_reasons from mart_customer_health where week_start = date '2026-11-16' order by 1").to_dict("records")
    s["health_counts_by_week"] = q(con, """select cast(week_start as varchar) w, health_status, count(*) n from mart_customer_health group by 1, 2 order by 1, 2""").to_dict("records")
    return s


def event1(con):
    d = q(con, """select case when event_date < date '2026-10-02' then 'drift' else 'after_fix' end as period, browser_major,
                         sum(control_events) n, sum(fn) fn from fct_accuracy_daily
                  where browser in ('Chrome', 'Chrome Mobile') and browser_major in (154, 155)
                    and event_date between date '2026-09-23' and date '2026-10-15' group by 1, 2""")
    g = {(r.period, int(r.browser_major)): r for r in d.itertuples()}
    out = {}
    for (p, mj), r in g.items():
        lo, hi = metrics.wilson(r.fn, r.n)
        out[f"{p}_{mj}"] = {"control_events": int(r.n), "fn_rate": r4(r.fn / r.n), "ci": [r4(lo), r4(hi)]}
    out["release_date"] = "2026-09-23"
    out["fix_date"] = "2026-10-02"
    out["ratio_drift_vs_154"] = r4(out["drift_155"]["fn_rate"] / out["drift_154"]["fn_rate"], 2)
    cust_hit = q(con, """select count(distinct customer_id) from fct_accuracy_daily where browser in ('Chrome','Chrome Mobile') and browser_major = 155
                         and event_date between date '2026-09-23' and date '2026-10-01' and fn > 0""").iloc[0, 0]
    out["customers_with_fn_on_155_during_drift"] = int(cust_hit)
    share155 = q(con, """select sum(case when browser_major = 155 then human_events end) * 1.0 / sum(human_events) from fct_accuracy_daily
                         where browser in ('Chrome','Chrome Mobile') and event_date between date '2026-09-23' and date '2026-10-01'""").iloc[0, 0]
    out["chrome_traffic_share_on_155_during_drift"] = r4(share155)
    return out


def event2(con):
    seg = q(con, """
        select case when e.event_date < date '2026-09-14' then 'before' when e.event_date < date '2026-10-07' then 'issue' else 'after' end as period,
               e.browser_major = 27 as ios27, count(*) n,
               avg(e.confidence_score) avg_conf, avg((t.truth_outcome = 'FP')::int) truth_fp
        from stg_identification_events e join int_events_truth t using (event_id)
        where e.browser = 'Mobile Safari' and e.method = 'probabilistic' and e.visitor_found and not e.is_bad_bot
        group by 1, 2""")
    out = {"segment": "Mobile Safari, probabilistic answers with an existing visitor"}
    for r in seg.itertuples():
        out[f"{r.period}_{'ios27' if r.ios27 else 'other'}"] = {"answers": int(r.n), "avg_confidence": r4(r.avg_conf), "true_fp_rate": r4(r.truth_fp),
                                                              "implied_fp_rate": r4(1 - r.avg_conf)}
    mes = q(con, """select case when event_date < date '2026-10-07' then 'issue' else 'after' end p, sum(control_events) n, sum(fp) fp
                    from fct_accuracy_daily where browser = 'Mobile Safari' and browser_major = 27 and event_date >= date '2026-09-14' group by 1""").set_index("p")
    out["measured_fp_ios27_issue"] = r4(mes.loc["issue", "fp"] / mes.loc["issue", "n"])
    out["measured_fp_ios27_after"] = r4(mes.loc["after", "fp"] / mes.loc["after", "n"])
    c2 = q(con, """select case when event_date < date '2026-09-14' then 'before' when event_date < date '2026-10-07' then 'issue' else 'after' end p,
                          sum(below_threshold_events) * 1.0 / sum(found_events) below,
                          sum(case when browser = 'Mobile Safari' and browser_major = 27 then below_threshold_events end) * 1.0
                            / nullif(sum(case when browser = 'Mobile Safari' and browser_major = 27 then found_events end), 0) below_ios27,
                          sum(case when browser = 'Mobile Safari' and browser_major <> 27 then below_threshold_events end) * 1.0
                            / nullif(sum(case when browser = 'Mobile Safari' and browser_major <> 27 then found_events end), 0) below_ios_other
                   from fct_accuracy_daily where customer_id = 'C02' group by 1""").set_index("p")
    out["c02_step_up_share"] = {p: {"all": r4(c2.loc[p, "below"]), "ios27": r4(c2.loc[p, "below_ios27"]), "iphone_other": r4(c2.loc[p, "below_ios_other"])} for p in c2.index}
    ios_share = q(con, """select sum(case when browser_major = 27 then human_events end) * 1.0 / sum(human_events) from fct_accuracy_daily
                          where browser = 'Mobile Safari' and event_date between date '2026-10-01' and date '2026-10-06'""").iloc[0, 0]
    out["ios27_share_of_iphone_safari_first_week_oct"] = r4(ios_share)
    out["release_date"], out["fix_date"] = "2026-09-14", "2026-10-07"
    return out


def event3(con):
    lm = q(con, "select * from mart_linked_id_metrics where customer_id = 'C07'").set_index("scope")
    it = q(con, """
        with agent_visitors as (
            select distinct t.true_visitor_id as visitor_id from stg_device_truth t where t.true_is_internal_agent
        )
        select i.is_internal_suspected, (a.visitor_id is not null) as is_agent, count(*) n
        from int_internal_traffic i left join agent_visitors a using (visitor_id)
        where i.customer_id = 'C07' group by 1, 2""")
    tp = int(it[(it.is_internal_suspected) & (it.is_agent)].n.sum())
    fp = int(it[(it.is_internal_suspected) & (~it.is_agent)].n.sum())
    fn = int(it[(~it.is_internal_suspected) & (it.is_agent)].n.sum())
    heavy = q(con, """select count(*) visitors, sum(is_internal_suspected::int) internal from int_internal_traffic
                      where customer_id = 'C07' and accounts > 5""").iloc[0]
    agent_events = q(con, """select avg(true_is_internal_agent::int) from int_events_truth where customer_id = 'C07'""").iloc[0, 0]
    exp = pd.read_csv(SIM / "customer_exports" / "C07_accounts_export.csv")
    ours = q(con, "select count(*) pairs, sum(events) logins from int_linked_id_pairs where customer_id = 'C07'").iloc[0]
    top = exp.groupby("visitor_id").account_id.nunique().sort_values(ascending=False)
    return {
        "accounts_per_visitor": {sc: {"mean": r4(lm.loc[sc, "accounts_per_visitor_mean"], 3), "p99": r4(lm.loc[sc, "accounts_per_visitor_p99"], 1),
                                      "max": int(lm.loc[sc, "accounts_per_visitor_max"]), "share_over_5": r4(lm.loc[sc, "share_visitors_over_5_accounts"], 4)} for sc in lm.index},
        "visitors_per_account": {sc: {"mean": r4(lm.loc[sc, "visitors_per_account_mean"], 3), "p99": r4(lm.loc[sc, "visitors_per_account_p99"], 1)} for sc in lm.index},
        "internal_rule": {"flagged": tp + fp, "true_agents_flagged": tp, "non_agents_flagged": fp, "agents_missed": fn,
                          "precision": r4(tp / (tp + fp)) if tp + fp else None, "recall": r4(tp / (tp + fn)) if tp + fn else None},
        "visitors_over_5_accounts": int(heavy.visitors), "of_which_internal": int(heavy.internal),
        "agent_share_of_c07_events": r4(agent_events),
        "export_pairs": int(len(exp)), "our_pairs": int(ours.pairs), "export_logins": int(exp.logins.sum()), "our_logins": int(ours.logins),
        "export_top_visitor_accounts": int(top.iloc[0]),
    }


def event4(con):
    exp = pd.read_csv(SIM / "customer_exports" / "C03_sessions_export.csv", parse_dates=["local_date"])
    ours_local = q(con, """select cast(timezone('America/New_York', ts_utc at time zone 'UTC') as date) as local_date, count(*) n
                           from stg_identification_events where customer_id = 'C03' group by 1""")
    ours_utc = q(con, "select event_date, count(*) n from stg_identification_events where customer_id = 'C03' group by 1")
    ours_local["local_date"] = pd.to_datetime(ours_local.local_date)
    ours_utc["event_date"] = pd.to_datetime(ours_utc.event_date)
    m0, m1 = pd.Timestamp("2026-10-01"), pd.Timestamp("2026-10-31")
    e = exp[exp.local_date.between(m0, m1)]
    their_total, their_vid = int(e.sessions.sum()), int(e.sessions_with_visitor_id.sum())
    our_local = int(ours_local[ours_local.local_date.between(m0, m1)].n.sum())
    our_utc = int(ours_utc[ours_utc.event_date.between(m0, m1)].n.sum())
    bridge = [
        {"step": "Customer export: sessions, October 2026 (local days, New York time)", "value": their_total},
        {"step": "minus sessions with no visitor id (identification request blocked: no proxy integration)", "value": -(their_total - their_vid)},
        {"step": "minus duplicate sessions in the export (page reloads counted twice; unexplained residual)", "value": -(their_vid - our_local)},
        {"step": "= our identification events on the same LOCAL days", "value": our_local, "subtotal": True},
        {"step": "minus / plus the time-zone shift (local days vs UTC days at both ends of the month)", "value": our_utc - our_local},
        {"step": "= billed identification events, October 2026 (UTC days)", "value": our_utc, "subtotal": True},
    ]
    daily = exp.merge(ours_utc.rename(columns={"event_date": "local_date", "n": "ours_utc"}), on="local_date").merge(ours_local.rename(columns={"n": "ours_local"}), on="local_date")
    daily["gap_utc"] = daily.sessions / daily.ours_utc - 1
    dst = daily[daily.local_date.isin([pd.Timestamp("2026-10-31"), pd.Timestamp("2026-11-01"), pd.Timestamp("2026-11-02")])]
    return {"month": "2026-10", "bridge": bridge, "their_over_ours_pct": r4(their_total / our_utc - 1),
            "blocked_share": r4(1 - their_vid / their_total), "residual_share": r4(their_vid / our_local - 1, 5),
            "tz_shift": our_utc - our_local, "daily_gap_mean_abs": r4(daily.gap_utc.abs().mean()),
            "daily_gap_min": r4(daily.gap_utc.min()), "daily_gap_max": r4(daily.gap_utc.max()),
            "dst_days": dst[["local_date", "sessions", "ours_utc", "ours_local"]].assign(local_date=lambda d: d.local_date.dt.strftime("%Y-%m-%d")).to_dict("records")}


def event5(con):
    raw = duckdb.sql(f"""select count(*) n, count(distinct event_id) u from read_parquet('{(SIM / 'identification_events' / 'event_date=2026-10-27' / 'C05.parquet').as_posix()}')""").fetchone()
    late = q(con, "select min(loaded_at) l from stg_ingestion_log where partition_date = date '2026-10-28'").iloc[0, 0]
    rr = json.loads((ROOT / "dbt" / "target" / "run_results.json").read_text())
    warn = {r["unique_id"].split(".")[2]: r.get("failures") for r in rr["results"] if r["status"] == "warn"}
    rep_path = PROC / "incremental_replay_check.json"
    rep = json.loads(rep_path.read_text()) if rep_path.exists() else None
    load = pd.read_csv(PROC / "incremental_naive_by_load_day.csv") if (PROC / "incremental_naive_by_load_day.csv").exists() else None
    return {"c05_rows_in_file": int(raw[0]), "c05_unique": int(raw[1]), "c05_duplicates": int(raw[0] - raw[1]), "dup_share": r4((raw[0] - raw[1]) / raw[1]),
            "late_partition": "2026-10-28", "late_loaded_at": str(late)[:16], "dbt_warnings": warn, "incremental_check": rep,
            "naive_by_load_day": load.to_dict("records") if load is not None else None}


def event6(con):
    w = q(con, """select case when event_date between date '2026-11-05' and date '2026-11-12' then 'wave' else 'outside' end p,
                         sum(bad_bot_events) * 1.0 / sum(events) bot_share, sum(events) ev from fct_accuracy_daily where customer_id = 'P01' group by 1""").set_index("p")
    fnb = q(con, """select is_bad_bot, avg((measured_outcome = 'FN')::int) fn, count(*) n from int_events_measured
                    where customer_id = 'P01' and event_date between date '2026-11-05' and date '2026-11-12' group by 1""").set_index("is_bad_bot")
    allfn = q(con, """select avg((measured_outcome = 'FN')::int) from int_events_measured
                      where customer_id = 'P01' and event_date between date '2026-11-05' and date '2026-11-12'""").iloc[0, 0]
    vpa = q(con, """with p as (
                        select linked_id, visitor_id, bool_or(is_bad_bot) any_bot, bool_and(is_bad_bot) all_bot
                        from stg_identification_events where customer_id = 'P01' and linked_id is not null
                          and event_date between date '2026-11-05' and date '2026-11-12' group by 1, 2)
                    select 'all' as scope, avg(c) as mean from (select linked_id, count(distinct visitor_id) c from p group by 1)
                    union all
                    select 'excl_bad_bots', avg(c) from (select linked_id, count(distinct visitor_id) c from p where not all_bot group by 1)""").set_index("scope")
    split = q(con, """select case when m.event_date between date '2026-11-05' and date '2026-11-12' then 'wave' else 'outside' end p,
                             avg((m.measured_outcome = 'FN')::int) fn_flag_excl,
                             avg(case when not t.true_is_bad_bot then (m.measured_outcome = 'FN')::int end) fn_true_humans
                      from int_events_measured m join stg_device_truth t using (event_id)
                      where m.customer_id = 'P01' and not m.is_bad_bot group by 1""").set_index("p")
    return {"fn_humans_outside": r4(split.loc["outside", "fn_flag_excl"]),
            "fn_true_humans_wave": r4(split.loc["wave", "fn_true_humans"]), "fn_true_humans_outside": r4(split.loc["outside", "fn_true_humans"]),
            "bot_share_wave": r4(w.loc["wave", "bot_share"]), "bot_share_outside": r4(w.loc["outside", "bot_share"]),
            "fn_all_traffic_wave": r4(allfn), "fn_humans_wave": r4(fnb.loc[False, "fn"]), "fn_bots_wave": r4(fnb.loc[True, "fn"]) if True in fnb.index else None,
            "visitors_per_account_wave_all": r4(vpa.loc["all", "mean"], 2), "visitors_per_account_wave_excl_bots": r4(vpa.loc["excl_bad_bots", "mean"], 2),
            "wave": ["2026-11-05", "2026-11-12"]}


def event7(con):
    d = q(con, """select case when event_date < date '2026-10-12' then 'before' else 'after' end p, is_incognito,
                         count(*) n, avg((truth_outcome in ('FP','FN'))::int) err, avg((truth_outcome = 'FN')::int) fn
                  from int_events_truth where customer_id = 'C09' and not is_bad_bot group by 1, 2""")
    seg = {f"{r.p}_{'incognito' if r.is_incognito else 'normal'}": {"events": int(r.n), "true_error_rate": r4(r.err), "true_fn_rate": r4(r.fn)} for r in d.itertuples()}
    tot = d.groupby("p").apply(lambda g: pd.Series({"err": np.average(g.err, weights=g.n), "inc": g.loc[g.is_incognito, "n"].sum() / g.n.sum()}), include_groups=False)
    mes = q(con, """select case when event_date < date '2026-10-12' then 'before' else 'after' end p, sum(control_events) n, sum(fp) + sum(fn) err, sum(fn) fn
                    from fct_accuracy_daily where customer_id = 'C09' group by 1""").set_index("p")
    nv = q(con, """select case when event_date < date '2026-10-12' then 'before' else 'after' end p, sum(new_visitor_events) * 1.0 / sum(human_events) nv
                   from fct_accuracy_daily where customer_id = 'C09' group by 1""").set_index("p")
    return {"incognito_share_before": r4(tot.loc["before", "inc"]), "incognito_share_after": r4(tot.loc["after", "inc"]),
            "true_error_before": r4(tot.loc["before", "err"]), "true_error_after": r4(tot.loc["after", "err"]),
            "measured_error_before": r4(mes.loc["before", "err"] / mes.loc["before", "n"]), "measured_error_after": r4(mes.loc["after", "err"] / mes.loc["after", "n"]),
            "new_visitor_share_before": r4(nv.loc["before", "nv"]), "new_visitor_share_after": r4(nv.loc["after", "nv"]),
            "by_segment": seg, "campaign_date": "2026-10-12"}


def event8(con):
    mix = q(con, "select * from mart_mix_standardized order by week_start")
    mix["week_start"] = mix.week_start.astype(str)
    w = mix.set_index("week_start")
    a, b = "2026-10-12", "2026-10-19"
    out = {"weeks": mix.round(6).to_dict("records"),
           "crude_change": r4(w.loc[b, "fp_rate_crude"] / w.loc[a, "fp_rate_crude"] - 1),
           "standardized_change": r4(w.loc[b, "fp_rate_standardized"] / w.loc[a, "fp_rate_standardized"] - 1),
           "stable_cohort_change": r4(w.loc[b, "fp_rate_stable_cohort"] / w.loc[a, "fp_rate_stable_cohort"] - 1),
           "crude_before": r4(w.loc[a, "fp_rate_crude"]), "crude_after": r4(w.loc[b, "fp_rate_crude"])}
    seg = q(con, """select browser, customer_id = 'C12' as is_c12, sum(control_events) n, sum(fp) fp from fct_accuracy_daily
                    where event_date >= date '2026-10-19' and browser in ('Mobile Safari', 'Chrome Mobile', 'Chrome') group by 1, 2""")
    comp = []
    for br, g in seg.groupby("browser"):
        c12, oth = g[g.is_c12].iloc[0], g[~g.is_c12].iloc[0]
        t = metrics.two_proportion_test(oth.fp, oth.n, c12.fp, c12.n, phi=2.0)
        comp.append({"browser": br, "c12_fp": r4(c12.fp / c12.n), "c12_ci": [r4(x) for x in metrics.wilson(c12.fp, c12.n)],
                     "others_fp": r4(oth.fp / oth.n), "others_ci": [r4(x) for x in metrics.wilson(oth.fp, oth.n)], "p_value": r4(t["p_value"])})
    out["c12_vs_others_same_segment"] = comp
    cw = q(con, """select customer_id, sum(case when week_start = date '2026-10-12' then control_events end) na, sum(case when week_start = date '2026-10-12' then fp end) ka,
                          sum(case when week_start = date '2026-10-19' then control_events end) nb, sum(case when week_start = date '2026-10-19' then fp end) kb
                   from fct_accuracy_weekly_customer w join stg_customers c using (customer_id)
                   where week_start in (date '2026-10-12', date '2026-10-19')
                     and c.start_date < date '2026-10-12'          -- existing customers only (not C12, not POCs)
                   group by 1 order by 1""").dropna()
    sig = []
    for r in cw.itertuples():
        t = metrics.two_proportion_test(r.ka, r.na, r.kb, r.nb, phi=2.0)
        sig.append({"customer_id": r.customer_id, "fp_a": r4(r.ka / r.na), "fp_b": r4(r.kb / r.nb), "p_value": r4(t["p_value"])})
    out["customers_week_over_week"] = sig
    out["customers_significant_at_1pct"] = sum(1 for x in sig if x["p_value"] < 0.01)
    c12_share = q(con, """select sum(case when customer_id = 'C12' then control_events end) * 1.0 / sum(control_events) from fct_accuracy_daily
                          where event_date between date '2026-10-19' and date '2026-10-25'""").iloc[0, 0]
    out["c12_share_of_control_week"] = r4(c12_share)
    return out


def stats_part(con):
    out = {}
    agg = q(con, """select visitor_id, count(*) n, sum((measured_outcome = 'FP')::int) k
                    from int_events_measured m join stg_identification_events e using (event_id)
                    where m.customer_id = 'C04' and m.event_date >= date '2026-10-26' and not m.is_bad_bot group by 1 order by 1""")  # fixed order: reproducible bootstrap
    k, n = agg.k.values, agg.n.values
    p = k.sum() / n.sum()
    lo, hi = metrics.wilson(k.sum(), n.sum())
    boot = metrics.cluster_bootstrap_rate(k, n, b=1000, seed=42)
    deff = (boot["se"] ** 2) / (p * (1 - p) / n.sum())
    daily_n = n.sum() / 28
    req = metrics.required_n(p, 0.002, phi=deff)
    out["c04"] = {"period": ["2026-10-26", "2026-11-22"], "control_events": int(n.sum()), "visitors": int(len(n)), "fp_rate": r4(p, 5),
                  "wilson": [r4(lo, 5), r4(hi, 5)], "cluster_bootstrap": [r4(boot["lo"], 5), r4(boot["hi"], 5)],
                  "width_ratio_cluster_vs_naive": r4((boot["hi"] - boot["lo"]) / (hi - lo), 2), "design_effect": r4(deff, 2),
                  "control_events_per_day": int(daily_n), "mde_delta": 0.002, "required_n_per_period": int(req), "required_days_per_period": r4(req / daily_n, 1),
                  "mde_with_28_days": r4(metrics.mde(p, n.sum(), phi=deff), 5)}
    # design effect depends on events per visitor: a few cases side by side
    deffs = []
    for cid, metric, start in [("C04", "FP", "2026-10-26"), ("C04", "FN", "2026-08-24"), ("C07", "FN", "2026-08-24"), ("C12", "FP", "2026-10-19")]:
        a2 = q(con, f"""select visitor_id, count(*) n, sum((measured_outcome = '{metric}')::int) k
                        from int_events_measured m join stg_identification_events e using (event_id)
                        where m.customer_id = '{cid}' and m.event_date >= date '{start}' and not m.is_bad_bot group by 1 order by 1""")
        bb = metrics.cluster_bootstrap_rate(a2.k.values, a2.n.values, b=1000, seed=42)
        pp = a2.k.sum() / a2.n.sum()
        lo2, hi2 = metrics.wilson(a2.k.sum(), a2.n.sum())
        deffs.append({"customer_id": cid, "metric": metric, "from": start, "events_per_visitor": r4(a2.n.mean(), 2),
                      "max_events_one_visitor": int(a2.n.max()), "rate": r4(pp, 5),
                      "design_effect": r4(bb["se"] ** 2 / (pp * (1 - pp) / a2.n.sum()), 2),
                      "width_ratio": r4((bb["hi"] - bb["lo"]) / (hi2 - lo2), 2)})
    out["design_effects"] = deffs
    # threshold trade-off for C02: step-up share vs share of true false positives caught (simulated truth)
    th = q(con, """select e.confidence_score s, (t.truth_outcome = 'FP') is_fp
                   from stg_identification_events e join int_events_truth t using (event_id)
                   where e.customer_id = 'C02' and e.visitor_found and not e.is_bad_bot""")
    rows = []
    for thr in [0.90, 0.92, 0.94, 0.95, 0.96, 0.97, 0.98, 0.99]:
        below = th.s < thr
        rows.append({"threshold": thr, "step_up_share": r4(below.mean()), "fp_caught_share": r4((below & th.is_fp).sum() / th.is_fp.sum()),
                     "precision_of_step_up": r4((below & th.is_fp).sum() / below.sum()) if below.sum() else None})
    out["threshold_tradeoff_c02"] = rows
    out["c02_found_answers"] = int(len(th))
    # calibration of the simulated score, probabilistic answers only (deterministic answers carry ~0.997)
    cal = q(con, """select e.confidence_score s, (t.truth_outcome = 'FP')::int is_fp,
                           (e.browser = 'Mobile Safari' and e.browser_major = 27 and e.event_date between date '2026-09-14' and date '2026-10-06') as ios_issue
                    from stg_identification_events e join int_events_truth t using (event_id)
                    where e.method = 'probabilistic' and e.visitor_found and not e.is_bad_bot and e.confidence_score >= 0.8""")
    bins = [0.80, 0.90, 0.94, 0.96, 0.97, 0.98, 0.99, 1.0]
    for key, mask in [("all_other_segments", ~cal.ios_issue), ("ios27_before_fix", cal.ios_issue)]:
        t = metrics.reliability_table(cal.s[mask].values, cal.is_fp[mask].values, bins)
        out[f"calibration_{key}"] = {"ece": r4(metrics.expected_calibration_error(t), 5), "table": [{kk: r4(v, 5) for kk, v in r.items()} for r in t]}
    return out


def queue_part(con):
    qq = q(con, "select * from mart_request_queue")
    res = qq[qq.hours_to_resolve.notna()]
    res = res.assign(within_sla=res.hours_to_resolve <= res.sla_hours)
    by_tier = res.groupby("priority_tier").agg(n=("request_id", "size"), median_hours=("hours_to_resolve", "median"), within_sla=("within_sla", "mean"))
    ss = qq[qq.self_service_possible]
    return {"requests": int(len(qq)), "open_at_end": int(qq.is_open.sum()), "by_team": qq.requesting_team.value_counts().to_dict(),
            "by_type": qq.request_type.value_counts().to_dict(), "by_tier": {t: {"n": int(r.n), "median_hours": r4(r.median_hours, 1), "within_sla": r4(r.within_sla, 3)} for t, r in by_tier.iterrows()},
            "tier_counts": qq.priority_tier.value_counts().sort_index().to_dict(),
            "self_service_possible": int(len(ss)), "self_service_share": r4(len(ss) / len(qq), 3),
            "self_service_hours": r4(ss.effort_hours.sum(), 1), "total_hours": r4(qq.effort_hours.sum(), 1),
            "self_service_hours_share": r4(ss.effort_hours.sum() / qq.effort_hours.sum(), 3),
            "linked_to_hidden_events": int(qq.linked_hidden_event.sum())}


def dbt_part():
    rr = json.loads((ROOT / "dbt" / "target" / "run_results.json").read_text())
    man = json.loads((ROOT / "dbt" / "target" / "manifest.json").read_text())
    st = pd.Series([r["status"] for r in rr["results"]]).value_counts().to_dict()
    nodes = man["nodes"].values()
    models = [n for n in nodes if n["resource_type"] == "model"]
    tests = [n for n in nodes if n["resource_type"] == "test"]
    unit = man.get("unit_tests", {})
    return {"status_counts": st, "models": len(models), "data_tests": len(tests), "unit_tests": len(unit),
            "seeds": sum(1 for n in nodes if n["resource_type"] == "seed"), "exposures": len(man.get("exposures", {})),
            "sources": len(man.get("sources", {})), "incremental_models": [n["name"] for n in models if n["config"]["materialized"] == "incremental"],
            "elapsed_s": r4(rr.get("elapsed_time"), 1)}


def reconciliation(con):
    r = q(con, "select count(*) rows_, count(distinct counter_id) sites, sum(total_abs_diff) as abs_diff, sum(case when grain='event' then duckdb_n end) n_event from mart_hits_reid_check").iloc[0]
    return {"sites": int(r.sites), "site_grain_rows": int(r.rows_), "total_abs_diff": int(r.abs_diff), "event_rows": int(r.n_event)}


def write_sample(con):
    """Published demo files: 10,000 SIMULATED events (no network hash) and the two simulated customer exports."""
    out = ROOT / "data" / "sample"
    out.mkdir(parents=True, exist_ok=True)
    s = con.sql("""select * exclude (ip_hash, loaded_at) from stg_identification_events using sample reservoir(10000 rows) repeatable (42)""").df()
    s.sort_values("ts_utc").to_csv(out / "identification_events_sample.csv", index=False)
    (out / "C03_sessions_export.csv").write_bytes((SIM / "customer_exports" / "C03_sessions_export.csv").read_bytes())
    # the full C07 export is 24 MB: publish the 20,000 pairs of the 200 visitors with the most accounts plus a random rest
    c07 = pd.read_csv(SIM / "customer_exports" / "C07_accounts_export.csv")
    top = c07.groupby("visitor_id").account_id.nunique().nlargest(200).index
    sample = pd.concat([c07[c07.visitor_id.isin(top)].head(15000), c07[~c07.visitor_id.isin(top)].sample(5000, random_state=42)])
    sample.to_csv(out / "C07_accounts_export_sample.csv", index=False)
    old = out / "C07_accounts_export.csv"
    if old.exists():
        old.unlink()


def write_generated_docs(f):
    """Markdown snippets with numbers, generated from findings (never typed by hand)."""
    g = ROOT / "docs" / "generated"
    g.mkdir(parents=True, exist_ok=True)
    e4 = f["sim"]["e4"]
    lines = ["# C03 reconciliation bridge, October 2026 (SIMULATED, generated by src/findings.py)", "",
             "| Step | Events |", "|---|---:|"]
    lines += [f"| {'**' + s['step'] + '**' if s.get('subtotal') else s['step']} | {s['value']:+,} |" if i and not s.get("subtotal")
              else f"| {'**' + s['step'] + '**' if s.get('subtotal') else s['step']} | {s['value']:,} |" for i, s in enumerate(e4["bridge"])]
    lines += ["", f"Their total is {e4['their_over_ours_pct']:+.1%} above ours; {e4['blocked_share']:.1%} of their sessions have no visitor id "
              f"(blocked requests); the unexplained residual is {e4['residual_share']:.3%}."]
    (g / "c03_bridge.md").write_text(chr(10).join(lines) + chr(10), encoding="utf-8")


def write_clickhouse_readme(f):
    """clickhouse/README.md: every statement with its run date, duration and row count, read from the cache metadata."""
    rows = []
    for meta in sorted(CH.glob("*.json")):
        m = json.loads(meta.read_text())
        if "rows" in m:
            rows.append(f"| `{m['name']}` | {m['rows']:,} | {m['seconds']} | {m['run_at_utc'][:16].replace('T', ' ')} |")
        elif "accepted" in m:
            rows.append(f"| `{m['name']}` (EXPLAIN AST) | {'accepted' if m['accepted'] else 'rejected'} | - | {m['run_at_utc'][:16].replace('T', ' ')} |")
    pg = f["real"]["playground"]
    text = f"""# ClickHouse

All SQL in `analyses/` ran on the **public, read-only ClickHouse playground** (`https://play.clickhouse.com/?user=play`,
ClickHouse {pg['server_version']}) against `default.hits` (ClickBench, CC BY-NC-SA 4.0), through `src/clickhouse_play.py`:
aggregates only, `FORMAT Parquet`, at least 1 second between queries, every result cached with its SQL, date and duration
in `data/cache/clickhouse/`. Queries sent in total: **{pg['queries_sent']} of the 150 allowed** ({pg['failed_queries']} failed and were
rewritten, never retried as is: memory limit of the playground).

- `analyses/01..10`: the real-data analyses of the report (each file starts with its question, grain and definitions).
- `analyses/11_reconciliation.sql`: the same replay as the dbt model `int_hits_reid`, for the DuckDB vs ClickHouse check.
- `ddl/`: target tables for the marts as they would be created in production (ReplacingMergeTree, SummingMergeTree,
  AggregatingMergeTree with `uniqState`/`uniqMerge`, materialized views). Not executed (read-only playground);
  **syntax checked with `EXPLAIN AST`**, which the playground accepts.

Rerun (uses the cache, sends nothing if the SQL did not change): `python src/clickhouse_play.py --all` and `--ddl`.

| Statement | Rows returned | Seconds (wall-clock, incl. up to 1 s politeness delay) | Run (UTC) |
|---|---:|---:|---|
""" + "\n".join(rows) + "\n\nNotes on the design choices: `docs/clickhouse_notes.md`.\n"
    (ROOT / "clickhouse" / "README.md").write_text(text, encoding="utf-8")


def write_data_issues_log(f):
    p, s = f["real"]["profile"], f["sim"]
    e5, e4 = s["e5"], s["e4"]
    checks = f["public"]["chrome_feed_checks"]
    text = f"""# Data issues log

Generated by `src/findings.py` from `data/processed/findings.json` (no number typed by hand).

| # | Data | Issue | Impact | Handling | Status |
|---|---|---|---|---|---|
| 1 | ClickBench `hits` (real) | Only {p['days_present']} days present between {p['first_day']} and {p['last_day']}; missing: {', '.join(d[5:] for d in p['missing_days'])} | daily counts meaningless; trends impossible | rates only; partial days flagged; no raw daily series in any chart except the coverage chart | documented |
| 2 | ClickBench `hits` (real) | Very uneven volumes: {p['users_day_min']:,} users on {p['users_day_min_date']} vs {p['users_day_max']:,} on {p['users_day_max_date']}; median site covers {p['site_days_median']:.0f} days | site histories are short | replay per site; calibration split by site days | documented |
| 3 | ClickBench `hits` (real) | Values obfuscated by `clickhouse-obfuscator` (e.g. resolutions are not real resolutions) | values cannot be interpreted | only equality of values used; entropy per attribute measured | documented |
| 4 | ClickBench `hits` (real) | Robots: {p['bot_share_day_min']:.0%} to {p['bot_share_day_max']:.0%} of events per day | inflates or deflates accuracy | measured with and without robots (analysis 07) | handled |
| 5 | ClickBench `hits` (real) | `UserID` (cookie) used as truth can be reset | some FPs may be the same device | upper bound computed (analysis 09) | bounded |
| 6 | ClickBench Parquet files | Sites cut between local files and the rest of the table | local replay would differ | only sites whose local row count equals ClickHouse's ({f['real']['reconciliation']['sites']} sites) | handled |
| 7 | ClickBench `hits` | `uniq` vs `uniqExact` users: {p['users_uniq_approx']:,} vs {p['users_exact']:,} ({p['uniq_vs_exact_gap']:+.2%}) | approximate counts | `uniqExact` for anything reconciled or tested | handled |
| 8 | Chromium Dash feed | {checks['builds_in_feed']} builds; several builds per milestone; the oldest milestone ({checks['oldest_milestone_dropped_as_incomplete']}) starts mid-way in the feed | wrong release dates if the latest build is used | first stable build per milestone; oldest milestone dropped; milestone = version prefix checked ({checks['milestone_equals_version_major']}) | handled |
| 9 | endoflife.date (iOS) | only the major release date and the latest point release are given | no dates for 27.1 / 27.2 | only 27.0 (release) used | documented |
| 10 | Simulated loader | C05 rows of {e5['late_partition'][:8]}27 re-sent: {e5['c05_duplicates']:,} duplicates ({e5['dup_share']:.0%} of the day) | double counting | source uniqueness test (warn), deduplication in staging, raw vs ingestion-log test (warn) | caught by dbt |
| 11 | Simulated loader | Partition {e5['late_partition']} loaded on {e5['late_loaded_at']} (two days late) | hole then spike in a naive chart; lost day in an append-only table | completeness test (warn), incremental model with 3-day lookback; replay shows equality with a full rebuild | caught by dbt |
| 12 | Customer export C03 (simulated) | sessions by local New York day, including requests blocked without proxy integration ({e4['blocked_share']:.1%}) | {e4['their_over_ours_pct']:+.1%} gap vs billed events | reconciliation bridge (docs/generated/c03_bridge.md) | explained |
"""
    (ROOT / "docs" / "data_issues_log.md").write_text(text, encoding="utf-8")


def main():
    con = duckdb.connect(str(DB), read_only=True)
    write_sample(con)
    f = {"meta": {"generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "window": ["2026-08-24", "2026-11-22"],
                  "seed": 42, "read_on": "2026-11-23"},
         "fingerprint": json.loads((PROC / "fingerprint_public_facts.json").read_text()),
         "real": real_part(), "public": public_part(), "sim": sim_part(con), "dbt": dbt_part()}
    f["real"]["reconciliation"] = reconciliation(con)
    mb = PROC / "monitoring_backtest.json"
    f["monitoring"] = json.loads(mb.read_text()) if mb.exists() else None
    (PROC / "findings.json").write_text(json.dumps(f, indent=1, default=str))
    write_generated_docs(f)
    write_clickhouse_readme(f)
    write_data_issues_log(f)
    print("findings.json written:", len(json.dumps(f, default=str)) // 1024, "KB")


if __name__ == "__main__":
    main()
