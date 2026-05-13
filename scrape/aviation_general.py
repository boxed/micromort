"""General aviation + helicopter fatality rates per flight hour.

Source: AOPA Air Safety Institute, 35th Richard G. McSpadden Report (2025;
2023 GA data). NTSB. NSAA-style fatality rates for general aviation are
expressed as fatal accidents per 100,000 flight hours.
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_deaths_per
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCE = dict(
    name="AOPA — Richard G. McSpadden Report (35th edition, 2023 data)",
    url="https://www.aopa.org/training-and-safety/air-safety-institute/accident-analysis/richard-g-mcspadden-report",
    publisher="Aircraft Owners and Pilots Association",
)

ROWS = [
    # slug, name, fatal_accidents_per_100k_hours, year, tags, note
    ("ga-fixed-wing-2023",
     "General aviation fixed-wing (per flight hour, 2023)",
     0.65, 2023,
     ("aviation", "private", "fixed-wing"),
     "Fatal accident rate per 100k flight hours."),
    ("helicopter-2024",
     "Helicopter (per flight hour, 2024)",
     0.44, 2024,
     ("aviation", "helicopter"),
     "Fatal accident rate, all US helicopter ops."),
    ("helicopter-recent-5yr",
     "Helicopter (per flight hour, 5-yr trend)",
     1.02, 2023,
     ("aviation", "helicopter"),
     "Older 5-yr-average fatal accident rate."),
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
        for suffix, name, rate, year, tags, note in ROWS:
            mm = from_deaths_per(rate, 100_000)
            risk_id = upsert_risk(
                conn,
                slug=f"ga:{suffix}",
                name=name,
                category="transport",
                micromorts=mm,
                exposure="per_hour",
                exposure_detail=note,
                year=year,
                source_id=source_id,
                original_value=f"{rate}/100,000 flight hours",
                original_unit="fatal accidents per 100k flight hours",
                confidence="high",
                notes="Note: 'fatal accident' rate; each fatal accident may involve >1 fatality.",
            )
            add_tags(conn, risk_id, list(tags))
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"general aviation: ingested {ingest(conn)} entries.")
