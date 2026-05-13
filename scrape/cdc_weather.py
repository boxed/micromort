"""US weather-related deaths — per US-resident per year.

Sources: NWS Weather Fatalities, EPA heat mortality estimates, NSC Injury
Facts. We compute the average resident risk for each weather class.
"""
from __future__ import annotations

import datetime as dt

from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCE = dict(
    name="NWS / EPA / NSC — US weather-related fatalities",
    url="https://www.weather.gov/hazstat/",
    publisher="US National Weather Service",
)
US_POP = 334_900_000

# (slug, name, annual_us_deaths, tags, note)
ROWS = [
    ("heat",      "Extreme heat (US average resident)",       1300, ("weather", "heat"),
     "EPA estimate ~1,300 deaths/yr; NOAA 30-yr avg lower (~158)."),
    ("cold",      "Extreme cold / hypothermia (US)",           1330, ("weather", "cold"),
     "CDC excess cold-related mortality."),
    ("tornado",   "Tornado fatality (US)",                       71, ("weather", "tornado"),
     "30-yr average."),
    ("hurricane", "Hurricane / tropical storm (US)",             45, ("weather", "tropical"),
     "30-yr average direct deaths."),
    ("flood",     "Flood (US)",                                  88, ("weather", "water"),
     "30-yr average."),
    ("lightning", "Lightning (US, redundant cross-check)",       19, ("weather", "lightning"),
     "10-yr avg ~19 deaths/yr."),
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
        for suffix, name, deaths, tags, note in ROWS:
            mm = 1_000_000 * deaths / US_POP
            risk_id = upsert_risk(
                conn,
                slug=f"wx:{suffix}",
                name=name,
                category="environmental",
                micromorts=mm,
                exposure="per_year",
                exposure_detail=note,
                region="US",
                source_id=source_id,
                original_value=f"~{deaths} deaths/yr / {US_POP:,} pop",
                original_unit="US deaths per year per population",
                confidence="medium",
            )
            add_tags(conn, risk_id, list(tags))
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"CDC weather: ingested {ingest(conn)} entries.")
