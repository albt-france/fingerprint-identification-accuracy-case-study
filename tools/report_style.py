"""Shared HTML style and a tiny dependency-free SVG line chart for the printable reports."""
import html

FOOTER = "Independent case study based on public data · not affiliated with or endorsed by Fingerprint"

CSS = """
:root { --bg:#f4f1ec; --card:#ffffff; --ink:#1f2328; --muted:#5f6670; --line:#e3ded6; --accent:#2f5d8a;
        --green:#2e7d4f; --amber:#b7791f; --red:#b83232; --grey:#7a7f87; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink); font:13px/1.45 "Segoe UI", system-ui, sans-serif; }
.page { max-width:980px; margin:0 auto; padding:22px 26px; }
h1 { font-size:21px; margin:0 0 2px; } h2 { font-size:14px; margin:0 0 8px; }
.sub { color:var(--muted); margin-bottom:14px; }
.tag { display:inline-block; font-size:10px; font-weight:700; letter-spacing:.06em; padding:2px 7px; border-radius:3px;
       background:#e8e1f5; color:#4b3a78; vertical-align:middle; margin-left:6px; }
.grid { display:grid; grid-template-columns:repeat(4, 1fr); gap:10px; margin-bottom:12px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:12px 14px; margin-bottom:12px; }
.kpi .v { font-size:20px; font-weight:700; } .kpi .l { color:var(--muted); font-size:11px; }
.badge { display:inline-block; padding:4px 12px; border-radius:14px; color:#fff; font-weight:700; text-transform:uppercase; font-size:12px; }
.green { background:var(--green); } .amber { background:var(--amber); } .red { background:var(--red); } .grey { background:var(--grey); }
table { border-collapse:collapse; width:100%; font-size:12px; }
th, td { text-align:left; padding:4px 6px; border-bottom:1px solid var(--line); } th { color:var(--muted); font-weight:600; }
td.n, th.n { text-align:right; }
.foot { color:var(--muted); font-size:10.5px; margin-top:10px; }
.two { display:grid; grid-template-columns:1.25fr 1fr; gap:12px; }
@media print { body { background:#fff; } .page { padding:0; } .card { break-inside:avoid; } }
@media (max-width:700px) { .grid { grid-template-columns:1fr 1fr; } .two { grid-template-columns:1fr; } }
"""


def esc(x) -> str:
    return html.escape(str(x))


def svg_lines(series: list[dict], width=560, height=190, y_fmt=lambda v: f"{100 * v:.1f}%", x_labels=None) -> str:
    """series = [{"name", "color", "y": [...], "lo": [...]?, "hi": [...]?}] on a shared x index (weeks)."""
    pad_l, pad_r, pad_t, pad_b = 44, 10, 10, 26
    n = max(len(s["y"]) for s in series)
    vals = [v for s in series for k in ("y", "lo", "hi") for v in s.get(k, []) if v is not None]
    ymax = max(vals) * 1.15 if vals else 1
    def x(i): return pad_l + (width - pad_l - pad_r) * (i / max(1, n - 1))
    def y(v): return pad_t + (height - pad_t - pad_b) * (1 - v / ymax)
    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" xmlns="http://www.w3.org/2000/svg">']
    for t in range(5):
        v = ymax * t / 4
        parts.append(f'<line x1="{pad_l}" x2="{width - pad_r}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="#e3ded6"/>'
                     f'<text x="{pad_l - 6}" y="{y(v) + 4:.1f}" font-size="10" text-anchor="end" fill="#5f6670">{y_fmt(v)}</text>')
    for s in series:
        if s.get("lo") and s.get("hi"):
            pts = [(x(i), y(h)) for i, h in enumerate(s["hi"]) if h is not None] + [(x(i), y(l)) for i, l in reversed(list(enumerate(s["lo"]))) if l is not None]
            parts.append('<polygon points="' + " ".join(f"{a:.1f},{b:.1f}" for a, b in pts) + f'" fill="{s["color"]}" opacity="0.15"/>')
        pts = [(x(i), y(v)) for i, v in enumerate(s["y"]) if v is not None]
        parts.append('<polyline fill="none" stroke-width="2" stroke="' + s["color"] + '" points="' + " ".join(f"{a:.1f},{b:.1f}" for a, b in pts) + '"/>')
    if x_labels:
        step = max(1, n // 7)
        for i, lab in enumerate(x_labels):
            if i % step == 0 or i == n - 1:
                parts.append(f'<text x="{x(i):.1f}" y="{height - 8}" font-size="10" text-anchor="middle" fill="#5f6670">{esc(lab)}</text>')
    lx = pad_l + 6
    for s in series:
        parts.append(f'<rect x="{lx}" y="{pad_t}" width="10" height="3" fill="{s["color"]}"/><text x="{lx + 14}" y="{pad_t + 5}" font-size="10" fill="#1f2328">{esc(s["name"])}</text>')
        lx += 18 + 6.5 * len(s["name"])
    parts.append("</svg>")
    return "".join(parts)
