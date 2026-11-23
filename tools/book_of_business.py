"""Weekly BOOK-OF-BUSINESS digest per CSM pod (SIMULATED data), ready to paste, NEVER sent automatically.

    python tools/book_of_business.py --week 2026-11-16      # -> report/book_of_business/<week>_<pod>.md and .html
"""
import argparse
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
import accuracy_core as core  # noqa: E402
from report_style import CSS, FOOTER, esc  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report" / "book_of_business"


def action_for(row) -> str:
    """One plain-English next step per customer, from the health reasons (rules in docs/playbooks)."""
    r = (row.health_reasons or "").lower()
    if "bad robots" in r:
        return "Segment robots out of the accuracy readout and share the robot report (playbook: POC accuracy analysis)."
    if "incognito" in r:
        return "Explain the private-browsing mix change; measured accuracy is optimistic on this traffic (customer explainer)."
    if "fp rate up" in r:
        return "Open a false-positive investigation by browser version and segment (playbook: false positives)."
    if "fn rate up" in r:
        return "Open a false-negative investigation by browser version (playbook: false negatives)."
    if "open critical" in r or "open high" in r:
        return "Follow up the open request with the analyst before the next customer call."
    if row.health_status == "grey":
        return "New customer: confirm the integration (proxy, linkedId, threshold) and set the baseline."
    return "No action needed."


def build(week: str):
    con = duckdb.connect(str(core.DB), read_only=True)
    h = con.execute("select * from mart_customer_health where cast(week_start as varchar) = ? order by csm_pod, customer_id", [week]).df()
    if h.empty:
        raise SystemExit(f"No data for week {week}.")
    prev = con.execute("select customer_id, fp_rate as prev_fp, health_status as prev_status from mart_customer_health "
                       "where week_start = cast(? as date) - interval 7 day", [week]).df()
    bob = con.execute("select * from mart_book_of_business where cast(week_start as varchar) = ?", [week]).df().set_index("csm_pod")
    q = con.execute("""select csm_pod, request_id, customer_id, title, priority_tier, cast(opened_at as date) as opened
                       from mart_request_queue r join stg_customers c using (customer_id)
                       where is_open or resolved_at >= cast(? as date) + interval 7 day
                       order by priority_score desc""", [week]).df()
    con.close()
    h = h.merge(prev, on="customer_id", how="left")
    OUT.mkdir(parents=True, exist_ok=True)
    written = []
    for pod, g in h.groupby("csm_pod"):
        b = bob.loc[pod]
        lines = [f"# Accuracy book of business · {pod} · week of {week}", "",
                 "_SIMULATED data (fictional customers). Draft for the pod channel, not sent automatically._", "",
                 f"**{int(b.customers)} customers** ({int(b.prospects)} prospects) · simulated ARR ${b.arr_usd_simulated / 1e6:.2f}M · "
                 f"red {int(b.red)} · amber {int(b.amber)} · green {int(b.green)} · grey {int(b.grey)} · "
                 f"ARR at risk (red + amber) ${b.arr_at_risk_usd_simulated / 1e3:,.0f}k", ""]
        if b.status_changes:
            lines += [f"**Status changes since last week:** {b.status_changes}", ""]
        lines += ["| Customer | Sector | Status | FP rate | vs last week | Why | Next step |", "|---|---|---|---|---|---|---|"]
        for r in g.itertuples():
            delta = "" if r.prev_fp is None or r.prev_fp != r.prev_fp else f"{100 * (r.fp_rate - r.prev_fp):+.2f} pts"
            lines.append(f"| {r.customer_id} | {r.sector} | {r.health_status} | {core.pct(r.fp_rate)} | {delta} | {r.health_reasons or '-'} | {action_for(r)} |")
        qq = q[q["csm_pod"] == pod].head(6)
        lines += ["", "**Open requests (highest priority first)**", ""]
        lines += [f"- {x.request_id} · {x.customer_id} · {x.priority_tier} · {x.title} (opened {x.opened})" for x in qq.itertuples()] or ["- none"]
        lines += ["", f"_{FOOTER}_"]
        md = "\n".join(lines)
        base = OUT / f"{week}_{pod}"
        base.with_suffix(".md").write_text(md, encoding="utf-8")
        rows = "".join(f"<tr><td>{esc(r.customer_id)}</td><td>{esc(r.sector)}</td><td><span class='badge {r.health_status}'>{r.health_status}</span></td>"
                       f"<td class='n'>{core.pct(r.fp_rate)}</td><td>{esc(r.health_reasons or '-')}</td><td>{esc(action_for(r))}</td></tr>" for r in g.itertuples())
        reqs = "".join(f"<li>{esc(x.request_id)} · {esc(x.customer_id)} · {esc(x.priority_tier)} · {esc(x.title)}</li>" for x in qq.itertuples()) or "<li>none</li>"
        html_doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Book of business {pod}</title><style>{CSS}</style></head><body><div class="page">
<h1>Accuracy book of business · {pod} <span class="tag">SIMULATED</span></h1><div class="sub">Week of {week} · draft, not sent automatically</div>
<div class="card">{int(b.customers)} customers · simulated ARR ${b.arr_usd_simulated / 1e6:.2f}M · red {int(b.red)} · amber {int(b.amber)} · green {int(b.green)} · grey {int(b.grey)}
{'<br><b>Status changes:</b> ' + esc(b.status_changes) if b.status_changes else ''}</div>
<div class="card"><table><tr><th>Customer</th><th>Sector</th><th>Status</th><th class='n'>FP rate</th><th>Why</th><th>Next step</th></tr>{rows}</table></div>
<div class="card"><h2>Open requests</h2><ul>{reqs}</ul></div><div class="foot">{FOOTER}</div></div></body></html>"""
        base.with_suffix(".html").write_text(html_doc, encoding="utf-8")
        written.append(base)
    return written


def main(argv=None):
    p = argparse.ArgumentParser(description="Weekly book-of-business digest per CSM pod (SIMULATED data).")
    p.add_argument("--week", default="2026-11-16", help="Monday of the week (YYYY-MM-DD)")
    a = p.parse_args(argv)
    for b in build(a.week):
        print("written", b.relative_to(ROOT).with_suffix(".md"), "and .html")


if __name__ == "__main__":
    main()
