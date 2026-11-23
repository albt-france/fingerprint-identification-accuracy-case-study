"""Matplotlib charts for the PDF (report/img/*.png).

Every chart reads data/processed (findings.json, monitoring and replay outputs, public extracts) or the dbt marts
(read-only). Style: light page, white cards, blue for the data, grey for comparison, red for alerts and thresholds,
dashed lines for events, Segoe UI. The PDF card around each chart carries the PUBLIC DATA / SIMULATED tag.
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import duckdb  # noqa: E402
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mtick  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROC, IMG = ROOT / "data" / "processed", ROOT / "report" / "img"
DB = ROOT / "dbt" / "fingerprint.duckdb"
BLUE, GREY, RED, INK, MUTED, GRID, ORANGE, GREEN = "#2A78D6", "#A3A19A", "#D03B3B", "#0B0B0B", "#52514E", "#E1E0D9", "#EB6834", "#2E7D4F"
LIGHT = "#C9DDF5"
plt.rcParams.update({
    "font.family": "Segoe UI", "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": MUTED,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "figure.facecolor": "white", "axes.facecolor": "white", "legend.frameon": False,
    "axes.titlesize": 11, "axes.titleweight": "semibold", "axes.titlecolor": INK, "axes.titlelocation": "left",
    "svg.hashsalt": "fixed", "pdf.fonttype": 42,
})
F = None


def findings():
    global F
    if F is None:
        F = json.loads((PROC / "findings.json").read_text(encoding="utf-8"))
    return F


def sql(q):
    with duckdb.connect(str(DB), read_only=True) as con:
        return con.sql(q).df()


def save(fig, name):
    IMG.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(IMG / f"{name}.png", dpi=170, metadata={"Software": None})
    plt.close(fig)
    return f"img/{name}.png"


def pct_axis(ax, axis="y", d=0):
    fmt = mtick.PercentFormatter(1.0, decimals=d)
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


def date_axis(ax, fmt="%d %b"):
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=6))
    ax.xaxis.set_major_formatter(mdates.DateFormatter(fmt))


def vline(ax, date, label, color=RED, y=0.97):
    d = pd.Timestamp(date)
    ax.axvline(d, color=color, ls="--", lw=1)
    ax.text(d, ax.get_ylim()[1] * y, " " + label, color=color, fontsize=8.5, va="top")


# ------------------------------------------------------------------------------------------------ page 1
def oss_releases():
    d = pd.read_csv(PROC / "fingerprintjs_releases_per_year.csv")
    fig, ax = plt.subplots(figsize=(5.0, 2.9))
    ax.bar(d.year.astype(str), d.releases, color=BLUE)
    ax.set_title("Open-source library releases per year")
    ax.set_ylabel("releases (GitHub)")
    ax.tick_params(axis="x", labelsize=8, rotation=45)
    return save(fig, "p1_oss_releases")


# ------------------------------------------------------------------------------------------------ page 2 (REAL)
def grain_outcomes():
    r = findings()["real"]["replay"]
    grains = [("Event\n(every page view)", r["event"]), ("Visit\n(30-min gap)", r["visit"]), ("User-day", r["day"])]
    fig, ax = plt.subplots(figsize=(5.3, 3.6))
    left = np.zeros(3)
    for key, lab, col in [("tp", "True positive", BLUE), ("fp", "False positive", RED), ("fn", "False negative", ORANGE), ("tn", "True new", GREY)]:
        vals = np.array([g[1][key] for g in grains])
        ax.barh([g[0] for g in grains], vals, left=left, color=col, label=lab)
        for i, v in enumerate(vals):
            if v > 0.06:
                ax.text(left[i] + v / 2, i, f"{v:.0%}", ha="center", va="center", color="white", fontsize=9, fontweight="bold")
        left += vals
    pct_axis(ax, "x")
    ax.invert_yaxis()
    ax.set_title("Same method, same data: the grain changes the answer")
    ax.legend(ncol=4, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    ax.grid(axis="y", visible=False)
    return save(fig, "p2_grain_outcomes")


def site_spread():
    s = pd.DataFrame(findings()["real"]["replay"]["sites"]).sort_values("fp_event")
    fig, ax = plt.subplots(figsize=(5.3, 3.6))
    y = np.arange(len(s))
    ax.hlines(y, s.fp_event, s.fp_visit, color=GRID, lw=2)
    ax.scatter(s.fp_event, y, color=BLUE, s=18, label="event grain", zorder=3)
    ax.scatter(s.fp_visit, y, color=RED, s=18, label="visit grain", zorder=3)
    ax.set_yticks([])
    ax.set_ylabel("30 largest sites")
    pct_axis(ax, "x")
    ax.set_xlabel("false-positive share of re-identification attempts")
    ax.set_title("Every site, both grains")
    ax.legend(fontsize=8, loc="lower right")
    return save(fig, "p2_site_spread")


def coverage():
    d = pd.DataFrame(findings()["real"]["profile_daily"])
    d["EventDate"] = pd.to_datetime(d.EventDate)
    full = pd.DataFrame({"EventDate": pd.date_range("2013-07-01", "2013-07-31")}).merge(d, how="left")
    fig, ax = plt.subplots(figsize=(5.3, 3.0))
    ax.bar(full.EventDate, full.users.fillna(0) / 1e6, color=np.where(full.users.isna(), RED, BLUE), width=0.8)
    for dd in full[full.users.isna()].EventDate:
        ax.text(dd, 0.05, "x", color=RED, ha="center", fontsize=8)
    ax.set_ylabel("distinct users (millions)")
    ax.set_title("Coverage: 17 of 31 days, very uneven (x = missing)")
    date_axis(ax, "%d")
    ax2 = ax.twinx()
    ax2.plot(d.EventDate, d.bot_share, color=ORANGE, marker="o", ms=3, lw=1.2)
    ax2.set_ylim(0, 0.6)
    pct_axis(ax2)
    ax2.set_ylabel("robot share of events", color=ORANGE)
    ax2.grid(False)
    ax2.spines["right"].set_visible(True)
    return save(fig, "p2_coverage")


def bots_effect():
    b = findings()["real"]["bots"]
    rows = [("Humans, robots kept\nin the history", b["humans_in_all_traffic"]), ("Robots", b["bots_in_all_traffic"]),
            ("Humans, robots removed\nbefore the replay", b["humans_bots_removed_before_replay"])]
    fig, ax = plt.subplots(figsize=(5.0, 3.0))
    x = np.arange(3)
    ax.bar(x - 0.2, [r[1]["fp"] for r in rows], 0.38, color=RED, label="false positive")
    ax.bar(x + 0.2, [r[1]["tp"] for r in rows], 0.38, color=BLUE, label="true positive")
    for i, r in enumerate(rows):
        ax.text(i - 0.2, r[1]["fp"] + 0.01, f"{r[1]['fp']:.1%}", ha="center", fontsize=8)
        ax.text(i + 0.2, r[1]["tp"] + 0.01, f"{r[1]['tp']:.1%}", ha="center", fontsize=8)
    ax.set_xticks(x, [r[0] for r in rows], fontsize=8)
    pct_axis(ax)
    ax.set_title("Robots: measured with and without (visit grain)")
    ax.legend(fontsize=8)
    return save(fig, "p2_bots")


# ------------------------------------------------------------------------------------------------ page 3 (REAL)
def tradeoff():
    t = pd.DataFrame(findings()["real"]["tolerant"])
    fig, ax = plt.subplots(figsize=(5.3, 3.6))
    ax.plot(t.fn, t.fp, color=BLUE, marker="o")
    for r in t.itertuples():
        ax.annotate(r.name, (r.fn, r.fp), textcoords="offset points", xytext=(6, -4 if r.variant != 1 else 6), fontsize=8,
                    color=RED if r.variant == 1 else INK)
    pct_axis(ax, "x", 1)
    pct_axis(ax)
    ax.set_xlabel("false-negative share (split)")
    ax.set_ylabel("false-positive share (merge)")
    ax.set_title("Stricter fingerprint: fewer merges, more splits")
    return save(fig, "p3_tradeoff")


def anonymity():
    b = pd.DataFrame(findings()["real"]["anonymity"]["buckets"])
    order = ["1", "2", "3-5", "6-20", "21-100", "101-1000", ">1000"]
    fig, ax = plt.subplots(figsize=(5.0, 3.2))
    for mob, col, lab, off in [(0, BLUE, "desktop", -0.2), (1, ORANGE, "mobile", 0.2)]:
        g = b[b.is_mobile == mob].set_index("set_size").reindex(order).fillna(0)
        share = g.users_total / g.users_total.sum()
        ax.bar(np.arange(len(order)) + off, share, 0.38, color=col, label=lab)
    ax.set_xticks(range(len(order)), order)
    ax.set_xlabel("users sharing the fingerprint (anonymity set)")
    pct_axis(ax)
    ax.set_ylabel("share of users")
    ax.set_title("Most users hide in crowds of look-alikes (15 Jul 2013)")
    ax.legend(fontsize=8)
    return save(fig, "p3_anonymity")


def calibration_real():
    c = findings()["real"]["calibration"]
    t = pd.DataFrame(c["reliability_test"])
    fig, ax = plt.subplots(figsize=(4.6, 3.6))
    ax.plot([0, 1], [0, 1], color=GREY, ls="--", lw=1, label="perfect calibration")
    ax.scatter(t.mean_score, t.observed_precision, s=np.clip(t.n / t.n.max() * 300, 15, 300), color=BLUE, alpha=0.8, label="later days of each site")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("score learnt on the first days (1 - FP share)")
    ax.set_ylabel("observed precision on later days")
    ax.set_title(f"Calibration holds out of sample (ECE {c['ece_test']:.3f})")
    ax.legend(fontsize=8, loc="upper left")
    return save(fig, "p3_calibration")


def entropy():
    e = pd.DataFrame(findings()["real"]["entropy"]).sort_values("entropy_bits")
    fig, ax = plt.subplots(figsize=(4.8, 3.9))
    cols = [GREY if a in ("IsMobile", "WindowClientWidth") else BLUE for a in e.attribute]
    ax.barh(e.attribute, e.entropy_bits, color=cols)
    ax.set_xlabel("Shannon entropy (bits), one profile per user")
    ax.tick_params(axis="y", labelsize=8)
    ax.set_title("What each attribute carries (grey = not used)")
    return save(fig, "p3_entropy")


# ------------------------------------------------------------------------------------------------ page 4 (REAL)
def uptake_curves():
    cal = findings()["public"]["adoption_curves_median"]
    fig, ax = plt.subplots(figsize=(5.0, 3.3))
    for fam, col in [("Chrome", BLUE), ("Firefox", ORANGE), ("Mobile Safari", RED)]:
        c = cal[fam]
        w = sorted(int(k) for k in c)
        ax.plot(w, [c[str(k)] for k in w], marker="o", ms=3, color=col, label=fam)
    pct_axis(ax)
    ax.set_xlabel("weeks after the official release")
    ax.set_ylabel("share already on that version or newer")
    ax.set_title("Real adoption speed (Wikimedia, median of releases)")
    ax.legend(fontsize=8)
    return save(fig, "p4_uptake")


def release_timeline():
    r = pd.DataFrame(findings()["public"]["releases_in_window"])
    r["release_date"] = pd.to_datetime(r.release_date)
    fig, ax = plt.subplots(figsize=(5.3, 2.4))
    ys = {"Chrome": 2, "Firefox": 1, "iOS": 0}
    for b, g in r.groupby("browser"):
        ax.scatter(g.release_date, [ys[b]] * len(g), color={"Chrome": BLUE, "Firefox": ORANGE, "iOS": RED}[b], s=40, zorder=3)
        for row in g.itertuples():
            ax.text(row.release_date, ys[b] + 0.18, row.major, fontsize=7.5, ha="center")
    ax.set_yticks([0, 1, 2], ["iOS", "Firefox", "Chrome"])
    ax.set_ylim(-0.5, 2.6)
    ax.set_xlim(pd.Timestamp("2026-08-24"), pd.Timestamp("2026-11-22"))
    date_axis(ax)
    ax.set_title("Real releases inside the 13 simulated weeks")
    ax.grid(axis="y", visible=False)
    return save(fig, "p4_releases")


def hits_rollout():
    v = findings()["real"]["version_rollout"]
    d = pd.DataFrame(v["daily_share"])
    d["day"] = pd.to_datetime(d.day)
    fig, ax = plt.subplots(figsize=(5.0, 3.0))
    for i, m in enumerate(v["majors"]):
        ax.plot(d.day, d[f"major_{m}"], marker="o", ms=3, color=[BLUE, ORANGE][i], label=f"version value {m}")
    pct_axis(ax)
    date_axis(ax, "%d %b")
    ax.set_ylabel("share of users of the main browser")
    ax.set_title("A real version change inside July 2013 (hits)")
    ax.legend(fontsize=8)
    return save(fig, "p4_hits_rollout")


def unique_devices():
    w = pd.read_csv(PROC / "wikimedia_detector.csv", parse_dates=["date"])
    fig, ax = plt.subplots(figsize=(5.3, 3.0))
    ax.plot(w.date, w.devices / 1e6, color=BLUE, lw=0.9)
    a = w[w.alert]
    ax.scatter(a.date, a.devices / 1e6, color=RED, s=14, zorder=3, label=f"detector alerts ({len(a)} days)")
    ax.set_ylabel("unique devices per day (millions)")
    ax.set_title("en.wikipedia unique devices, counted without fingerprinting")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    ax.legend(fontsize=8)
    return save(fig, "p4_unique_devices")


# ------------------------------------------------------------------------------------------------ page 5 (SIM)
def drift(metric, browser, major, start, fix, name, title):
    d = pd.read_csv(PROC / "monitoring_drift_series.csv", parse_dates=["event_date"])
    s = d[(d.metric == metric) & (d.browser == browser) & (d.browser_major == major)]
    s = s[(s.event_date >= pd.Timestamp(start) - pd.Timedelta(days=4)) & (s.event_date <= pd.Timestamp(fix) + pd.Timedelta(days=14))]
    fig, ax = plt.subplots(figsize=(5.3, 3.2))
    ax.plot(s.event_date, s.rate, color=BLUE, marker="o", ms=3, label=f"{browser} {major}, measured {metric.upper()} rate")
    ax.plot(s.event_date, s.p0, color=GREY, ls="-", lw=1.5, label="reference")
    al = s[s.alert]
    ax.scatter(al.event_date, al.rate, color=RED, s=40, zorder=4, label="alert")
    pct_axis(ax, d=1)
    date_axis(ax)
    ax.set_title(title)
    ax.legend(fontsize=7.5, loc="lower right" if metric == "fp" else "upper right")
    ax.set_ylim(0, max(s.rate.max(), s.p0.max()) * 1.25)
    vline(ax, start, "real release", GREY, 0.99)
    vline(ax, fix, "model fix", GREEN, 0.88)
    return save(fig, name)


def threshold_tradeoff():
    t = pd.DataFrame(findings()["sim"]["stats"]["threshold_tradeoff_c02"])
    fig, ax = plt.subplots(figsize=(4.8, 3.2))
    ax.plot(t.step_up_share, t.fp_caught_share, color=BLUE, marker="o")
    for r in t.itertuples():
        ax.annotate(f"{r.threshold:.2f}", (r.step_up_share, r.fp_caught_share), textcoords="offset points", xytext=(5, -10), fontsize=8,
                    color=RED if abs(r.threshold - 0.95) < 1e-9 else INK)
    pct_axis(ax, "x", 1)
    pct_axis(ax)
    ax.set_xlabel("answers sent to step-up (one-time code)")
    ax.set_ylabel("true false positives caught")
    ax.set_title("C02 threshold: friction vs merges caught")
    return save(fig, "p5_threshold")


# ------------------------------------------------------------------------------------------------ page 6 (SIM)
def c07_accounts():
    e = findings()["sim"]["e3"]["accounts_per_visitor"]
    scopes = [("all", "all traffic"), ("excl_bad_bots", "without robots"), ("excl_internal_and_bots", "without internal\ntraffic and robots")]
    fig, ax = plt.subplots(figsize=(5.0, 3.2))
    x = np.arange(3)
    ax.bar(x, [e[s]["max"] for s, _ in scopes], color=[RED, RED, BLUE])
    for i, (s, _) in enumerate(scopes):
        ax.text(i, e[s]["max"] * 1.15, f"max {e[s]['max']:,}\np99 {e[s]['p99']:.0f}", ha="center", fontsize=8)
    ax.set_yscale("log")
    ax.set_xticks(x, [l for _, l in scopes], fontsize=8)
    ax.set_ylabel("accounts linked to one visitor id (log)")
    ax.set_title("C07: the 'merged accounts' are support agents")
    ax.set_ylim(1, max(e[s]["max"] for s, _ in scopes) * 8)
    return save(fig, "p6_c07")


def p01_bots():
    d = sql("""select event_date, sum(bad_bot_events) * 1.0 / sum(events) bot, sum(events) ev
               from fct_accuracy_daily where customer_id = 'P01' group by 1 order by 1""")
    d["event_date"] = pd.to_datetime(d.event_date)
    fig, ax = plt.subplots(figsize=(5.0, 3.2))
    ax.bar(d.event_date, d.bot, color=np.where(d.bot > 0.1, RED, GREY), width=0.8)
    pct_axis(ax)
    date_axis(ax)
    ax.set_ylabel("bad-robot share of P01 requests")
    ax.set_title("P01 POC: the 'accuracy drop' is a robot wave")
    return save(fig, "p6_p01")


def c09_incognito():
    d = sql("""select week_start, incognito_share, fp_rate + fn_rate measured_err, truth_fp_rate + truth_fn_rate true_err
               from fct_accuracy_weekly_customer where customer_id = 'C09' order by 1""")
    d["week_start"] = pd.to_datetime(d.week_start)
    fig, ax = plt.subplots(figsize=(5.0, 3.2))
    ax.plot(d.week_start, d.measured_err, color=BLUE, marker="o", ms=3, label="measured error (control set)")
    ax.plot(d.week_start, d.true_err, color=RED, marker="o", ms=3, label="true error, all traffic (sim only)")
    ax.plot(d.week_start, d.incognito_share, color=GREY, ls="--", label="private-browsing share")
    pct_axis(ax)
    date_axis(ax)
    ax.set_title("C09: more private browsing, optimistic measurement")
    ax.legend(fontsize=7.5)
    vline(ax, "2026-10-12", "campaign", ORANGE, 0.99)
    return save(fig, "p6_c09")


# ------------------------------------------------------------------------------------------------ page 7 (SIM)
def c03_bridge():
    b = findings()["sim"]["e4"]["bridge"]
    labels = ["Their sessions\n(local days)", "Blocked\n(no proxy)", "Duplicates\nresidual", "Ours, local\ndays", "Time-zone\nshift", "Billed\n(UTC days)"]
    fig, ax = plt.subplots(figsize=(5.6, 3.4))
    run = 0
    for i, s in enumerate(b):
        v = s["value"]
        if i == 0 or s.get("subtotal"):
            ax.bar(i, v, color=BLUE if i == 0 else GREEN)
            run = v
            ax.text(i, v * 1.005, f"{v:,.0f}", ha="center", fontsize=8)
        else:
            bottom = run + min(v, 0)
            ax.bar(i, abs(v), bottom=bottom, color=RED if v < 0 else ORANGE)
            run += v
            ax.text(i, run + abs(v) + b[0]["value"] * 0.003 if v >= 0 else bottom + abs(v) + b[0]["value"] * 0.003, f"{v:+,.0f}", ha="center", fontsize=8)
    lo = min(s["value"] for s in b if s.get("subtotal")) * 0.85
    ax.set_ylim(lo, b[0]["value"] * 1.03)
    ax.set_xticks(range(len(labels)), labels, fontsize=7.5)
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v / 1e3:,.0f}k"))
    ax.set_title("C03, October 2026: from their number to ours")
    return save(fig, "p7_bridge")


def c03_daily():
    d = pd.DataFrame(findings()["sim"]["e4"]["dst_days"])
    exp = pd.read_csv(ROOT / "data" / "sample" / "C03_sessions_export.csv", parse_dates=["local_date"]) if (ROOT / "data" / "sample" / "C03_sessions_export.csv").exists() else None
    q = sql("select event_date, count(*) n from stg_identification_events where customer_id = 'C03' group by 1 order by 1")
    q["event_date"] = pd.to_datetime(q.event_date)
    m = exp.merge(q, left_on="local_date", right_on="event_date")
    m = m[(m.local_date >= "2026-10-15") & (m.local_date <= "2026-11-15")]
    fig, ax = plt.subplots(figsize=(5.3, 3.2))
    ax.plot(m.local_date, m.sessions / m.n - 1, color=RED, marker="o", ms=3, label="their sessions vs our UTC-day events")
    ax.plot(m.local_date, m.sessions_with_visitor_id / m.n - 1, color=BLUE, marker="o", ms=3, label="their sessions WITH a visitor id")
    ax.axhline(0, color=GREY, lw=1)
    pct_axis(ax)
    date_axis(ax)
    ax.set_title("Daily gaps: blocked requests + day boundaries")
    ax.legend(fontsize=7.5)
    vline(ax, "2026-11-01", "DST ends (New York)", GREY, 0.99)
    return save(fig, "p7_daily")


def incremental():
    r = pd.read_csv(PROC / "incremental_replay.csv")
    nb = pd.read_csv(PROC / "incremental_naive_by_load_day.csv")
    last = r[r.run_at == r.run_at.max()].set_index("event_date")
    days = list(last.index)
    nb = nb.set_index("report_day").reindex(days).fillna(0)
    fig, ax = plt.subplots(figsize=(5.3, 3.2))
    x = np.arange(len(days))
    ax.bar(x - 0.27, nb.rows_by_load_day / 1e3, 0.27, color=GREY, label="naive chart by load day")
    ax.bar(x, last.naive_pipeline_events / 1e3, 0.27, color=RED, label="naive append-only table")
    ax.bar(x + 0.27, last.incremental_model_events / 1e3, 0.27, color=BLUE, label="dbt incremental, 3-day lookback")
    ax.set_xticks(x, [d[5:] for d in days])
    ax.set_ylabel("events (thousands)")
    ax.set_title("Late partition (28 Oct) and re-sent rows (27 Oct)")
    ax.legend(fontsize=7.5, loc="lower left")
    return save(fig, "p7_incremental")


# ------------------------------------------------------------------------------------------------ page 8 (SIM)
def mix_weekly():
    w = pd.DataFrame(findings()["sim"]["e8"]["weeks"])
    w["week_start"] = pd.to_datetime(w.week_start)
    fig, ax = plt.subplots(figsize=(5.6, 3.4))
    ax.plot(w.week_start, w.fp_rate_crude, color=RED, marker="o", ms=4, label="crude (naive global dashboard)")
    ax.plot(w.week_start, w.fp_rate_standardized, color=BLUE, marker="o", ms=4, label="at constant traffic mix")
    ax.plot(w.week_start, w.fp_rate_stable_cohort, color=GREY, marker="o", ms=4, label="stable cohort of customers")
    pct_axis(ax, d=2)
    date_axis(ax)
    ax.set_ylim(0, w[["fp_rate_crude", "fp_rate_standardized"]].max().max() * 1.3)
    ax.set_title("Weekly false-positive rate: one jump, three readings")
    ax.legend(fontsize=8, loc="lower left")
    vline(ax, "2026-10-19", "C12 goes live", ORANGE, 0.99)
    return save(fig, "p8_mix")


def c12_segments():
    c = pd.DataFrame(findings()["sim"]["e8"]["c12_vs_others_same_segment"])
    fig, ax = plt.subplots(figsize=(4.8, 3.2))
    y = np.arange(len(c))
    for off, key, col, lab in [(-0.15, "others", GREY, "other customers"), (0.15, "c12", ORANGE, "C12")]:
        v = c[f"{key}_fp"]
        lo = v - c[f"{key}_ci"].map(lambda x: x[0])
        hi = c[f"{key}_ci"].map(lambda x: x[1]) - v
        ax.errorbar(v, y + off, xerr=[lo, hi], fmt="o", color=col, capsize=3, label=lab)
    ax.set_yticks(y, c.browser)
    pct_axis(ax, "x", 1)
    ax.set_title("Same segment, same rate (95% intervals)")
    ax.legend(fontsize=8)
    return save(fig, "p8_c12_segments")


def bootstrap_ci():
    """Width of the cluster-bootstrap interval relative to the Wilson interval, for a few customer x metric cases."""
    d = pd.DataFrame(findings()["sim"]["stats"]["design_effects"])
    d["label"] = d.customer_id + " " + d.metric + "\n" + d.events_per_visitor.map(lambda x: f"{x:.1f} ev./visitor")
    fig, ax = plt.subplots(figsize=(4.8, 3.0))
    ax.bar(d.label, d.width_ratio, color=[BLUE if r > 1.05 else GREY for r in d.width_ratio])
    ax.axhline(1, color=RED, lw=1, ls="--")
    for i, r in enumerate(d.itertuples()):
        ax.text(i, r.width_ratio + 0.01, f"x{r.width_ratio:.2f}", ha="center", fontsize=8.5)
    ax.set_ylim(0.8, d.width_ratio.max() * 1.12)
    ax.tick_params(axis="x", labelsize=8)
    ax.set_ylabel("cluster CI width / Wilson CI width")
    ax.set_title("Naive intervals are too narrow when visitors repeat")
    return save(fig, "p8_bootstrap")


# ------------------------------------------------------------------------------------------------ page 9 (SIM)
def health_grid():
    h = sql("select customer_id, week_start, health_status from mart_customer_health order by 1, 2")
    h["week_start"] = pd.to_datetime(h.week_start)
    weeks = sorted(h.week_start.unique())
    custs = sorted(h.customer_id.unique())
    colmap = {"green": "#2E7D4F", "amber": "#E0A030", "red": "#C0392B", "grey": "#C9C7C1"}
    fig, ax = plt.subplots(figsize=(5.4, 3.4))
    for r in h.itertuples():
        ax.add_patch(plt.Rectangle((weeks.index(r.week_start), custs.index(r.customer_id)), 0.92, 0.85, color=colmap[r.health_status]))
    ax.set_xlim(0, len(weeks))
    ax.set_ylim(len(custs), 0)
    ax.set_yticks(np.arange(len(custs)) + 0.42, custs, fontsize=8)
    ax.set_xticks(np.arange(len(weeks)) + 0.46, [pd.Timestamp(w).strftime("%d %b") for w in weeks], fontsize=7, rotation=90)
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title("Weekly health status per customer")
    return save(fig, "p9_health")


def queue():
    qd = findings()["sim"]["queue"]
    tiers = ["P1", "P2", "P3", "P4"]
    fig, ax = plt.subplots(figsize=(4.6, 3.0))
    vals = [qd["tier_counts"].get(t, 0) for t in tiers]
    ax.bar(tiers, vals, color=[RED, ORANGE, BLUE, GREY])
    for i, t in enumerate(tiers):
        bt = qd["by_tier"].get(t)
        if bt:
            ax.text(i, vals[i] + 1, f"{vals[i]}\nmedian {bt['median_hours']:.0f} h", ha="center", fontsize=8)
    ax.set_ylim(0, max(vals) * 1.35)
    ax.set_title(f"140 requests by priority ({qd['self_service_share']:.0%} self-servable)")
    ax.set_ylabel("requests")
    return save(fig, "p9_queue")


def build_all():
    return {
        "oss": oss_releases(), "grain": grain_outcomes(), "sites": site_spread(), "coverage": coverage(), "bots": bots_effect(),
        "tradeoff": tradeoff(), "anonymity": anonymity(), "calib": calibration_real(), "entropy": entropy(),
        "uptake": uptake_curves(), "releases": release_timeline(), "rollout": hits_rollout(), "udev": unique_devices(),
        "drift_chrome": drift("fn", "Chrome", 155, "2026-09-23", "2026-10-02", "p5_chrome155", "Chrome 155: false negatives tripled"),
        "drift_ios": drift("fp", "Mobile Safari", 27, "2026-09-14", "2026-10-07", "p5_ios27", "iOS 27 Mobile Safari: false positives"),
        "threshold": threshold_tradeoff(), "c07": c07_accounts(), "p01": p01_bots(), "c09": c09_incognito(),
        "bridge": c03_bridge(), "c03_daily": c03_daily(), "incremental": incremental(),
        "mix": mix_weekly(), "c12": c12_segments(), "boot": bootstrap_ci(), "health": health_grid(), "queue": queue(),
    }


if __name__ == "__main__":
    print(build_all())
