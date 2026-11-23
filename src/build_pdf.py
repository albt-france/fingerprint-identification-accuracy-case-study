"""Build the 11-page PDF: charts (src/charts.py) -> HTML pages (16:9) -> PDF with headless Edge, empty metadata.

Every number is read from data/processed/findings.json, so the report matches the code.
    python src/build_pdf.py
Outputs: report/report.html (intermediate, not published), report/Fingerprint_identification_accuracy.pdf
"""
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from pypdf import PdfReader, PdfWriter

import charts

ROOT = Path(__file__).resolve().parents[1]
REP, PROC = ROOT / "report", ROOT / "data" / "processed"
PDF_NAME = "Fingerprint_identification_accuracy.pdf"
N_PAGES = 11
DISCLAIMER = "Independent case study based on public data · not affiliated with or endorsed by Fingerprint"
AI_NOTE = ("AI-assisted workflow: I used Claude, mainly to write scripts faster. I drove the project: I defined the questions, "
           "chose and validated the data sources, made the analytical decisions and checked every result.")
TITLE = "Is it the model, the mix or the measurement? Identification-accuracy analytics for Fingerprint"
DOC = "docs.fingerprint.com/docs/identification-accuracy-and-confidence (read 23 Nov 2026)"


def pct(x, d=0, sign=False):
    return f"{x * 100:{'+' if sign else ''}.{d}f}%"


def n0(x):
    return f"{x:,.0f}"


def page(n, title, subtitle, tags, body, sources):
    t = "".join(f'<div class="tag tag-{x.lower().split()[0]}">{x}</div>' for x in tags)
    return f"""
<section class="page">
  <header><div><h1>{title}</h1><p class="sub">{subtitle}</p></div><div class="tags">{t}</div></header>
  <main>{body}</main>
  <footer><span>{sources}</span><span>{DISCLAIMER}</span><span>{n + 1} / {N_PAGES}</span></footer>
</section>"""


def card(inner, cls="", tag=None):
    tg = f'<span class="ctag ctag-{tag.lower().split()[0]}">{tag}</span>' if tag else ""
    return f'<div class="card {cls}">{tg}{inner}</div>'


def img(src, tag, cap=""):
    return card(f'<figure><img src="{src}"/>{f"<figcaption>{cap}</figcaption>" if cap else ""}</figure>', "fig", tag)


def tile(label, value, text, tag):
    return card(f'<div class="label">{label}</div><div class="big">{value}</div><p>{text}</p>', "tile", tag)


# ------------------------------------------------------------------ pages
def p0(f, ch):
    r, s, m = f["real"], f["sim"], f["monitoring"]
    tiles = "".join([
        tile("GRAIN", f"{pct(r['replay']['event']['fp'])} → {pct(r['replay']['visit']['fp'])}",
             f"False-positive share of the same replay of Fingerprint's accuracy method on {r['replay']['events_top30'] / 1e6:.0f}M real events, event vs visit grain.", "PUBLIC DATA"),
        tile("TWO ENGINES, ONE ANSWER", str(r["reconciliation"]["total_abs_diff"]),
             f"Difference between DuckDB and ClickHouse on {r['reconciliation']['sites']} real sites ({n0(r['reconciliation']['event_rows'])} events), 6 measures, 2 grains.", "PUBLIC DATA"),
        tile("THE FALSE SIGNAL", f"{pct(s['e8']['crude_change'], 0, True)} vs {pct(s['e8']['standardized_change'], 1, True)}",
             "Weekly platform FP rate the week a mobile-heavy customer goes live: crude vs constant traffic mix. No model incident.", "SIMULATED"),
        tile("MONITOR BACK-TEST", f"{m['recall_events_1_2_5_6']:.0%} · {m['false_alerts_per_week_all_monitors']:.2f}",
             f"Hidden events caught · false alerts per week. Chrome 155 drift caught in {m['event_1']['delay_days']} days, before the mass roll-out.", "SIMULATED"),
    ])
    qs = """<ol class="qs">
<li>How does Fingerprint's published accuracy method behave on real event data, and what does the <b>grain</b> do to it?</li>
<li>What drives the trade-off between <b>merging</b> people (FP) and <b>splitting</b> them (FN), and can a confidence score stay calibrated?</li>
<li>Can monitoring catch an accuracy drift after a browser release <b>before customers notice</b>, without paging on-call for nothing?</li>
<li>When a customer complains, is it the <b>model</b>, the <b>mix</b> of traffic or the <b>measurement</b>? How do we prove it and explain it?</li>
<li>Which questions should never reach an analyst again: what <b>self-service tools</b> (including an MCP server) remove them?</li></ol>"""
    reco = f"""<ul class="reco">
<li><b>Always show a constant-mix line</b> next to any platform accuracy rate; annotate onboardings. It would have avoided a false model incident (page 9).</li>
<li><b>Watch every new browser version against its family</b> for 28 days: a new version has no history, and drifts happen exactly then (page 6).</li>
<li><b>Never read a customer's merged-accounts metric before removing internal traffic and robots</b>: at C07 the max dropped from {n0(s['e3']['accounts_per_visitor']['all']['max'])} to {s['e3']['accounts_per_visitor']['excl_internal_and_bots']['max']} (page 7).</li>
<li><b>Report accuracy by traffic type</b>: the control set cannot see private browsing, so the headline rate is optimistic when it grows (page 7).</li>
<li><b>Reconcile with a bridge, not an argument</b>: blocked requests, time zones, duplicates, each measured (page 8).</li></ul>"""
    flow = '<div class="flow">' + "".join(f'<div class="step">{x}</div>' for x in ["Monitor", "Detect", "Triage", "Investigate", "Reconcile", "Explain", "Tool", "Document"]) + "</div>"
    mmm = """<div class="mmm"><div><b>Model</b><br>rates move <i>inside</i> segments<br>→ engineering, release calendar</div>
<div><b>Mix</b><br>only the composition moves<br>→ standardize, fix the dashboard</div>
<div><b>Measurement</b><br>grain, control set, time zone, duplicates<br>→ fix the metric or the pipeline</div></div>"""
    method = f"""<p><b>Real part (PUBLIC DATA)</b>: ClickBench <code>hits</code> ({r['profile']['rows'] / 1e6:.0f}M anonymised 2013 web-analytics events) queried in a real ClickHouse
(public read-only playground, {r['playground']['queries_sent']} queries); real browser release calendars and Wikimedia adoption curves.
<b>Simulated part</b>: a fictional identification platform, 12 customers + 2 prospects, {s['volume']['events'] / 1e6:.1f}M events over 13 weeks with a hidden
truth and 8 hidden events. Stack: ClickHouse SQL, dbt ({f['dbt']['models']} models, {f['dbt']['data_tests']} data tests, {f['dbt']['unit_tests']} unit tests, incremental), Python, Prefect, MCP.</p>"""
    deliver = """<h2 style="margin-top:10px">What an identification-accuracy analyst delivers here</h2><table class="small">
<tr><th>Deliverable</th><th>For whom</th><th>Where</th></tr>
<tr><td>Accuracy monitor with alerting back-tested on 13 weeks</td><td>on-call, engineering</td><td>src/monitoring.py, dashboard tab 1</td></tr>
<tr><td>Weekly health report per customer, weekly book-of-business per pod</td><td>Customer Success</td><td>report/health_reports, report/book_of_business</td></tr>
<tr><td>Six investigation playbooks, three customer explainers</td><td>CS, SE, customers</td><td>docs/playbooks, docs/customer_explainers</td></tr>
<tr><td>dbt project (incremental, tested, documented), ClickHouse SQL and DDL</td><td>data team</td><td>dbt/, clickhouse/</td></tr>
<tr><td>Self-service CLI and read-only MCP server</td><td>CS, SE, Product</td><td>tools/</td></tr></table>"""
    body = f"""<div class="grid4">{tiles}</div>
<div class="grid-2-1">{card('<h2>Five questions</h2>' + qs + '<h2 style="margin-top:8px">How the work is organised</h2>' + flow + mmm + deliver)}{card('<h2>Recommendations</h2>' + reco + '<h2>Method</h2>' + method)}</div>"""
    return page(0, TITLE, "A case study for the Data Analyst, Identification Accuracy role: replay the published accuracy method on 100M real events, then run 13 weeks of a simulated platform end to end.",
                ["OVERVIEW"], body, "Sources: page 11")


def p1(f, ch):
    fp = f["fingerprint"]
    j, o, c = fp["job"], fp["oss_repo"], fp["careers"]
    facts = f"""<ul class="facts">
<li><b>FingerprintJS, Inc.</b>, an all-remote company. Its Identification API processes <b>approximately {j['requests_per_month_as_stated']} requests per month</b>, as stated by Fingerprint in the job post.</li>
<li>As stated in the job post: $77M raised; 2026 Forbes Best Startup Employers list; #803 on the 2026 Inc. 5000; customers include Plaid, Dropbox and Booking.com.</li>
<li>Careers site (Greenhouse API, 23 Nov 2026): <b>{c['open_roles']} open roles</b>, {'all' if c['all_remote'] else 'mostly'} remote. This role: {j['title'].strip()}, {j['department']}, ref. {j['requisition_id']}, first published {j['first_published'][:10]}.</li>
<li>Open source: <b>{o['name']}</b>, {n0(o['stars'])} stars, {o['license']} licence, {o['releases']} releases since {o['first_release'][:4]}, latest {o['latest_release']} on {o['latest_release_date']}.</li>
<li>Public docs describe accuracy, the confidence score, <code>linkedId</code> for the customer's own ids, and an official MCP server for AI assistants.</li></ul>"""
    defs = """<table class="small"><tr><th>Term</th><th>Fingerprint's definition (paraphrased, docs)</th><th>Used here</th></tr>
<tr><td>Deterministic / probabilistic</td><td>unique, reliable properties such as a cookie / non-deterministic properties such as screen resolution or time zone, combined</td><td>method of each simulated answer</td></tr>
<tr><td>Control / test</td><td>control = deterministically identified events; test = the same events with the deterministic properties removed, re-identified</td><td>real replay (cookie = control) and simulated measurement</td></tr>
<tr><td>True positive</td><td>same visitor ID in control and test</td><td>TP</td></tr>
<tr><td>False positive</td><td>"incorrectly identified as another <b>existing</b> browser"</td><td>FP = merge</td></tr>
<tr><td>False negative</td><td>incorrectly identified as a new browser</td><td>FN = split</td></tr>
<tr><td>Confidence score</td><td>1 - probability of a false positive; 1.0 for a new visitor or a deterministic match; says nothing about false negatives; example: ask for an OTP under 0.95</td><td>calibration (pages 4, 6)</td></tr></table>"""
    role = """<table class="small"><tr><th>Mission in the job post</th><th>Where in this study</th></tr>
<tr><td>First point of contact for reported FP / FN: root cause, actionable explanation</td><td>pages 6-9, playbooks, customer explainers</td></tr>
<tr><td>Analyses for strategic customers and prospects, custom metrics from account ids</td><td>page 7 (C07 linkedId, P01 POC)</td></tr>
<tr><td>Dashboards: per-customer health reports, weekly book-of-business</td><td>page 10, dashboard, tools/</td></tr>
<tr><td>Self-service and AI-assisted tools, adoption</td><td>page 10 (CLI, MCP server, adoption plan)</td></tr>
<tr><td>dbt on ClickHouse: aggregates, incremental models, tests</td><td>pages 8, 10; dbt/, clickhouse/ddl</td></tr>
<tr><td>Monitoring, anomaly detection, time series</td><td>page 6</td></tr>
<tr><td>Reconcile numbers with a customer's analysis; prioritise a request queue</td><td>pages 8, 10</td></tr>
<tr><td>Document findings and investigation procedures; shared on-call</td><td>page 10, docs/playbooks, on-call runbook</td></tr></table>"""
    body = f"""<div class="grid2">{card('<h2>Fingerprint, as stated by Fingerprint</h2>' + facts, tag='PUBLIC DATA')}{card('<h2>The definitions this study uses everywhere</h2>' + defs, tag='PUBLIC DATA')}</div>
<div class="grid-2-1">{card('<h2>The role, mapped to this study</h2>' + role, tag='PUBLIC DATA')}{img(ch['oss'], 'PUBLIC DATA', 'GitHub API, fingerprintjs/fingerprintjs releases (read 23 Nov 2026).')}</div>"""
    return page(1, "Fingerprint measures accuracy with a control / test experiment: this study reuses its exact definitions",
                "Facts are quoted as stated by Fingerprint (job post, careers API, GitHub, public docs), with dates. No internal data, no claim on Fingerprint's real accuracy.",
                ["PUBLIC DATA"], body, f"Sources: job post and careers API (Greenhouse, 23 Nov 2026), {DOC}, GitHub API")


def p2(f, ch):
    r = f["real"]
    p, rp, b = r["profile"], r["replay"], r["bots"]
    txt = f"""<ul>
<li><b>Replay</b>: on each of the 30 largest sites ({pct(p['top30_share_of_rows'])} of the rows), the cookie (<code>UserID</code>) is the control answer; the test answer is the user
of the last earlier event with the same 16-attribute fingerprint. Window functions in ClickHouse: about {rp['seconds_event_query']:.0f} s wall-clock for {rp['events_top30'] / 1e6:.0f}M events.</li>
<li><b>Grain</b>: per event, repeated page views of the same user are easy matches: TP {pct(rp['event']['tp'])}. Per visit (first event after 30 min,
{rp['events_per_visit']} events per visit) TP falls to {pct(rp['visit']['tp'])} and FP rises to {pct(rp['visit']['fp'])}. <b>An identification request is closer to a visit than to a page view.</b></li>
<li><b>Sites differ hugely</b>: event-grain FP from {pct(rp['site_fp_event_min'])} to {pct(rp['site_fp_event_max'])}; a platform average hides that.</li>
<li><b>Robots</b>: {pct(b['visit_share_bots'])} of visits; removing them before the replay changes human FP from {pct(b['humans_in_all_traffic']['fp'], 1)} to {pct(b['humans_bots_removed_before_replay']['fp'], 1)}.</li>
<li><b>Coverage trap</b>: {p['days_present']} days only, from {n0(p['users_day_min'])} to {n0(p['users_day_max'])} users a day: rates only, never raw daily counts.</li>
<li>Exact match on 16 obfuscated 2013 attributes is far weaker than any modern product: this page is about the <b>measurement</b>, not a level of accuracy.</li></ul>"""
    body = f"""<div class="grid3">{img(ch['grain'], 'PUBLIC DATA')}{img(ch['sites'], 'PUBLIC DATA')}{card('<h2>What the replay shows</h2>' + txt, tag='PUBLIC DATA')}</div>
<div class="grid2">{img(ch['coverage'], 'PUBLIC DATA', 'Distinct users per day (bars) and robot share (line). Missing days in red.')}{img(ch['bots'], 'PUBLIC DATA')}</div>"""
    return page(2, f"Replaying the accuracy method on {rp['events_top30'] / 1e6:.0f}M real events: the grain alone moves FP from {pct(rp['event']['fp'])} to {pct(rp['visit']['fp'])}",
                f"ClickBench hits ({p['rows'] / 1e6:.0f}M rows, {n0(p['users_exact'])} users, {p['sites']:,} sites, July 2013), anonymised: only the equality of values is used.",
                ["PUBLIC DATA"], body, "Sources: ClickBench hits on play.clickhouse.com (CC BY-NC-SA 4.0), clickhouse/analyses 01, 04, 05, 07")


def p3(f, ch):
    r = f["real"]
    a, t, c, k = r["anonymity"], {x["variant"]: x for x in r["tolerant"]}, r["calibration"], r["cookie_churn"]
    txt = f"""<ul>
<li><b>Entropy</b>: the 16-attribute fingerprint carries {r['entropy_fingerprint16_bits']} bits for {n0(r['entropy_users'])} users ({r['entropy_max_bits_users']} bits would single everyone out).
On 15 July, {pct(a['share_users_alone_in_fp'])} of users are alone in their fingerprint; the largest crowd holds {n0(a['largest_set'])} users.</li>
<li><b>Trade-off</b>: from the strictest (18 attributes, incl. window width) to the loosest variant (5), FP goes {pct(t[0]['fp'])} → {pct(t[4]['fp'])}
and FN {pct(t[0]['fn'], 1)} → {pct(t[4]['fn'], 1)}. Dropping minor versions (tolerant 14) halves FN vs the reference: fewer splits after small updates, more merges.</li>
<li><b>Calibration</b>: a score = 1 - FP share by crowd size, learnt on each site's first days, holds on later days (expected calibration error {c['ece_test']:.3f}, {c['sites_used']} sites).</li>
<li><b>The cookie is not a perfect truth</b>: at most {pct(k['share_nonoverlap_upper_bound'])} of measured FPs link two cookies that never overlap (possibly one device with a cleared cookie),
but only {pct(k['share_gap_over_1_day'], 1)} with more than a day between them: the bound is loose, the measured FP is an upper estimate.</li>
<li>Users show a median of {a['fps_per_user_p50']:.0f}, a 90th percentile of {a['fps_per_user_p90']:.0f} fingerprints in the month; {pct(a['share_users_multi_fp'])} have more than one.</li></ul>"""
    body = f"""<div class="grid3">{img(ch['tradeoff'], 'PUBLIC DATA', 'Visit grain, 30 largest sites, 5 fingerprint variants.')}{img(ch['anonymity'], 'PUBLIC DATA')}{img(ch['calib'], 'PUBLIC DATA', 'Bubble size = matched visits.')}</div>
<div class="grid-2-1">{card('<h2>What it means</h2>' + txt, tag='PUBLIC DATA')}{img(ch['entropy'], 'PUBLIC DATA')}</div>"""
    return page(3, "Strict or tolerant: every fingerprint trades merges for splits, and a simple score can stay calibrated out of sample",
                "Illustrative fingerprint on real anonymised data; the variants show the mechanics an accuracy analyst explains, not Fingerprint's algorithm.",
                ["PUBLIC DATA"], body, "Sources: ClickBench hits on play.clickhouse.com (CC BY-NC-SA 4.0), clickhouse/analyses 02, 03, 06, 08, 09")


def p4(f, ch):
    pu, v = f["public"], f["real"]["version_rollout"]
    ad = pu["adoption"]
    txt = f"""<ul>
<li><b>Real calendars</b> place the simulated drifts: Chrome 155 on {[x for x in pu['releases_in_window'] if x['browser'] == 'Chrome' and x['major'] == '155'][0]['release_date']},
iOS 27 on {[x for x in pu['releases_in_window'] if x['browser'] == 'iOS'][0]['release_date']} ({len(pu['releases_in_window'])} major releases fall inside the 13 weeks).</li>
<li><b>Adoption is slow, then sudden</b> (Wikimedia, median of {ad['Chrome']['versions']} Chrome releases): {pct(ad['Chrome']['uptake_week1'], 1)} of Chrome views on the new version after a week,
{pct(ad['Chrome']['uptake_week2'], 1)} after two, {pct(ad['Chrome']['uptake_week4'])} after four. Firefox: {pct(ad['Firefox']['uptake_week1'])} after a week. Mobile Safari: {pct(ad['Mobile Safari']['uptake_week4'])} after four weeks.
So a drift on a new version starts tiny: a per-customer series cannot see it in time, a platform series per version can.</li>
<li><b>In the real 2013 data</b>, {pct(v['share_changed_major'])} of the main browser's returning users changed major version in July; even ignoring version attributes,
{pct(v['multi_fp_no_version_changed'])} of them showed several fingerprints against {pct(v['multi_fp_no_version_stable'])} of the others: updates destabilise identification.</li>
<li><b>Counting devices without fingerprinting</b> (Wikimedia unique devices): a last-access cookie plus an offset correction worth {pct(pu['unique_devices']['offset_share_median'])} of the count (median day).
The same detector as page 6 flags {len(pu['unique_devices']['alert_days'])} days on this real series; the one-day spike of August 2025 is not flagged, because an alert needs two consecutive days. No cause is claimed.</li></ul>"""
    body = f"""<div class="grid3">{img(ch['releases'], 'PUBLIC DATA', 'Chromium Dash, Mozilla product-details, endoflife.date.')}{img(ch['uptake'], 'PUBLIC DATA', 'Share of the family already on the version or newer.')}{img(ch['rollout'], 'PUBLIC DATA', 'Version values are obfuscated: only the change matters.')}</div>
<div class="grid-2-1">{card('<h2>Why browser releases matter to accuracy</h2>' + txt, tag='PUBLIC DATA')}{img(ch['udev'], 'PUBLIC DATA', 'en.wikipedia, daily unique devices, Analytics API.')}</div>"""
    return page(4, "Browsers move, accuracy drifts: a new version reaches few users for two weeks, then most of them",
                "Real release dates and real adoption curves calibrate the simulation; a real version change inside the 2013 data shows the effect on fingerprints.",
                ["PUBLIC DATA"], body, "Sources: Chromium Dash, Mozilla product-details, endoflife.date, Wikimedia published datasets and Analytics API, ClickBench (analysis 10)")


def p5(f, ch):
    s, m = f["sim"], f["monitoring"]
    e1, e2, st = s["e1"], s["e2"], s["stats"]
    txt = f"""<ul>
<li><b>Detector</b>: per series (customer or platform × browser × version), errors of today and yesterday pooled against a reference (28 days; a new version is compared with its family),
exact binomial tail on over-dispersion-adjusted counts (phi {m['phi']['platform_segment_fn']}-{m['phi']['platform_segment_fp']}), Benjamini-Hochberg at 1% over all series of the day.</li>
<li><b>Chrome 155</b>: FN {pct(e1['drift_155']['fn_rate'], 1)} vs {pct(e1['drift_154']['fn_rate'], 1)} on Chrome 154 (x{e1['ratio_drift_vs_154']}), but only {pct(e1['chrome_traffic_share_on_155_during_drift'], 1)} of Chrome traffic: alert after {m['event_1']['delay_days']} days, fixed before the roll-out.</li>
<li><b>iOS 27</b>: true FP {pct(e2['issue_ios27']['true_fp_rate'], 1)} while the score implied {pct(e2['issue_ios27']['implied_fp_rate'], 1)}: overconfident (ECE {st['calibration_ios27_before_fix']['ece']:.3f} vs {st['calibration_all_other_segments']['ece']:.4f} elsewhere).
Alert the day after release. C02 step-ups on iOS 27: {pct(e2['c02_step_up_share']['issue']['ios27'], 1)} vs {pct(e2['c02_step_up_share']['after']['ios27'], 1)} after the fix.</li>
<li><b>Back-test</b>: {m['segment_alerts']['alert_days_total']} alert-days, precision {pct(m['segment_alerts']['precision'])}; events 1, 2, 5, 6 all caught; {m['false_alerts_per_week_all_monitors']} false alerts per week across monitors: a sustainable on-call load.</li>
<li><b>Threshold</b> (C02, sim truth): at 0.95, {pct(st['threshold_tradeoff_c02'][3]['step_up_share'], 1)} of answers get a step-up and {pct(st['threshold_tradeoff_c02'][3]['fp_caught_share'])} of the merges are caught.</li></ul>"""
    body = f"""<div class="grid2">{img(ch['drift_chrome'], 'SIMULATED', 'Platform series, Chrome 155 (real release date).')}{img(ch['drift_ios'], 'SIMULATED', 'Platform series, iOS 27 Mobile Safari (real release date).')}</div>
<div class="grid-2-1">{card('<h2>Catching drift before customers do</h2>' + txt, tag='SIMULATED')}{img(ch['threshold'], 'SIMULATED')}</div>"""
    return page(5, f"Catching drift before customers do: both browser drifts alerted within {max(m['event_1']['delay_days'], m['event_2']['delay_days'])} days, at {m['false_alerts_per_week_all_monitors']} false alerts a week",
                "Simulated platform, measured the Fingerprint way (control / test). The hidden truth is only used to score the monitor.",
                ["SIMULATED"], body, "Sources: src/monitoring.py, dbt fct_accuracy_daily; release dates: Chromium Dash, endoflife.date")


def p6(f, ch):
    s = f["sim"]
    e3, e6, e7 = s["e3"], s["e6"], s["e7"]
    a = e3["accounts_per_visitor"]
    c07 = f"""<h2>C07: staff, not merges</h2><p><b>C07 (online bank)</b>: "one visitor ID groups hundreds of our accounts". The extreme visitors (max {n0(a['all']['max'])} accounts) are
<b>{e3['internal_rule']['flagged']} support-agent computers</b> on shared office networks: correct identification, not FP. Rule: 20+ accounts and a network shared by 5+ such visitors
(precision {pct(e3['internal_rule']['precision'])}, recall {pct(e3['internal_rule']['recall'])} against the simulated truth). Without them and robots: mean {a['excl_internal_and_bots']['mean']:.2f}, p99 {a['excl_internal_and_bots']['p99']:.0f}, max {a['excl_internal_and_bots']['max']} (families).
Their export and our pairs match exactly ({n0(e3['export_pairs'])} pairs). <b>Action</b>: tag internal traffic.</p>"""
    p01 = f"""<h2>P01: a robot wave</h2><p><b>P01 (POC)</b>: "visitors per account exploded". Bad robots: {pct(e6['bot_share_wave'])} of requests from {e6['wave'][0]} to {e6['wave'][1]} (usually {pct(e6['bot_share_outside'], 1)}).
Visitors per account {e6['visitors_per_account_wave_all']} with robots, {e6['visitors_per_account_wave_excl_bots']} without. With flagged robots removed FN is still {pct(e6['fn_humans_wave'], 1)} (other weeks {pct(e6['fn_humans_outside'], 1)}):
unflagged robots leak in; on truly human traffic {pct(e6['fn_true_humans_wave'], 1)} vs {pct(e6['fn_true_humans_outside'], 1)}. <b>Action</b>: report human accuracy and robot detection separately.</p>"""
    c09 = f"""<h2>C09: the blind spot</h2><p><b>C09 (gaming)</b>: "accuracy is worse since our campaign". Private browsing {pct(e7['incognito_share_before'])} → {pct(e7['incognito_share_after'])}.
True error (all traffic) {pct(e7['true_error_before'], 1)} → {pct(e7['true_error_after'], 1)}, stable within each segment; the measured error stays at {pct(e7['measured_error_before'], 1)} → {pct(e7['measured_error_after'], 1)} because the control set
excludes private browsing. Observable without truth: new-visitor share {pct(e7['new_visitor_share_before'], 1)} → {pct(e7['new_visitor_share_after'], 1)}. <b>Action</b>: accuracy by traffic type.</p>"""
    body = f"""<div class="grid3">{img(ch['c07'], 'SIMULATED')}{img(ch['p01'], 'SIMULATED')}{img(ch['c09'], 'SIMULATED')}</div>
<div class="grid3 auto">{card(c07, 'roomy', tag='SIMULATED')}{card(p01, 'roomy', tag='SIMULATED')}{card(c09, 'roomy', tag='SIMULATED')}</div>"""
    return page(6, "Three customer complaints, three different causes: staff traffic, a robot wave and private browsing, none of them a model failure",
                "Customer-specific metrics from account ids (linkedId), robot segmentation in a POC, and the blind spot of the control-set measurement.",
                ["SIMULATED"], body, "Sources: dbt mart_linked_id_metrics, int_internal_traffic, fct_accuracy_weekly_customer; playbooks linked_id_custom_metrics, poc_accuracy_analysis")


def p7(f, ch):
    s = f["sim"]
    e4, e5 = s["e4"], s["e5"]
    ic = e5["incremental_check"]
    txt = f"""<ul>
<li><b>C03 (subscription news)</b> sees {pct(e4['their_over_ours_pct'], 1, True)} more sessions than billed identifications in October. Bridge: {pct(e4['blocked_share'], 1)} of their sessions have no visitor id
(requests blocked by ad blockers: <b>no proxy integration</b>); a {pct(e4['residual_share'], 2)} residual of duplicates; a time-zone shift of {e4['tz_shift']:+,} events between New York and UTC days. Daily gaps look much larger
(mean {pct(e4['daily_gap_mean_abs'], 1)}) because day boundaries move events, and move again with the DST change on 1 Nov.</li>
<li><b>Pipeline</b>: {n0(e5['c05_duplicates'])} C05 rows re-sent on 27 Oct ({pct(e5['dup_share'])} of the day) and the 28 Oct partition loaded on {e5['late_loaded_at'][:10]}.
dbt caught both (source uniqueness: {n0(e5['dbt_warnings'].get('source_unique_sim_identification_events_event_id', 0))} duplicates; raw rows vs ingestion log) as warnings, while the error-level tests on deduplicated staging pass.</li>
<li><b>Incremental model, 3-day lookback</b>, replayed morning by morning: after the last run it equals a full rebuild on every day ({n0(ic['2026-10-28']['incremental_after_last_run'])} events on 28 Oct).
A naive append-only table never gets 28 Oct ({n0(ic['2026-10-28']['naive_pipeline'])}) and counts {n0(ic['2026-10-27']['naive_pipeline'] - ic['2026-10-27']['full_build'])} duplicates on 27 Oct.</li></ul>"""
    body = f"""<div class="grid2">{img(ch['bridge'], 'SIMULATED')}{img(ch['c03_daily'], 'SIMULATED')}</div>
<div class="grid-2-1">{card('<h2>Reconcile step by step, and let the pipeline defend itself</h2>' + txt, tag='SIMULATED')}{img(ch['incremental'], 'SIMULATED', 'Events per day after the last morning run (02 Nov).')}</div>"""
    return page(7, f"When their numbers and ours disagree: a bridge explains the {pct(e4['their_over_ours_pct'], 0, True)} gap, and dbt tests catch what would break our side",
                "Customer export vs platform data (blocked requests, time zones, duplicates), then the same discipline applied to our own pipeline.",
                ["SIMULATED"], body, "Sources: customer export C03 (simulated), dbt tests and fct_accuracy_daily (incremental), src/incremental_replay.py")


def p8(f, ch):
    s = f["sim"]
    e8, st = s["e8"], s["stats"]
    c4 = st["c04"]
    de = {(d["customer_id"], d["metric"]): d for d in st["design_effects"]}
    txt = f"""<ul>
<li><b>The alert</b>: the weekly platform FP rate jumps {pct(e8['crude_change'], 0, True)} ({pct(e8['crude_before'], 2)} → {pct(e8['crude_after'], 2)}) the week of 19 Oct; the global control chart signals every day after.</li>
<li><b>Model?</b> No platform segment alerts; none of the existing customers changes significantly week over week ({e8['customers_significant_at_1pct']} of {len(e8['customers_week_over_week'])} at 1%).</li>
<li><b>Mix!</b> C12, a mobile marketplace, goes live and makes {pct(e8['c12_share_of_control_week'])} of the control events of that week, mostly look-alike iPhones, the segment with the highest FP everywhere.
Its rate per segment matches the other customers' (overlapping intervals). At constant mix the rate moves {pct(e8['standardized_change'], 1, True)}; the stable cohort {pct(e8['stable_cohort_change'], 1, True)}. <b>No incident; fix the dashboard.</b></li>
<li><b>Honest intervals</b>: events of one visitor are correlated. Cluster bootstrap vs Wilson: x{de[('C07', 'FN')]['width_ratio']} wider for C07 FN ({de[('C07', 'FN')]['events_per_visitor']} events per visitor), x{de[('C04', 'FP')]['width_ratio']} for C04 FP over 4 weeks ({de[('C04', 'FP')]['events_per_visitor']}): it depends on repeat visits.</li>
<li><b>How long to wait</b>: C04 has {n0(c4['control_events_per_day'])} control events a day; to detect +0.2 points of FP from {pct(c4['fp_rate'], 2)} needs {n0(c4['required_n_per_period'])} events per period, about <b>{c4['required_days_per_period']} days</b> each.
With 4 weeks, the smallest detectable change is {pct(c4['mde_with_28_days'], 2)} points.</li></ul>"""
    body = f"""<div class="grid-2-1">{img(ch['mix'], 'SIMULATED')}{card('<h2>Model, mix or measurement?</h2>' + txt, tag='SIMULATED')}</div>
<div class="grid2">{img(ch['c12'], 'SIMULATED', 'FP rate per segment since 19 Oct, 95% Wilson intervals.')}{img(ch['boot'], 'SIMULATED', 'Ratio of interval widths; above 1 = the naive interval is too narrow.')}</div>"""
    return page(8, f"Model, mix or measurement? A {pct(e8['crude_change'], 0, True)} jump in false positives that is pure mix, and the statistics that prove it",
                "Direct standardization, a stable cohort, per-segment comparisons with intervals, cluster bootstrap and minimal detectable effects.",
                ["SIMULATED"], body, "Sources: dbt mart_mix_standardized, fct_accuracy_weekly_customer; src/metrics.py, src/monitoring.py")


def p9(f, ch):
    s, d = f["sim"], f["dbt"]
    q = s["queue"]
    tools = f"""<ul class="small">
<li><b>accuracy_cli.py</b>: "accuracy of C07 over 4 weeks by browser?", "is this change real?" (quasi-binomial test), definitions, health; plain-English answers.</li>
<li><b>health_report.py</b>: one printable page per customer for CS (C02, C07, C09, P01 generated), with analyst notes filled from the findings.</li>
<li><b>book_of_business.py</b>: weekly digest per CSM pod (Markdown + HTML), status changes, next steps, open requests. Drafts, never sent.</li>
<li><b>MCP server</b> (read-only): 5 whitelisted tools for any MCP-compatible AI assistant; validated parameters, no free SQL, aggregates only, call log. Tested with the SDK client, no LLM.</li>
<li><b>dbt</b>: {d['models']} models, {d['data_tests']} data tests, {d['unit_tests']} unit tests, {d['exposures']} exposures, incremental <code>{d['incremental_models'][0]}</code>; portability macros for ClickHouse; DDL with AggregatingMergeTree and materialized views checked with EXPLAIN AST.</li>
<li><b>On-call</b>: runbook with severities, first moves, who to wake (roles), incident template; Prefect flow for the whole pipeline.</li></ul>"""
    qt = f"""<p>{q['requests']} requests in 13 weeks (CS {q['by_team']['CS']}, SE {q['by_team']['SE']}, Product {q['by_team']['Product']}), prioritised by impact (simulated ARR at stake) × urgency.
<b>{pct(q['self_service_share'])}</b> were standard questions a tool answers ({pct(q['self_service_hours_share'])} of analyst hours): the adoption plan targets them first.
Resolution within target: P1 {pct(q['by_tier']['P1']['within_sla'])}, P2 {pct(q['by_tier']['P2']['within_sla'])}.</p>"""
    body = f"""<div class="grid3">{img(ch['health'], 'SIMULATED')}{img(ch['queue'], 'SIMULATED')}{card('<h2>Request queue</h2>' + qt, 'roomy', tag='SIMULATED')}</div>
<div class="grid2 auto">{card('<h2>Self-service tools and operating model</h2>' + tools, tag='SIMULATED')}{card(LINEAGE, tag='SIMULATED')}</div>"""
    return page(9, f"Turning repeat questions into tools: {pct(q['self_service_share'])} of requests could be self-served, health reports and an MCP server do it",
                "Same read-only query layer behind the CLI, the reports and the MCP server; dbt models documented end to end.",
                ["SIMULATED"], body, "Sources: tools/, dbt (docs in dbt-docs/), mart_request_queue, mart_customer_health")


LINEAGE = """<h2>dbt lineage (simplified)</h2><pre>
sources (sim Parquet, ClickBench Parquet, seeds from ClickHouse)
  └─ staging      stg_identification_events (dedup, as_of)  stg_device_truth  stg_customers
  │               stg_browser_releases (first stable)  stg_hits  stg_ingestion_log  stg_request_queue
  └─ intermediate int_events_measured (control / test)  int_events_truth (sim only)  int_version_age
  │               int_linked_id_pairs  int_internal_traffic  int_hits_reid (real replay)
  └─ marts        fct_accuracy_daily (incremental, 3-day lookback)  fct_accuracy_weekly_customer
                  mart_customer_health  mart_book_of_business  mart_linked_id_metrics  mart_request_queue
                  mart_anomaly_candidates  mart_mix_standardized  mart_hits_reid_check (DuckDB = ClickHouse)
  └─ exposures    dashboard · health reports · book of business · MCP server</pre>"""


def p10(f, ch):
    r, s = f["real"], f["sim"]
    src = f"""<ul class="small">
<li><b>ClickBench hits</b> (ClickHouse/ClickBench, CC BY-NC-SA 4.0): public playground play.clickhouse.com, read-only, {r['playground']['queries_sent']} of 150 allowed queries, aggregates only; 5 Parquet files for dbt. Published results are aggregates under the same licence.</li>
<li><b>Browser calendars</b>: Chromium Dash (Stable, Windows), Mozilla product-details, endoflife.date (iOS). <b>Wikimedia Foundation</b>: published browser datasets, Analytics API unique devices (CC0).</li>
<li><b>Fingerprint</b>: job post and careers list (Greenhouse API), {DOC}, identify-visitors and MCP-server docs, GitHub API. All read on 23 Nov 2026.</li>
<li><b>Simulation</b>: src/simulate_platform.py, seed 42; every assumption in docs/assumptions.md. Error rates are illustrative, never Fingerprint's.</li></ul>"""
    lim = f"""<ul class="small">
<li>Real data is from 2013, obfuscated, from a web-analytics service, with {r['profile']['days_present']} of 31 days; the 16-attribute exact match is a teaching device, not Fingerprint's algorithm. The cookie used as truth can be cleared (bounded on page 4).</li>
<li>No local ClickHouse (no Docker or WSL): ClickHouse SQL ran on the public playground; dbt runs on DuckDB with portability macros; DDL syntax checked, not executed.</li>
<li>Superset: specification and virtual datasets (bi/superset), see the README for the installation attempt. The HTML dashboard covers the same views.</li>
<li>The simulated platform, its customers, ARR and requests are fictional; the hidden truth exists only in a simulation.</li>
<li><b>Privacy</b>: device identification is personal data under the GDPR (legal basis, fraud-prevention purpose, minimisation). No visitor-level real row, no IP (even hashed) and no browser-signal collection code are published; nothing here explains how to evade identification or robot detection.</li></ul>"""
    meth = f"""<ul class="small">
<li>Definitions: Fingerprint's control / test experiment (page 2). Grains: event, visit (30-minute gap), user-day.</li>
<li>Statistics: Wilson intervals, cluster bootstrap by visitor, quasi-binomial tests (phi), minimal detectable effect, direct standardization, Benjamini-Hochberg, Laney p'-chart, CUSUM, calibration (ECE).</li>
<li>Checks: DuckDB = ClickHouse on {r['reconciliation']['sites']} sites (difference {r['reconciliation']['total_abs_diff']}); dbt build green with 2 expected warnings; pytest green; the whole pipeline re-run from scratch before publication.</li>
<li>{AI_NOTE}</li></ul>"""
    body = f"""<div class="grid3">{card('<h2>Sources and licences</h2>' + src.replace('class="small"', ''), 'roomy')}{card('<h2>Methods</h2>' + meth.replace('class="small"', ''), 'roomy')}{card('<h2>Limits</h2>' + lim.replace('class="small"', ''), 'roomy')}</div>"""
    return page(10, "Methods, limits and sources", "How to rerun everything: README. Every number in this report is read from data/processed/findings.json.",
                ["PUBLIC DATA", "SIMULATED"], body, "Repository: README, METRICS.md, docs/")


CSS = """
@page { size: 1600px 900px; margin: 0; }
* { box-sizing: border-box; }
body { margin: 0; font-family: 'Segoe UI', Arial, sans-serif; color: #0B0B0B; background: #F4F4F2; }
.page { width: 1600px; height: 900px; padding: 28px 40px 20px; display: flex; flex-direction: column; page-break-after: always; overflow: hidden; background: #F4F4F2; }
header { display: flex; justify-content: space-between; align-items: flex-start; gap: 30px; }
h1 { font-size: 25px; margin: 0 0 5px; font-weight: 700; line-height: 1.15; max-width: 1320px; }
.sub { margin: 0; color: #52514E; font-size: 14.5px; max-width: 1320px; }
.tags { display: flex; gap: 6px; }
.tag, .ctag { font-size: 12px; font-weight: 700; letter-spacing: .08em; padding: 5px 10px; border-radius: 4px; white-space: nowrap; color: #52514E; }
.ctag { position: absolute; top: 8px; right: 10px; font-size: 9.5px; padding: 2px 6px; z-index: 2; }
.tag-public, .ctag-public { background: #E3EEFB; color: #1C5CAB; } .tag-simulated, .ctag-simulated { background: #FBE9E0; color: #9A3B12; } .tag-overview { color: #52514E; background: #E9E8E3; }
main { flex: 1; display: flex; flex-direction: column; gap: 12px; margin-top: 12px; min-height: 0; }
footer { display: flex; justify-content: space-between; gap: 20px; font-size: 11px; color: #898781; margin-top: 8px; }
.card { position: relative; background: #FCFCFB; border: 1px solid #E1E0D9; border-radius: 8px; padding: 11px 15px; min-height: 0; overflow: hidden; }
.card h2 { font-size: 15.5px; margin: 0 0 5px; padding-right: 90px; }
.card p, .card li { font-size: 13px; line-height: 1.38; margin: 3px 0; color: #2B2A27; }
.card ul, .card ol { padding-left: 18px; margin: 3px 0; }
.fig { padding: 10px 12px 8px; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; flex: 1; min-height: 0; }
.grid3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; flex: 1; min-height: 0; }
.grid4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; flex: 0 0 auto; }
.grid-2-1 { display: grid; grid-template-columns: 1.5fr 1fr; gap: 12px; flex: 1; min-height: 0; }
figure { margin: 0; height: 100%; display: flex; flex-direction: column; }
figure img { width: 100%; flex: 1; min-height: 0; object-fit: contain; }
figcaption { font-size: 11px; color: #52514E; margin-top: 3px; }
.tile .label { font-size: 12px; font-weight: 700; color: #52514E; letter-spacing: .04em; padding-right: 80px; }
.tile .big { font-size: 34px; font-weight: 700; margin: 2px 0; color: #0B0B0B; }
.tile p { font-size: 12.5px; color: #52514E; }
.qs li { font-size: 14px !important; margin: 6px 0; } .reco li { font-size: 13.5px !important; margin: 5px 0; }
table { border-collapse: collapse; width: 100%; font-size: 12.5px; }
th { text-align: left; color: #52514E; font-weight: 600; border-bottom: 1px solid #E1E0D9; padding: 3px 6px; }
td { border-bottom: 1px solid #EFEEE9; padding: 3px 6px; vertical-align: top; }
table.small, .small, .small li, .small td, .small th { font-size: 12px !important; }
.facts li { font-size: 13px !important; margin: 5px 0; }
pre { background: #F4F4F2; border-radius: 6px; padding: 8px 10px; font-size: 11.5px; margin: 4px 0; line-height: 1.35; white-space: pre; }
code { font-size: 12px; background: #F0EFEC; padding: 0 3px; border-radius: 3px; }
.flow { display: flex; gap: 0; margin: 6px 0 10px; }
.step { flex: 1; background: #E3EEFB; color: #1C5CAB; font-weight: 600; font-size: 12px; text-align: center; padding: 9px 4px;
        clip-path: polygon(0 0, 88% 0, 100% 50%, 88% 100%, 0 100%, 12% 50%); margin-right: -6px; }
.step:first-child { clip-path: polygon(0 0, 88% 0, 100% 50%, 88% 100%, 0 100%); }
.auto { flex: 0 0 auto !important; }
.roomy p, .roomy li { font-size: 14.5px !important; line-height: 1.45; margin: 5px 0; }
.mmm { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }
.mmm div { background: #F4F4F2; border-radius: 6px; padding: 8px 10px; font-size: 12.5px; line-height: 1.35; }
"""


def build_html() -> Path:
    ch = charts.build_all()
    f = json.loads((PROC / "findings.json").read_text(encoding="utf-8"))
    pages = [p(f, ch) for p in [p0, p1, p2, p3, p4, p5, p6, p7, p8, p9, p10]]
    assert len(pages) == N_PAGES
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Identification accuracy case study</title><style>{CSS}</style></head><body>{''.join(pages)}</body></html>"""
    out = REP / "report.html"
    out.write_text(html, encoding="utf-8")
    return out


def find_browser() -> str:
    for c in [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe", shutil.which("msedge") or "", shutil.which("google-chrome") or ""]:
        if c and Path(c).exists():
            return c
    raise FileNotFoundError("Edge or Chrome is needed to print the PDF")


def print_pdf(html: Path) -> Path:
    pdf, tmp = REP / PDF_NAME, REP / "_print.pdf"
    profile = tempfile.mkdtemp()
    subprocess.run([find_browser(), "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--user-data-dir={profile}",
                    "--run-all-compositor-stages-before-draw", "--virtual-time-budget=5000",
                    f"--print-to-pdf={tmp}", html.as_uri()], check=True, timeout=180)
    last = -1
    for _ in range(120):
        time.sleep(1)
        size = tmp.stat().st_size if tmp.exists() else -1
        if size > 0 and size == last:
            break
        last = size
    shutil.rmtree(profile, ignore_errors=True)
    reader, writer = PdfReader(str(tmp)), PdfWriter()
    for pg in reader.pages:
        writer.add_page(pg)
    writer.add_metadata({"/Title": "Identification accuracy analytics - case study", "/Author": "", "/Creator": "", "/Producer": "", "/Subject": "", "/Keywords": ""})
    with open(pdf, "wb") as fh:
        writer.write(fh)
    tmp.unlink()
    return pdf


def main():
    html = build_html()
    pdf = print_pdf(html)
    print("written", pdf.relative_to(ROOT), len(PdfReader(str(pdf)).pages), "pages")


if __name__ == "__main__":
    main()
