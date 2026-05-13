"""National Park Service — deaths per visit.

Source: NPS Mortality Data page + 2007-2024 panel analyses.
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_deaths_per
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCE = dict(
    name="NPS Mortality Data + Panish 2007-2024 analysis",
    url="https://www.nps.gov/aboutus/mortality-data.htm",
    publisher="US National Park Service",
)

ROWS = [
    ("nps-average-visit",
     "Visiting a US National Park (average)",
     243, 312_000_000, "Per visit, averaged across all NPS lands.",
     ("parks", "outdoor")),
    ("nps-north-cascades",
     "Visiting North Cascades NP",
     60, 1_000_000, "Highest per-visit fatality rate of any US NP (~60/M visits).",
     ("parks", "outdoor", "mountaineering")),
    ("nps-virgin-islands",
     "Visiting Virgin Islands NP",
     6, 1_000_000, "Mostly drownings.",
     ("parks", "outdoor", "water")),
    ("nps-big-bend",
     "Visiting Big Bend NP",
     5.8, 1_000_000, "Environmental hazards.",
     ("parks", "outdoor", "desert")),
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
        for suffix, name, deaths, visits, note, tags in ROWS:
            risk_id = upsert_risk(
                conn,
                slug=f"nps:{suffix}",
                name=name,
                category="activity",
                micromorts=from_deaths_per(deaths, visits),
                exposure="per_event",
                exposure_detail=note,
                region="US",
                source_id=source_id,
                original_value=f"{deaths}/{visits:,} visits",
                original_unit="deaths per visit",
                confidence="medium",
            )
            add_tags(conn, risk_id, list(tags))
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"NPS: ingested {ingest(conn)} entries.")
