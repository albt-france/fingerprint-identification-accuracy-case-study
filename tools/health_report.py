"""Accuracy HEALTH REPORT of one customer: a printable one-page HTML for Customer Success (SIMULATED data).

    python tools/health_report.py --customer C07            # -> report/health_reports/C07.html
    python tools/health_report.py --all-examples            # C02, C07, C09, P01

Plain language first, numbers second, definitions at the bottom. Reads the dbt marts read-only.
"""
import argparse
import json
import re
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import accuracy_core as core  # noqa: E402
import metrics  # noqa: E402
from report_style import CSS, FOOTER, esc, svg_lines  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report" / "health_reports"
NOTES = ROOT / "tools" / "templates" / "analyst_notes.json"
REPORT_WEEK = "2026-11-16"
EXAMPLES = ["C02", "C07", "C09", "P01"]


def fill(template):
    """Replace {path|format} placeholders with values from findings.json (e.g. {sim.e6.bot_share_wave|.0%})."""
    if not template:
        return template
    f = json.loads((ROOT / "data" / "processed" / "findings.json").read_text(encoding="utf-8"))

    def get(path):
        v = f
        for part in path.split("."):
            v = v[int(part)] if isinstance(v, list) else v[part]
        return v

    def rep(m):
        path, _, fmt = m.group(1).partition("|")
        return format(get(path), fmt) if fmt else str(get(path))
    return re.sub(r"\{([a-zA-Z0-9_.]+(?:\|[^}]*)?)\}", rep, template)


def build(cid: str) -> Path:
    cid = core.check_customer(cid)
    con = duckdb.connect(str(core.DB), read_only=True)
    cust = con.execute("select * from stg_customers where customer_id = ?", [cid]).df().iloc[0]
    wk = con.execute("select * from mart_customer_health where customer_id = ? order by week_start", [cid]).df()
    weekly = con.execute("select * from fct_accuracy_weekly_customer where customer_id = ? order by week_start", [cid]).df()
    cur = wk[wk["week_start"].astype(str) == REPORT_WEEK].iloc[0]
    # last 4 weeks vs previous 4 weeks, control set, bad robots excluded
    d = con.execute("""select case when event_date >= date '2026-10-26' then 'recent' when event_date >= date '2026-09-28' then 'previous' end as p,
                              sum(control_events) n, sum(fp) fp, sum(fn) fn, sum(found_events) found, sum(below_threshold_events) below,
                              sum(events) ev, sum(bad_bot_events) bots, sum(incognito_events) inc, sum(human_events) hum
                       from fct_accuracy_daily where customer_id = ? and event_date >= date '2026-09-28' group by 1""", [cid]).df().dropna().set_index("p")
    by_browser = con.execute("""select browser, sum(control_events) n, sum(fp) fp, sum(fn) fn from fct_accuracy_daily
                                where customer_id = ? and event_date >= date '2026-10-26' group by 1 order by n desc""", [cid]).df()
    linked = con.execute("select * from mart_linked_id_metrics where customer_id = ? order by scope", [cid]).df()
    reqs = con.execute("""select request_id, title, priority_tier, urgency, cast(opened_at as date) as opened, is_open
                          from mart_request_queue where customer_id = ? order by opened_at desc limit 5""", [cid]).df()
    con.close()
    phi = core._phi()
    r = d.loc["recent"]
    has_prev = "previous" in d.index and d.loc["previous", "n"] > 0
    fp_ci, fn_ci = metrics.wilson(r.fp, r.n), metrics.wilson(r.fn, r.n)
    chg_fp = metrics.two_proportion_test(d.loc["previous", "fp"], d.loc["previous", "n"], r.fp, r.n, phi) if has_prev else None
    chg_fn = metrics.two_proportion_test(d.loc["previous", "fn"], d.loc["previous", "n"], r.fn, r.n, phi) if has_prev else None

    def change_text(t, name):
        if t is None:
            return f"No previous period to compare the {name} rate with (new customer)."
        if t["p_value"] < 0.01:
            return f"The {name} rate moved from {core.pct(t['rate_a'])} to {core.pct(t['rate_b'])}: a real change, not noise."
        return f"The {name} rate is stable ({core.pct(t['rate_a'])} then {core.pct(t['rate_b'])}): the difference is within normal noise."

    notes = json.loads(NOTES.read_text(encoding="utf-8")) if NOTES.exists() else {}
    note = fill(notes.get(cid))
    labels = [str(w)[5:10] for w in weekly["week_start"]]
    chart = svg_lines([
        {"name": "False-positive rate", "color": "#b83232", "y": weekly["fp_rate"].tolist(), "lo": weekly["fp_rate_lo"].tolist(), "hi": weekly["fp_rate_hi"].tolist()},
        {"name": "False-negative rate", "color": "#2f5d8a", "y": weekly["fn_rate"].tolist(), "lo": weekly["fn_rate_lo"].tolist(), "hi": weekly["fn_rate_hi"].tolist()},
    ], x_labels=labels)
    status_hist = "".join(f'<span class="badge {s}" title="{esc(w)}" style="padding:2px 6px;margin-right:2px;font-size:9px">{s[0]}</span>'
                          for w, s in zip(wk["week_start"].astype(str), wk["health_status"]))
    rows_b = "".join(f"<tr><td>{esc(b.browser)}</td><td class='n'>{int(b.n):,}</td><td class='n'>{core.pct(b.fp / b.n if b.n else None)}</td>"
                     f"<td class='n'>{core.pct(b.fn / b.n if b.n else None)}</td></tr>" for b in by_browser.itertuples() if b.n >= 200)
    linked_html = ""
    if len(linked):
        L = linked.set_index("scope")
        linked_html = f"""<div class="card"><h2>Your own accounts (customer-specific metrics from linkedId)</h2>
        <table><tr><th>Scope</th><th class='n'>Accounts per visitor (mean / 99th pct / max)</th><th class='n'>Visitors per account (mean / 99th pct)</th></tr>
        {''.join(f"<tr><td>{esc(s.replace('_', ' '))}</td><td class='n'>{L.loc[s, 'accounts_per_visitor_mean']:.2f} / {L.loc[s, 'accounts_per_visitor_p99']:.0f} / {L.loc[s, 'accounts_per_visitor_max']:.0f}</td><td class='n'>{L.loc[s, 'visitors_per_account_mean']:.2f} / {L.loc[s, 'visitors_per_account_p99']:.0f}</td></tr>" for s in ['all', 'excl_bad_bots', 'excl_internal_and_bots'] if s in L.index)}
        </table><div class="foot">"Internal" = visitors linked to 20+ accounts on a network shared by 5+ such visitors (support or call-centre agents).</div></div>"""
    rows_q = "".join(f"<tr><td>{esc(q.request_id)}</td><td>{esc(q.title)}</td><td>{esc(q.priority_tier)}</td><td>{q.opened}</td><td>{'open' if q.is_open else 'resolved'}</td></tr>" for q in reqs.itertuples())
    below_prev = d.loc["previous", "below"] / d.loc["previous", "found"] if has_prev and d.loc["previous", "found"] else None
    html_doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Accuracy health {cid}</title><style>{CSS}</style></head><body><div class="page">
<h1>Accuracy health report · {cid} <span class="tag">SIMULATED</span></h1>
<div class="sub">{esc(cust.sector)} · {esc(cust.use_case)} · {esc(cust.csm_pod)} · confidence threshold {cust.confidence_threshold} ·
week of {REPORT_WEEK} · fictional customer of a simulated identification platform</div>
<div class="card"><span class="badge {cur.health_status}">{cur.health_status}</span>
&nbsp; <b>{esc(cur.health_reasons) if cur.health_reasons else "No accuracy change, no robot or incognito alert, no urgent request."}</b>
<div style="margin-top:8px">{esc(change_text(chg_fp, 'false-positive'))} {esc(change_text(chg_fn, 'false-negative'))}</div>
{f'<div style="margin-top:8px"><b>Analyst note.</b> {esc(note)}</div>' if note else ''}
<div class="foot">Status by week (oldest to latest): {status_hist}</div></div>
<div class="grid">
<div class="card kpi"><div class="v">{core.pct(r.fp / r.n)}</div><div class="l">False-positive rate, last 4 weeks<br>95% CI {core.pct(fp_ci[0])}-{core.pct(fp_ci[1])}</div></div>
<div class="card kpi"><div class="v">{core.pct(r.fn / r.n)}</div><div class="l">False-negative rate, last 4 weeks<br>95% CI {core.pct(fn_ci[0])}-{core.pct(fn_ci[1])}</div></div>
<div class="card kpi"><div class="v">{core.pct(r.below / r.found if r.found else None, 1)}</div><div class="l">Answers under your confidence threshold<br>(previous 4 weeks: {core.pct(below_prev, 1)})</div></div>
<div class="card kpi"><div class="v">{core.pct(r.bots / r.ev, 1)}</div><div class="l">Bad-robot share of requests<br>incognito share {core.pct(r.inc / r.hum, 1)}</div></div>
</div>
<div class="two"><div class="card"><h2>Weekly error rates with 95% intervals</h2>{chart}</div>
<div class="card"><h2>By browser, last 4 weeks</h2><table><tr><th>Browser</th><th class='n'>Control events</th><th class='n'>FP rate</th><th class='n'>FN rate</th></tr>{rows_b}</table>
<div class="foot">Browsers with fewer than 200 control events are hidden (too few to read a rate).</div></div></div>
{linked_html}
<div class="card"><h2>Recent requests about this customer</h2><table><tr><th>Id</th><th>Request</th><th>Priority</th><th>Opened</th><th>State</th></tr>{rows_q or '<tr><td colspan=5>None</td></tr>'}</table></div>
<div class="foot"><b>Definitions.</b> Measured like Fingerprint documents it: events identified with a deterministic signal (control set) are
re-identified without it. <b>False positive</b>: recognised as another existing visitor (two people merged). <b>False negative</b>: a returning
visitor treated as new (one person split). Rates exclude requests flagged as bad robots. The confidence score is 1 minus the estimated probability
of a false positive. Intervals: Wilson 95%. "Real change" = two-period test with over-dispersion {phi:.1f}, p &lt; 0.01.
Private-browsing traffic cannot be measured this way, so the measured rates are optimistic when its share grows.<br>{FOOTER}</div>
</div></body></html>"""
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{cid}.html"
    path.write_text(html_doc, encoding="utf-8")
    return path


def main(argv=None):
    p = argparse.ArgumentParser(description="One-page accuracy health report (SIMULATED data).")
    p.add_argument("--customer")
    p.add_argument("--all-examples", action="store_true")
    a = p.parse_args(argv)
    ids = EXAMPLES if a.all_examples or not a.customer else [a.customer]
    for cid in ids:
        print("written", build(cid).relative_to(ROOT))


if __name__ == "__main__":
    main()
