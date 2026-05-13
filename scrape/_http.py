"""Polite HTTP fetcher with on-disk caching.

Scrapers can be rerun cheaply: each URL is cached for 24h under `cache/`.
"""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

import requests

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"
USER_AGENT = (
    "MicromortDB/0.1 (research; https://example.invalid/micromort)"
)
DEFAULT_TTL_SECONDS = 24 * 3600


def _cache_path(url: str) -> Path:
    h = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    return CACHE_DIR / f"{h}.html"


def fetch(url: str, ttl: int = DEFAULT_TTL_SECONDS, timeout: int = 30) -> str:
    CACHE_DIR.mkdir(exist_ok=True)
    p = _cache_path(url)
    if p.exists() and (time.time() - p.stat().st_mtime) < ttl:
        return p.read_text(encoding="utf-8")
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    p.write_text(resp.text, encoding="utf-8")
    return resp.text
