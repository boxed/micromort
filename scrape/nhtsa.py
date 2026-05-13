"""Derive micromorts from NHTSA FARS top-line numbers.

Source: NHTSA "Overview of Motor Vehicle Traffic Crashes" research notes
(Publication 813705, 2023 data).
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_deaths_per
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCE = dict(
    name="NHTSA — Overview of Motor Vehicle Traffic Crashes, 2023 Data",
    url="https://crashstats.nhtsa.dot.gov/Api/Public/Publication/813705",
    publisher="US DOT NHTSA",
)

# Headline figures from NHTSA Research Note 813705 (2023 data).
US_FATALITIES_2023 = 40_901
US_VMT_2023_MILES = 3_247e9          # 3,247 billion VMT
US_POPULATION_2023 = 334_900_000     # Census mid-2023 est.
YEAR = 2023


def _touch_source_page() -> bool:
    try:
        fetch(SOURCE["url"])
        return True
    except Exception:
        return False


def ingest(conn) -> int:
    alive = _touch_source_page()
    source_id = upsert_source(
        conn,
        accessed_at=dt.date.today().isoformat() if alive else None,
        **SOURCE,
    )
    per_mile = from_deaths_per(US_FATALITIES_2023, US_VMT_2023_MILES)
    per_capita_year = from_deaths_per(US_FATALITIES_2023, US_POPULATION_2023)

    rows = [
        dict(
            slug="nhtsa:us-road-per-mile-2023",
            name="US road travel (per mile, 2023)",
            category="transport",
            micromorts=per_mile,
            exposure="per_mile",
            exposure_detail="Per vehicle mile travelled (all road users)",
            region="US",
            year=YEAR,
            source_id=source_id,
            original_value=f"{US_FATALITIES_2023:,} deaths / {US_VMT_2023_MILES:,.0f} mi VMT",
            original_unit="per mile",
            confidence="high",
            notes="Computed from NHTSA fatalities and FHWA VMT.",
            _tags=("car", "us"),
        ),
        dict(
            slug="nhtsa:us-road-per-capita-year-2023",
            name="US road fatality (average resident, 2023)",
            category="transport",
            micromorts=per_capita_year,
            exposure="per_year",
            exposure_detail="Average risk to one US resident from road fatalities, 2023",
            region="US",
            year=YEAR,
            source_id=source_id,
            original_value=f"{US_FATALITIES_2023:,} deaths / {US_POPULATION_2023:,} pop",
            original_unit="per year",
            confidence="high",
            _tags=("car", "us", "baseline"),
        ),
    ]
    with transaction(conn):
        for r in rows:
            tags = r.pop("_tags")
            slug = r.pop("slug")
            risk_id = upsert_risk(conn, slug=slug, **r)
            add_tags(conn, risk_id, list(tags))
    return len(rows)


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"NHTSA: ingested {ingest(conn)} entries.")
