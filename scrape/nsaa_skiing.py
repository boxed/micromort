"""US downhill skiing & snowboarding — per-visit fatality rate.

Source: National Ski Areas Association annual fatality fact sheet.
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_deaths_per
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCE = dict(
    name="NSAA — Fatality Fact Sheet 2023/24",
    url="https://nsaa.org/webdocs/Media_Public/IndustryStats/fatality_fact_sheet_2024.pdf",
    publisher="National Ski Areas Association",
)

ROWS = [
    ("ski-resort-10yr-avg",
     "Ski / snowboard at US resort (per visit, 10-yr avg)",
     0.74, 1_000_000, "0.74 deaths per million skier visits, 10-yr average.",
     ("snow", "outdoor")),
    ("ski-resort-2023-24",
     "Ski / snowboard at US resort (per visit, 2023/24)",
     35, 60_000_000, "35 fatalities in 2023/24 season (≈60M skier visits).",
     ("snow", "outdoor")),
]


def _touch() -> bool:
    try:
        fetch(SOURCE["url"])
        return True
    except Exception:
        return False


def ingest(conn) -> int:
    alive = _touch()
    source_id = upsert_source(
        conn,
        accessed_at=dt.date.today().isoformat() if alive else None,
        **SOURCE,
    )
    n = 0
    with transaction(conn):
        for suffix, name, deaths, per_n, note, tags in ROWS:
            risk_id = upsert_risk(
                conn,
                slug=f"nsaa:{suffix}",
                name=name,
                category="activity",
                micromorts=from_deaths_per(deaths, per_n),
                exposure="per_event",
                exposure_detail=note,
                region="US",
                source_id=source_id,
                original_value=f"{deaths}/{per_n:,} visits",
                original_unit="per skier-visit",
                confidence="high",
            )
            add_tags(conn, risk_id, list(tags))
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"NSAA skiing: ingested {ingest(conn)} entries.")
