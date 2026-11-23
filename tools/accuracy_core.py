"""Shared, READ-ONLY query layer of the self-service tools (CLI, health report, book of business, MCP server).

Guard-rails (the same for every tool, so the MCP server cannot do more than the CLI):
- the DuckDB file is opened read_only=True;
- only the whitelisted, parameterised queries below exist: no free SQL, ever;
- every parameter is validated (customer id pattern and existence, ISO dates inside the data window, whitelists
  for metrics and group-by columns);
- outputs are aggregates only: no event-level row, no visitor id, no account id, no network hash;
- results are capped at MAX_ROWS rows;
- every call is appended to tools/logs/calls.jsonl (tool, parameters, row count, time).

All data behind these tools is SIMULATED (fictional platform and customers).
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import metrics  # noqa: E402

DB = ROOT / "dbt" / "fingerprint.duckdb"
LOG = ROOT / "tools" / "logs" / "calls.jsonl"
MAX_ROWS = 200
WINDOW = (dt.date(2026, 8, 24), dt.date(2026, 11, 22))
CUSTOMER_RE = re.compile(r"^(C(0[1-9]|1[0-2])|P0[12])$")
GROUP_BY = {"none": None, "browser": "browser", "device_type": "device_type", "browser_version": "browser || ' ' || browser_major",
            "week": "cast(date_trunc('week', event_date) as date)"}
METRICS_ALLOWED = {"fp": "fp", "fn": "fn"}
LABEL = "SIMULATED data (fictional platform and customers)"


class ToolError(ValueError):
    """Raised for invalid parameters; the message is safe to show to the user."""


def _con():
    return duckdb.connect(str(DB), read_only=True)


def _log(tool: str, params: dict, rows: int):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "tool": tool,
                            "params": params, "rows": rows}) + "\n")


def _phi() -> float:
    """Over-dispersion factor estimated by src/monitoring.py (customer-level FP series); 2.0 if not available."""
    p = ROOT / "data" / "processed" / "monitoring_backtest.json"
    try:
        return float(json.loads(p.read_text())["phi"]["customer_segment_fp"])
    except (OSError, KeyError, ValueError):
        return 2.0


# ---------------------------------------------------------------- validation
def check_customer(customer_id: str) -> str:
    cid = str(customer_id).strip().upper()
    if not CUSTOMER_RE.match(cid):
        raise ToolError(f"Unknown customer id '{customer_id}'. Expected C01..C12, P01 or P02.")
    with _con() as con:
        if not con.execute("select count(*) from stg_customers where customer_id = ?", [cid]).fetchone()[0]:
            raise ToolError(f"Customer {cid} does not exist.")
    return cid


def check_date(value: str, name: str) -> dt.date:
    try:
        d = dt.date.fromisoformat(str(value))
    except ValueError:
        raise ToolError(f"{name} must be an ISO date (YYYY-MM-DD), got '{value}'.") from None
    if not WINDOW[0] <= d <= WINDOW[1]:
        raise ToolError(f"{name} must be between {WINDOW[0]} and {WINDOW[1]}.")
    return d


def check_period(start: str, end: str, label: str = "period") -> tuple[dt.date, dt.date]:
    s, e = check_date(start, f"{label} start"), check_date(end, f"{label} end")
    if s > e:
        raise ToolError(f"{label}: start must be before end.")
    return s, e


def pct(x, digits=2):
    return "n/a" if x is None else f"{100 * x:.{digits}f}%"


# ---------------------------------------------------------------- tools
def list_customers() -> list[dict]:
    with _con() as con:
        rows = con.execute("""select customer_id, sector, use_case, plan, region, csm_pod, cast(start_date as varchar) as start_date,
                                     confidence_threshold, is_prospect
                              from stg_customers order by customer_id""").fetchall()
        cols = ["customer_id", "sector", "use_case", "plan", "region", "csm_pod", "start_date", "confidence_threshold", "is_prospect"]
    out = [dict(zip(cols, r)) for r in rows]
    _log("list_customers", {}, len(out))
    return out


def accuracy_summary(customer_id: str, start: str, end: str, group_by: str = "none") -> dict:
    """Measured FP and FN rates (control set, bad robots excluded) with 95% Wilson intervals, optionally grouped."""
    cid = check_customer(customer_id)
    s, e = check_period(start, end)
    if group_by not in GROUP_BY:
        raise ToolError(f"group_by must be one of {sorted(GROUP_BY)}.")
    g = GROUP_BY[group_by]
    sel = f"{g} as grp," if g else "'all' as grp,"
    sql = f"""select {sel} sum(control_events) as n, sum(fp) as fp, sum(fn) as fn, sum(events) as events,
                     sum(incognito_events) as incognito, sum(human_events) as human, sum(bad_bot_events) as bad_bots
              from fct_accuracy_daily
              where customer_id = ? and event_date between ? and ?
              group by 1 order by n desc limit {MAX_ROWS}"""
    with _con() as con:
        rows = con.execute(sql, [cid, s, e]).fetchall()
    out = []
    for grp, n, fp, fn, events, inc, human, bots in rows:
        fp_lo, fp_hi = metrics.wilson(fp, n)
        fn_lo, fn_hi = metrics.wilson(fn, n)
        out.append({"group": str(grp), "control_events": int(n), "fp_rate": fp / n if n else None, "fp_rate_ci95": [fp_lo, fp_hi],
                    "fn_rate": fn / n if n else None, "fn_rate_ci95": [fn_lo, fn_hi], "events": int(events),
                    "incognito_share": inc / human if human else None, "bad_bot_share": bots / events if events else None})
    total = out[0] if group_by == "none" and out else None
    sentence = (f"{cid}, {s} to {e}: measured false-positive rate {pct(total['fp_rate'])} (95% CI {pct(total['fp_rate_ci95'][0])}-"
                f"{pct(total['fp_rate_ci95'][1])}), false-negative rate {pct(total['fn_rate'])}, on {total['control_events']:,} control events."
                if total else f"{cid}, {s} to {e}: {len(out)} groups by {group_by}, largest first.")
    _log("accuracy_summary", {"customer_id": cid, "start": str(s), "end": str(e), "group_by": group_by}, len(out))
    return {"label": LABEL, "customer_id": cid, "start": str(s), "end": str(e), "group_by": group_by, "rows": out,
            "summary": sentence, "definition": "Rates on the control set (deterministic events re-identified without the deterministic signal); bad robots excluded."}


def is_change_significant(customer_id: str, metric: str, period_a_start: str, period_a_end: str,
                          period_b_start: str, period_b_end: str) -> dict:
    """Compare a rate between two periods with a quasi-binomial two-proportion test (over-dispersion phi)."""
    cid = check_customer(customer_id)
    if metric not in METRICS_ALLOWED:
        raise ToolError("metric must be 'fp' or 'fn'.")
    a = check_period(period_a_start, period_a_end, "period A")
    b = check_period(period_b_start, period_b_end, "period B")
    col = METRICS_ALLOWED[metric]
    sql = f"select sum(control_events), sum({col}) from fct_accuracy_daily where customer_id = ? and event_date between ? and ?"
    with _con() as con:
        na, ka = con.execute(sql, [cid, *a]).fetchone()
        nb, kb = con.execute(sql, [cid, *b]).fetchone()
    if not na or not nb:
        raise ToolError("One of the periods has no control events for this customer.")
    phi = _phi()
    t = metrics.two_proportion_test(ka, na, kb, nb, phi=phi)
    name = "false-positive" if metric == "fp" else "false-negative"
    real = t["p_value"] < 0.01
    verdict = "a real change" if real else "within normal noise"
    sentence = (f"{cid}: the {name} rate went from {pct(t['rate_a'])} to {pct(t['rate_b'])} "
                f"({t['relative_change']:+.0%}). With {na:,} and {nb:,} control events and the usual day-to-day noise "
                f"(over-dispersion {phi:.1f}), this is {verdict} (p = {t['p_value']:.3g}).")
    if real:
        sentence += " Next step: check whether one browser version or one traffic segment explains it before calling it a model change."
    _log("is_change_significant", {"customer_id": cid, "metric": metric, "a": [str(x) for x in a], "b": [str(x) for x in b]}, 1)
    return {"label": LABEL, "customer_id": cid, "metric": metric, "period_a": [str(x) for x in a], "period_b": [str(x) for x in b],
            "n_a": int(na), "n_b": int(nb), "phi": phi, **{k: float(v) for k, v in t.items()}, "significant_at_1pct": bool(real),
            "summary": sentence}


DEFINITIONS = {
    "true_positive": "The visitor is recognised as the right existing visitor. Measured on the control set: the answer without the deterministic signal is the same visitor as the deterministic answer.",
    "false_positive": "The visitor is wrongly recognised as ANOTHER existing visitor (two people merged). Fingerprint's definition; the confidence score is 1 minus the estimated probability of this error.",
    "false_negative": "A returning visitor is wrongly treated as NEW (one person split in two). The confidence score says nothing about this error.",
    "control_set": "Events identified deterministically. The accuracy experiment re-identifies them without the deterministic signal and compares both answers. Incognito traffic never enters it, so the measured accuracy is optimistic when incognito traffic grows.",
    "confidence_score": "1 minus the estimated probability of a false positive (1.0 for a new visitor). A calibrated score means: among answers with score 0.97, about 3% are false positives.",
    "accounts_per_visitor": "Customer-specific metric from the customer's own account ids (linkedId): distinct accounts seen with one visitor id. High values can be shared family devices, support agents or false positives: exclude internal traffic before concluding.",
    "visitors_per_account": "Distinct visitor ids seen with one account. High values can be several devices per person, false negatives, incognito or robots.",
    "health_status": "green / amber / red / grey per customer and week: FP or FN rate up against the previous 4 weeks (z > 2 amber, > 3 red), bad-robot share, incognito share change, open high or critical requests; grey = less than 2 weeks of history.",
    "mix_standardized_rate": "Platform rate recomputed at a fixed traffic mix (browser x device type). A new mobile-heavy customer moves the crude rate but not this one; only a real change inside segments moves it.",
}


def explain_metric(name: str) -> dict:
    key = str(name).strip().lower().replace(" ", "_").replace("-", "_")
    if key not in DEFINITIONS:
        raise ToolError(f"Unknown metric '{name}'. Known: {', '.join(sorted(DEFINITIONS))}.")
    _log("explain_metric", {"name": key}, 1)
    return {"metric": key, "definition": DEFINITIONS[key], "source": "METRICS.md"}


def customer_health(customer_id: str) -> dict:
    cid = check_customer(customer_id)
    with _con() as con:
        rows = con.execute("""select cast(week_start as varchar), health_status, health_reasons, fp_rate, fp_rate_lo, fp_rate_hi, fn_rate,
                                     control_events, open_requests
                              from mart_customer_health where customer_id = ? order by week_start desc limit 4""", [cid]).fetchall()
    if not rows:
        raise ToolError(f"No health history for {cid}.")
    hist = [{"week_start": r[0], "status": r[1], "reasons": r[2] or "", "fp_rate": r[3], "fp_rate_ci95": [r[4], r[5]],
             "fn_rate": r[6], "control_events": int(r[7]), "open_requests": int(r[8])} for r in rows]
    cur = hist[0]
    sentence = (f"{cid} is {cur['status'].upper()} for the week of {cur['week_start']}"
                + (f": {cur['reasons']}." if cur["reasons"] else ": no accuracy change, robot or incognito alert, no urgent request."))
    _log("customer_health", {"customer_id": cid}, len(hist))
    return {"label": LABEL, "customer_id": cid, "current": cur, "last_4_weeks": hist, "summary": sentence}
