"""Download the public sources once (cached in data/raw/, never published) and write small, publishable
aggregates to data/processed/. One request per second at most, User-Agent fingerprint-case-study/1.0.

    python src/fetch_public.py            # downloads only what is missing, then rebuilds the extracts

Sources (all tested on 2026-11-23, see data/README.md for licences):
- Fingerprint job post (Greenhouse API), open-roles list, GitHub repo and releases of fingerprintjs/fingerprintjs
- Fingerprint public documentation pages (definitions quoted briefly in the report)
- Chrome (Chromium Dash), Firefox (Mozilla product-details), iOS (endoflife.date) release calendars
- Wikimedia browser shares (weekly TSV) and unique devices (Analytics API)
- ClickBench hits_0..hits_4 Parquet files (real, anonymised 2013 web-analytics traffic)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from polite import cached  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"

SRC = {
    "job.json": "https://boards-api.greenhouse.io/v1/boards/fingerprint/jobs/6266169004",
    "jobs_list.json": "https://boards-api.greenhouse.io/v1/boards/fingerprint/jobs",
    "gh_repo.json": "https://api.github.com/repos/fingerprintjs/fingerprintjs",
    "gh_releases.json": "https://api.github.com/repos/fingerprintjs/fingerprintjs/releases?per_page=100",
    "doc_accuracy.md": "https://docs.fingerprint.com/docs/identification-accuracy-and-confidence.md",
    "doc_identify.md": "https://docs.fingerprint.com/docs/identify-visitors.md",
    "doc_mcp.md": "https://docs.fingerprint.com/ai/mcp-server.md",
    "chrome_releases.json": "https://chromiumdash.appspot.com/fetch_releases?channel=Stable&platform=Windows&num=200",
    "firefox_major.json": "https://product-details.mozilla.org/1.0/firefox_history_major_releases.json",
    "ios.json": "https://endoflife.date/api/v1/products/ios",
    "wikimedia_browsers.tsv": "https://analytics.wikimedia.org/published/datasets/periodic/reports/metrics/browser/all_sites_by_os_and_browser.tsv",
    "wikimedia_unique_devices.json": "https://wikimedia.org/api/rest_v1/metrics/unique-devices/en.wikipedia.org/all-sites/daily/20250101/20261121",
}
for i in range(5):
    SRC[f"hits_{i}.parquet"] = f"https://datasets.clickhouse.com/hits_compatible/athena_partitioned/hits_{i}.parquet"


def download():
    for name, url in SRC.items():
        p = cached(url, RAW / name)
        print(("[ok]  " if p else "[miss]"), name)


if __name__ == "__main__":
    download()
    if "--download-only" not in sys.argv:
        import extracts  # noqa: E402  (processing lives in src/extracts.py)
        extracts.main()
