"""Commercial aviation safety — per-flight micromorts.

IATA reports a 'fatality risk per million sectors' metric: the probability
that a passenger boarding a flight dies as a result of an aviation accident
on that flight. That is exactly micromorts per sector.

Source: IATA Annual Safety Report 2024.
"""
from __future__ import annotations

import datetime as dt

from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCE = dict(
    name="IATA — Annual Safety Report 2024",
    url="https://www.iata.org/contentassets/a8e49941e8824a058fee3f5ae0c005d9/safety-report-executive-summary-and-safety-overview-2024_final.pdf",
    publisher="International Air Transport Association",
)

# IATA's "fatality risk" is per-million-sectors. 1 µmt per sector = 1 risk
# per million sectors. They report:
ENTRIES = [
    # slug,                year, fatality_risk_per_M_sectors, notes
    ("commercial-aviation-2024", 2024, 0.06, "IATA member + global jet+turboprop."),
    ("commercial-aviation-2023", 2023, 0.03, "Record-low year."),
    ("commercial-aviation-5yr",  2024, 0.10, "Five-year rolling average (2020–2024)."),
    ("commercial-aviation-2005", 2005, 0.69, "Historical reference — 20 years ago."),
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
        for slug, year, rate, note in ENTRIES:
            risk_id = upsert_risk(
                conn,
                slug=f"iata:{slug}",
                name=f"Commercial flight, fatal accident ({year})",
                category="transport",
                micromorts=rate,
                exposure="per_event",
                exposure_detail="Per passenger sector (one flight leg)",
                year=year,
                source_id=source_id,
                original_value=f"{rate} per million sectors",
                original_unit="fatality risk per million sectors",
                confidence="high",
                notes=note,
            )
            add_tags(conn, risk_id, ["aviation", "commercial"])
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"IATA: ingested {ingest(conn)} entries.")
