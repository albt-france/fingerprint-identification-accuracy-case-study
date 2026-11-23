"""Generate the dbt documentation site and copy it to dbt-docs/ (published with GitHub Pages).

`dbt docs generate --static` writes one self-contained HTML file (manifest and catalog embedded). Absolute local paths
in the embedded JSON are replaced by repository-relative ones, so no local folder name is published.

    python src/build_dbt_docs.py
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DBT = str(Path(sys.executable).parent / "dbt")
OUT = ROOT / "dbt-docs"


def main():
    subprocess.run([DBT, "docs", "generate", "--static", "--profiles-dir", ".", "--target-path", "target_docs"],
                   cwd=ROOT / "dbt", check=True, capture_output=True, text=True)
    html = (ROOT / "dbt" / "target_docs" / "static_index.html").read_text(encoding="utf-8")
    root_variants = {str(ROOT), str(ROOT).replace("\\", "/"), str(ROOT).replace("\\", "\\\\"), str(ROOT).replace("\\", "\\\\\\\\")}
    for v in sorted(root_variants, key=len, reverse=True):
        html = html.replace(v, ".")
    # any remaining Windows user folder would be a leak: fail loudly instead of publishing it
    if re.search(r"[A-Za-z]:[\\/]+Users[\\/]", html):
        raise SystemExit("local user path left in the dbt docs")
    OUT.mkdir(exist_ok=True)
    (OUT / "index.html").write_text(html, encoding="utf-8")
    print("written", (OUT / "index.html").relative_to(ROOT), f"{len(html) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
