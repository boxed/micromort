"""Recreational scuba diving — per-dive micromorts (DAN).

Source: DAN Annual Diving Report (2020 ed.) reports a US recreational
fatality rate of 1.8 per million dives over 2006-2015. Supplementary
rates: 0.48 / 100k student dives, 0.54 / 100k BSAC dives, 1.03 / 100k
non-BSAC UK dives (2007).
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_deaths_per
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCE = dict(
    name="DAN — Annual Diving Report 2020",
    url="https://www.ncbi.nlm.nih.gov/books/NBK582505/",
    publisher="Divers Alert Network",
)

ROWS = [
    # slug, name, deaths, per N dives, year, tags
    ("dan-us-recreational",
     "Recreational scuba dive (US, 2006-2015 avg)",
     1.8, 1_000_000, 2015,
     ("water", "scuba", "us"),
     "1.8 deaths per million recreational dives, DAN multi-year average."),
    ("dan-uk-bsac-2007",
     "Scuba dive (UK BSAC member, 2007)",
     0.54, 100_000, 2007,
     ("water", "scuba", "uk"),
     "0.54 deaths per 100k BSAC dives."),
    ("dan-uk-nonbsac-2007",
     "Scuba dive (UK non-BSAC, 2007)",
     1.03, 100_000, 2007,
     ("water", "scuba", "uk"),
     "1.03 deaths per 100k non-BSAC dives."),
    ("dan-student-2007",
     "Scuba training dive (student, 2007)",
     0.48, 100_000, 2007,
     ("water", "scuba", "training"),
     "0.48 deaths per 100k student dives."),
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
        for suffix, name, deaths, per_n, year, tags, note in ROWS:
            risk_id = upsert_risk(
                conn,
                slug=f"dan:{suffix}",
                name=name,
                category="activity",
                micromorts=from_deaths_per(deaths, per_n),
                exposure="per_dive",
                exposure_detail=note,
                year=year,
                source_id=source_id,
                original_value=f"{deaths}/{per_n:,} dives",
                original_unit="deaths per dive",
                confidence="medium",
            )
            add_tags(conn, risk_id, list(tags))
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"DAN diving: ingested {ingest(conn)} entries.")
