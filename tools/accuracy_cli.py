"""Self-service command line for the most common accuracy questions (read-only, SIMULATED data).

Examples
    python tools/accuracy_cli.py customers
    python tools/accuracy_cli.py summary --customer C07 --start 2026-10-26 --end 2026-11-22 --by browser
    python tools/accuracy_cli.py change --customer C04 --metric fp --a 2026-09-28 2026-10-11 --b 2026-10-12 2026-10-25
    python tools/accuracy_cli.py explain false_negative
    python tools/accuracy_cli.py health --customer C02
Add --json for machine-readable output.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import accuracy_core as core  # noqa: E402


def fmt_rows(rows):
    lines = [f"{'group':<22}{'control ev.':>12}{'FP rate':>10}{'95% CI':>18}{'FN rate':>10}"]
    for r in rows:
        ci = f"{core.pct(r['fp_rate_ci95'][0])}-{core.pct(r['fp_rate_ci95'][1])}"
        lines.append(f"{r['group'][:21]:<22}{r['control_events']:>12,}{core.pct(r['fp_rate']):>10}{ci:>18}{core.pct(r['fn_rate']):>10}")
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description="Accuracy self-service CLI (SIMULATED data, read-only).")
    p.add_argument("--json", action="store_true", help="print JSON instead of text")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("customers")
    s = sub.add_parser("summary")
    s.add_argument("--customer", required=True)
    s.add_argument("--start", default="2026-10-26")
    s.add_argument("--end", default="2026-11-22")
    s.add_argument("--by", default="none", choices=sorted(core.GROUP_BY))
    c = sub.add_parser("change")
    c.add_argument("--customer", required=True)
    c.add_argument("--metric", choices=["fp", "fn"], default="fp")
    c.add_argument("--a", nargs=2, required=True, metavar=("START", "END"))
    c.add_argument("--b", nargs=2, required=True, metavar=("START", "END"))
    e = sub.add_parser("explain")
    e.add_argument("name")
    h = sub.add_parser("health")
    h.add_argument("--customer", required=True)
    args = p.parse_args(argv)
    try:
        if args.cmd == "customers":
            res = core.list_customers()
            text = "\n".join(f"{r['customer_id']}  {r['sector']:<24}{r['use_case']:<24}{r['csm_pod']}  threshold {r['confidence_threshold']}" for r in res)
        elif args.cmd == "summary":
            res = core.accuracy_summary(args.customer, args.start, args.end, args.by)
            text = f"[{res['label']}]\n{res['summary']}\n\n{fmt_rows(res['rows'])}"
        elif args.cmd == "change":
            res = core.is_change_significant(args.customer, args.metric, *args.a, *args.b)
            text = f"[{res['label']}]\n{res['summary']}"
        elif args.cmd == "explain":
            res = core.explain_metric(args.name)
            text = f"{res['metric']}: {res['definition']}"
        else:
            res = core.customer_health(args.customer)
            text = f"[{res['label']}]\n{res['summary']}\n" + "\n".join(
                f"  {w['week_start']}  {w['status']:<6} FP {core.pct(w['fp_rate'])}  FN {core.pct(w['fn_rate'])}  {w['reasons']}" for w in res["last_4_weeks"])
    except core.ToolError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    print(json.dumps(res, indent=2, default=str) if args.json else text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
