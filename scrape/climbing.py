"""Rock climbing & mountaineering fatality rates.

Sources:
- UK mountain-leader review: 47 climbing deaths over 2000-2019; cited
  incidence rate of 1 in 10,000 active participants.
- Victoria Australia: 6.6 serious-injury-or-deaths per 100,000 participants.
- AAC (American Alpine Club) annual accident reporting.

These are per-active-participant per-year rates; per-climb rates are much
lower but vary wildly by discipline (sport vs ice vs alpine).
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_one_in, from_rate_per_100k
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCES = {
    "aac": dict(
        name="American Alpine Club — Climbing Accident Statistics",
        url="https://www.climbing.com/news/9-takeaways-climbing-accidents-2024/",
        publisher="American Alpine Club / Climbing magazine",
    ),
    "victoria_2010": dict(
        name="Victoria Australia rock climbing injury study",
        url="https://pmc.ncbi.nlm.nih.gov/articles/PMC6843304/",
        publisher="Mortality in Different Mountain Sports Activities",
    ),
}

ROWS = [
    ("aac", "rock-climbing-uk-participant",
     "Rock climbing (UK, active participant per year)",
     "activity", from_one_in(10_000), "per_year",
     "1 in 10,000 active participants per year (UK mountain leader data)",
     ("climbing", "outdoor")),
    ("victoria_2010", "rock-climbing-aus-participant",
     "Rock climbing (Victoria, AU, active participant per year)",
     "activity", from_rate_per_100k(6.6), "per_year",
     "6.6 serious-injury-or-deaths per 100k participants",
     ("climbing", "outdoor")),
]


def _touch(url: str) -> bool:
    try:
        fetch(url)
        return True
    except Exception:
        return False


def ingest(conn) -> int:
    today = dt.date.today().isoformat()
    src_ids: dict[str, int] = {}
    for k, meta in SOURCES.items():
        alive = _touch(meta["url"])
        src_ids[k] = upsert_source(
            conn,
            accessed_at=today if alive else None,
            **meta,
        )
    n = 0
    with transaction(conn):
        for src_key, slug, name, cat, mm, exposure, note, tags in ROWS:
            risk_id = upsert_risk(
                conn,
                slug=f"climb:{slug}",
                name=name,
                category=cat,
                micromorts=mm,
                exposure=exposure,
                exposure_detail=note,
                source_id=src_ids[src_key],
                confidence="medium",
            )
            add_tags(conn, risk_id, list(tags))
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"climbing: ingested {ingest(conn)} entries.")
