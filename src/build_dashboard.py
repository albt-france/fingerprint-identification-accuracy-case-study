"""Self-contained HTML dashboard with 6 tabs (dashboard/index.html), Plotly embedded once, no network needed.

Tabs: Accuracy monitor · Customer health · Book of business · Investigations · Request queue · Real data: ClickHouse replay.
Every chart carries its label (PUBLIC DATA or SIMULATED). Reads findings.json, data/processed and the dbt marts (read-only).

    python src/build_dashboard.py
"""
import html
import json
from pathlib import Path

import duckdb
import pandas as pd
import plotly.graph_objects as go
from plotly.offline import get_plotlyjs

ROOT = Path(__file__).resolve().parents[1]
PROC, DB = ROOT / "data" / "processed", ROOT / "dbt" / "fingerprint.duckdb"
OUT = ROOT / "dashboard" / "index.html"
BLUE, GREY, RED, ORANGE, GREEN, AMBER = "#2A78D6", "#A3A19A", "#D03B3B", "#EB6834", "#2E7D4F", "#E0A030"
STATUS_COL = {"green": GREEN, "amber": AMBER, "red": "#C0392B", "grey": "#C9C7C1"}
FOOTER = "Independent case study based on public data · not affiliated with or endorsed by Fingerprint"
F = json.loads((PROC / "findings.json").read_text(encoding="utf-8"))


def sql(q):
    with duckdb.connect(str(DB), read_only=True) as con:
        return con.sql(q).df()


def fig_html(fig, title, tag, note=""):
    fig.update_layout(template="plotly_white", margin=dict(l=50, r=20, t=40, b=40), height=340,
                      font=dict(family="Segoe UI, sans-serif", size=12), title=dict(text=title, font=dict(size=14)),
                      legend=dict(orientation="h", y=-0.18))
    div = fig.to_html(full_html=False, include_plotlyjs=False, config={"displaylogo": False, "responsive": True})
    cls = "public" if tag.startswith("PUBLIC") else "sim"
    return f'<div class="card"><span class="ctag {cls}">{tag}</span>{div}{f"<p class=note>{note}</p>" if note else ""}</div>'


def table_html(df, title, tag, max_rows=40):
    cls = "public" if tag.startswith("PUBLIC") else "sim"
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in df.columns)
    rows = "".join("<tr>" + "".join(f"<td>{html.escape(str(v))}</td>" for v in r) + "</tr>" for r in df.head(max_rows).itertuples(index=False))
    return f'<div class="card"><span class="ctag {cls}">{tag}</span><h3>{html.escape(title)}</h3><div class="tw"><table><tr>{head}</tr>{rows}</table></div></div>'


def kpis(items):
    return '<div class="kpis">' + "".join(f'<div class="kpi"><div class="v">{v}</div><div class="l">{l}</div></div>' for v, l in items) + "</div>"


# ------------------------------------------------------------------------------------------------ tabs
def tab_monitor():
    w = pd.DataFrame(F["sim"]["e8"]["weeks"])
    f1 = go.Figure()
    for col, name, c in [("fp_rate_crude", "crude (all customers)", RED), ("fp_rate_standardized", "constant traffic mix", BLUE),
                         ("fp_rate_stable_cohort", "stable cohort", GREY)]:
        f1.add_scatter(x=w.week_start, y=w[col], name=name, line=dict(color=c))
    f1.add_vline(x="2026-10-19", line_dash="dash", line_color=ORANGE)
    f1.update_yaxes(tickformat=".2%", rangemode="tozero")
    d = pd.read_csv(PROC / "monitoring_drift_series.csv")
    figs = []
    for metric, br, mj, title in [("fn", "Chrome", 155, "Chrome 155: measured FN rate vs reference"), ("fp", "Mobile Safari", 27, "iOS 27 Mobile Safari: measured FP rate vs reference")]:
        s = d[(d.metric == metric) & (d.browser == br) & (d.browser_major == mj)]
        f = go.Figure()
        f.add_scatter(x=s.event_date, y=s.rate, name="measured", line=dict(color=BLUE))
        f.add_scatter(x=s.event_date, y=s.p0, name="reference", line=dict(color=GREY))
        a = s[s.alert]
        f.add_scatter(x=a.event_date, y=a.rate, mode="markers", name="alert", marker=dict(color=RED, size=9))
        f.update_yaxes(tickformat=".1%", rangemode="tozero")
        figs.append(fig_html(f, title, "SIMULATED", "A new version is compared with the rest of its browser family for its first 28 days; after that its own history "
                             "(drift included) becomes the reference, which is why the iOS 27 reference rises after the fix." if br == "Mobile Safari" else
                             "Few users had updated yet: only the platform series by browser version could see it."))
    al = pd.read_csv(PROC / "monitoring_alerts.csv")
    al = al.assign(rate=lambda x: (100 * x.rate).round(2).astype(str) + "%", reference=lambda x: (100 * x.p0).round(2).astype(str) + "%",
                   z=lambda x: x.z.round(1), n=lambda x: x.n.astype(int), customer_id=lambda x: x.customer_id.fillna("all (platform)"),
                   matched_event=lambda x: x.matched_event.fillna(0).astype(int).astype(str).replace("0", "none (false alert)"))[["event_date", "level", "metric", "customer_id", "browser", "browser_major", "n", "rate", "reference", "ref_source", "z", "matched_event"]]
    m = F["monitoring"]
    k = kpis([(f"{m['recall_events_1_2_5_6']:.0%}", "hidden events caught (1, 2, 5, 6)"), (f"{m['segment_alerts']['precision']:.0%}", "precision of segment alerts"),
              (f"{m['false_alerts_per_week_all_monitors']:.2f}", "false alerts per week (on-call load)"),
              (f"{m['event_1']['delay_days']} / {m['event_2']['delay_days']} days", "detection delay, Chrome 155 / iOS 27")])
    return k + '<div class="g2">' + fig_html(f1, "Weekly FP rate: crude vs constant mix vs stable cohort", "SIMULATED",
                                             "The crude line jumps when C12 goes live; at constant mix nothing moves: no model incident.") + figs[0] + figs[1] + \
        table_html(al.sort_values("event_date"), "Alerts raised by the monitor (2-day persistence, BH FDR 1%)", "SIMULATED") + "</div>"


def tab_health():
    h = sql("select customer_id, cast(week_start as varchar) w, health_status, health_reasons, fp_rate, fn_rate from mart_customer_health order by 1, 2")
    custs = sorted(h.customer_id.unique())
    weeks = sorted(h.w.unique())
    code = {"grey": 0, "green": 1, "amber": 2, "red": 3}
    z = [[code.get(h[(h.customer_id == c) & (h.w == wk)].health_status.iloc[0], None) if len(h[(h.customer_id == c) & (h.w == wk)]) else None for wk in weeks] for c in custs]
    txt = [[(h[(h.customer_id == c) & (h.w == wk)].health_reasons.iloc[0] or "ok") if len(h[(h.customer_id == c) & (h.w == wk)]) else "" for wk in weeks] for c in custs]
    f = go.Figure(go.Heatmap(z=z, x=weeks, y=custs, text=txt, hovertemplate="%{y} %{x}<br>%{text}<extra></extra>", showscale=False, xgap=2, ygap=2,
                             colorscale=[[0, STATUS_COL["grey"]], [0.33, STATUS_COL["grey"]], [0.34, STATUS_COL["green"]], [0.66, STATUS_COL["green"]],
                                         [0.67, STATUS_COL["amber"]], [0.83, STATUS_COL["amber"]], [0.84, STATUS_COL["red"]], [1, STATUS_COL["red"]]], zmin=0, zmax=3))
    f.update_yaxes(autorange="reversed")
    f.update_layout(height=420)
    f2 = go.Figure()
    for c in custs:
        s = h[h.customer_id == c]
        f2.add_scatter(x=s.w, y=s.fp_rate, name=c, mode="lines", visible=True if c in ("C02", "C04", "C12") else "legendonly")
    f2.update_yaxes(tickformat=".2%")
    last = h[h.w == weeks[-1]][["customer_id", "health_status", "health_reasons"]].rename(columns={"health_reasons": "why"})
    return '<div class="g2">' + fig_html(f, "Weekly health status (grey = no baseline yet)", "SIMULATED", "Rules in METRICS.md section 6; hover for the reasons.") + \
        fig_html(f2, "Measured FP rate per customer (click the legend)", "SIMULATED") + table_html(last, f"Status, week of {weeks[-1]}", "SIMULATED") + \
        '<div class="card"><span class="ctag sim">SIMULATED</span><h3>Printable health reports</h3><ul>' + \
        "".join(f'<li><a href="../report/health_reports/{c}.html">{c}</a></li>' for c in ["C02", "C07", "C09", "P01"]) + "</ul></div></div>"


def tab_bob():
    b = sql("select csm_pod, cast(week_start as varchar) w, customers, arr_usd_simulated, red, amber, green, grey, arr_at_risk_usd_simulated, customers_to_watch, status_changes, open_requests from mart_book_of_business order by 2, 1")
    f = go.Figure()
    for pod, c in zip(sorted(b.csm_pod.unique()), [BLUE, ORANGE, GREEN]):
        s = b[b.csm_pod == pod]
        f.add_bar(x=s.w, y=s.arr_at_risk_usd_simulated, name=pod, marker_color=c)
    f.update_layout(barmode="group")
    f.update_yaxes(tickprefix="$")
    last = b[b.w == b.w.max()].drop(columns=["w"]).fillna("")
    return '<div class="g2">' + fig_html(f, "Simulated ARR of customers in red or amber, by CSM pod", "SIMULATED") + \
        table_html(last, f"Book of business, week of {b.w.max()}", "SIMULATED") + \
        '<div class="card"><span class="ctag sim">SIMULATED</span><h3>Weekly digests (drafts, never sent)</h3><ul>' + \
        "".join(f'<li><a href="../report/book_of_business/2026-11-16_{p}.html">{p}</a></li>' for p in ["POD-A", "POD-B", "POD-C"]) + "</ul></div></div>"


def tab_investigations():
    e3, e6, e4 = F["sim"]["e3"], F["sim"]["e6"], F["sim"]["e4"]
    sc = ["all", "excl_bad_bots", "excl_internal_and_bots"]
    f1 = go.Figure()
    f1.add_bar(x=sc, y=[e3["accounts_per_visitor"][s]["max"] for s in sc], name="max", marker_color=RED)
    f1.add_bar(x=sc, y=[e3["accounts_per_visitor"][s]["p99"] for s in sc], name="99th percentile", marker_color=BLUE)
    f1.update_yaxes(type="log")
    p = sql("select event_date, sum(bad_bot_events) * 1.0 / sum(events) bot from fct_accuracy_daily where customer_id = 'P01' group by 1 order by 1")
    f2 = go.Figure(go.Bar(x=p.event_date, y=p.bot, marker_color=[RED if v > 0.1 else GREY for v in p.bot]))
    f2.update_yaxes(tickformat=".0%")
    c = sql("select week_start, incognito_share, fp_rate + fn_rate m, truth_fp_rate + truth_fn_rate t from fct_accuracy_weekly_customer where customer_id = 'C09' order by 1")
    f3 = go.Figure()
    f3.add_scatter(x=c.week_start, y=c.m, name="measured error (control set)", line=dict(color=BLUE))
    f3.add_scatter(x=c.week_start, y=c.t, name="true error, all traffic", line=dict(color=RED))
    f3.add_scatter(x=c.week_start, y=c.incognito_share, name="private-browsing share", line=dict(color=GREY, dash="dash"))
    f3.update_yaxes(tickformat=".0%")
    br = e4["bridge"]
    f4 = go.Figure(go.Waterfall(x=["their sessions", "blocked", "duplicates", "ours, local days", "time zone", "billed, UTC"],
                                measure=["absolute", "relative", "relative", "total", "relative", "total"], y=[s["value"] for s in br],
                                connector=dict(line=dict(color=GREY))))
    f4.update_yaxes(range=[min(s["value"] for s in br if s.get("subtotal")) * 0.9, br[0]["value"] * 1.02])
    return '<div class="g2">' + \
        fig_html(f1, "C07: accounts per visitor id (log scale)", "SIMULATED", f"{e3['internal_rule']['flagged']} internal visitors flagged; precision {e3['internal_rule']['precision']:.0%}, recall {e3['internal_rule']['recall']:.0%} against the simulated truth.") + \
        fig_html(f2, "P01 POC: daily bad-robot share", "SIMULATED", f"Visitors per account during the wave: {e6['visitors_per_account_wave_all']} with robots, {e6['visitors_per_account_wave_excl_bots']} without.") + \
        fig_html(f3, "C09: private browsing and the measurement bias", "SIMULATED") + \
        fig_html(f4, "C03, October 2026: reconciliation bridge", "SIMULATED", f"Their total is {e4['their_over_ours_pct']:+.1%} above ours; unexplained residual {e4['residual_share']:.2%}.") + "</div>"


def tab_queue():
    q = sql("select * from mart_request_queue")
    f1 = go.Figure()
    for team, c in [("CS", BLUE), ("SE", ORANGE), ("Product", GREY)]:
        s = q[q.requesting_team == team].priority_tier.value_counts().reindex(["P1", "P2", "P3", "P4"]).fillna(0)
        f1.add_bar(x=s.index, y=s.values, name=team, marker_color=c)
    f1.update_layout(barmode="stack")
    f2 = go.Figure()
    for t in ["P1", "P2", "P3", "P4"]:
        f2.add_box(y=q[q.priority_tier == t].hours_to_resolve, name=t)
    f2.update_yaxes(title="hours to resolve")
    wk = q.groupby(["week_opened", "self_service_possible"]).size().unstack(fill_value=0).reset_index()
    f3 = go.Figure()
    f3.add_bar(x=wk.week_opened, y=wk.get(True, 0), name="self-service possible", marker_color=GREEN)
    f3.add_bar(x=wk.week_opened, y=wk.get(False, 0), name="needs an analyst", marker_color=BLUE)
    f3.update_layout(barmode="stack")
    qq = F["sim"]["queue"]
    k = kpis([(str(qq["requests"]), "requests in 13 weeks"), (f"{qq['self_service_share']:.0%}", "could be self-served"),
              (f"{qq['self_service_hours_share']:.0%}", "of analyst hours on self-servable questions"), (str(qq["open_at_end"]), "open at the end")])
    top = q[q.is_open].sort_values("priority_score", ascending=False)[["request_id", "priority_tier", "customer_id", "requesting_team", "title", "urgency"]]
    return k + '<div class="g2">' + fig_html(f1, "Requests by priority and team", "SIMULATED") + fig_html(f2, "Time to resolve by priority", "SIMULATED") + \
        fig_html(f3, "Requests opened per week", "SIMULATED") + table_html(top, "Open requests, highest priority first", "SIMULATED") + "</div>"


def tab_real():
    r = F["real"]
    gr = [("event", r["replay"]["event"]), ("visit", r["replay"]["visit"]), ("user-day", r["replay"]["day"])]
    f1 = go.Figure()
    for key, name, c in [("tp", "true positive", BLUE), ("fp", "false positive", RED), ("fn", "false negative", ORANGE), ("tn", "true new", GREY)]:
        f1.add_bar(y=[g[0] for g in gr], x=[g[1][key] for g in gr], name=name, orientation="h", marker_color=c)
    f1.update_layout(barmode="stack")
    f1.update_xaxes(tickformat=".0%")
    s = pd.DataFrame(r["replay"]["sites"])
    f2 = go.Figure()
    f2.add_scatter(x=s.fp_event, y=s.fp_visit, mode="markers", text=s.site, marker=dict(size=8, color=BLUE), hovertemplate="site %{text}<br>event %{x:.1%}<br>visit %{y:.1%}<extra></extra>")
    f2.add_scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(color=GREY, dash="dash"), name="same at both grains")
    f2.update_xaxes(tickformat=".0%", title="FP share, event grain")
    f2.update_yaxes(tickformat=".0%", title="FP share, visit grain")
    t = pd.DataFrame(r["tolerant"])
    f3 = go.Figure(go.Scatter(x=t.fn, y=t.fp, mode="lines+markers+text", text=t.name, textposition="top right", line=dict(color=BLUE)))
    f3.update_xaxes(tickformat=".1%", title="false-negative share")
    f3.update_yaxes(tickformat=".0%", title="false-positive share")
    c = pd.DataFrame(r["calibration"]["reliability_test"])
    f4 = go.Figure()
    f4.add_scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(color=GREY, dash="dash"), name="perfect")
    f4.add_scatter(x=c.mean_score, y=c.observed_precision, mode="markers", marker=dict(size=10, color=BLUE), name="later days")
    p = r["profile"]
    k = kpis([(f"{p['rows'] / 1e6:.0f}M", "real events replayed (ClickHouse)"), (f"{p['days_present']} / 31", "days present in July 2013"),
              (f"{r['reconciliation']['total_abs_diff']}", f"DuckDB vs ClickHouse difference on {r['reconciliation']['sites']} sites"),
              (f"{r['playground']['queries_sent']} / 150", "playground queries used")])
    return k + '<div class="g2">' + fig_html(f1, "Outcome shares by grain (30 largest sites)", "PUBLIC DATA",
                                             "Real anonymised 2013 traffic (ClickBench, CC BY-NC-SA 4.0). Illustrative 16-attribute fingerprint, not Fingerprint's algorithm.") + \
        fig_html(f2, "Each site: FP share at event vs visit grain", "PUBLIC DATA") + fig_html(f3, "Strict to loose fingerprint: the FP / FN trade-off", "PUBLIC DATA") + \
        fig_html(f4, f"Illustrative confidence score, out of sample (ECE {r['calibration']['ece_test']:.3f})", "PUBLIC DATA") + "</div>"


CSS = """
*{box-sizing:border-box} body{margin:0;background:#F4F4F2;color:#0B0B0B;font:14px/1.45 'Segoe UI',system-ui,sans-serif}
header{padding:18px 26px 6px} h1{font-size:22px;margin:0} .sub{color:#52514E;margin:4px 0 10px}
nav{display:flex;gap:6px;padding:0 26px;flex-wrap:wrap} nav button{border:1px solid #E1E0D9;background:#fff;padding:8px 14px;border-radius:6px 6px 0 0;cursor:pointer;font:inherit}
nav button.on{background:#0B0B0B;color:#fff} section{display:none;padding:14px 26px} section.on{display:block}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:12px} .card{position:relative;background:#fff;border:1px solid #E1E0D9;border-radius:8px;padding:10px 12px;min-width:0}
.ctag{position:absolute;top:8px;right:10px;font-size:10px;font-weight:700;letter-spacing:.06em;padding:2px 6px;border-radius:3px;z-index:2}
.ctag.public{background:#E3EEFB;color:#1C5CAB} .ctag.sim{background:#FBE9E0;color:#9A3B12}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:12px} .kpi{background:#fff;border:1px solid #E1E0D9;border-radius:8px;padding:12px}
.kpi .v{font-size:24px;font-weight:700} .kpi .l{color:#52514E;font-size:12px}
h3{font-size:14px;margin:2px 0 8px} .tw{max-height:330px;overflow:auto} table{border-collapse:collapse;width:100%;font-size:12px}
th,td{text-align:left;padding:3px 6px;border-bottom:1px solid #EFEEE9} th{color:#52514E;position:sticky;top:0;background:#fff}
.note{font-size:12px;color:#52514E;margin:4px 0 0} footer{padding:10px 26px 20px;color:#898781;font-size:12px}
@media(max-width:900px){.g2,.kpis{grid-template-columns:1fr}}
"""
JS = """
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{
 document.querySelectorAll('nav button,section').forEach(x=>x.classList.remove('on'));
 b.classList.add('on'); const s=document.getElementById(b.dataset.t); s.classList.add('on');
 s.querySelectorAll('.js-plotly-plot').forEach(el=>Plotly.Plots.resize(el));});
"""


def main():
    tabs = [("monitor", "Accuracy monitor", tab_monitor()), ("health", "Customer health", tab_health()), ("bob", "Book of business", tab_bob()),
            ("inv", "Investigations", tab_investigations()), ("queue", "Request queue", tab_queue()), ("real", "Real data: ClickHouse replay", tab_real())]
    nav = "".join(f'<button data-t="{k}" class="{"on" if i == 0 else ""}">{t}</button>' for i, (k, t, _) in enumerate(tabs))
    secs = "".join(f'<section id="{k}" class="{"on" if i == 0 else ""}">{body}</section>' for i, (k, _, body) in enumerate(tabs))
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Identification accuracy dashboard</title><style>{CSS}</style><script>{get_plotlyjs()}</script></head><body>
<header><h1>Identification accuracy analytics</h1><div class="sub">Case study for an identification-accuracy analyst role at Fingerprint.
SIMULATED tabs show a fictional identification platform with fictional customers (C01-C12, P01, P02), 24 Aug to 22 Nov 2026;
PUBLIC DATA shows real anonymised 2013 web traffic replayed in ClickHouse. No Fingerprint data.</div></header>
<nav>{nav}</nav>{secs}<footer>{FOOTER}</footer><script>{JS}</script></body></html>"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(doc, encoding="utf-8")
    print("written", OUT.relative_to(ROOT), f"{OUT.stat().st_size / 1e6:.1f} MB")
    screenshot()


def screenshot():
    """PNG of the first tab for the README (headless Edge, temporary profile)."""
    import shutil
    import subprocess
    import tempfile
    edge = Path(r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
    if not edge.exists():
        return
    prof = tempfile.mkdtemp()
    png = ROOT / "report" / "img" / "dashboard_screenshot.png"
    png.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(edge), "--headless=new", "--disable-gpu", f"--user-data-dir={prof}", "--window-size=1500,1080",
                    "--virtual-time-budget=8000", f"--screenshot={png}", OUT.as_uri()], timeout=120, capture_output=True)
    shutil.rmtree(prof, ignore_errors=True)


if __name__ == "__main__":
    main()
