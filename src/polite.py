"""Polite HTTP helper used by src/fetch_public.py and src/clickhouse_play.py.

- official APIs and files only, no workaround of any block;
- at most one request per second;
- neutral User-Agent, no personal data;
- raw responses cached in data/raw/ (never published).
"""
import time
from pathlib import Path

import requests

USER_AGENT = "fingerprint-case-study/1.0"
MIN_DELAY_S = 1.0
_last = 0.0


def _wait():
    """Sleep so that two requests are always at least MIN_DELAY_S apart."""
    global _last
    wait = MIN_DELAY_S - (time.time() - _last)
    if wait > 0:
        time.sleep(wait)
    _last = time.time()


def get(url: str, timeout: int = 300, stream: bool = False):
    _wait()
    try:
        return requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout, stream=stream)
    except requests.RequestException as e:
        print("[error]", url, e)
        return None


def post(url: str, data: bytes, timeout: int = 120):
    _wait()
    try:
        return requests.post(url, data=data, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    except requests.RequestException as e:
        print("[error]", url, e)
        return None


def cached(url: str, path: Path) -> Path | None:
    """Download url to path once (streamed to disk); later runs reuse the cached file."""
    if path.exists() and path.stat().st_size > 0:
        return path
    r = get(url, stream=True)
    if r is None or r.status_code != 200:
        print("[skip]", url, getattr(r, "status_code", None))
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    with open(tmp, "wb") as f:
        for chunk in r.iter_content(chunk_size=1 << 20):
            f.write(chunk)
    tmp.replace(path)
    return path
