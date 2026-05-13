"""Misc US natural-hazard and accidental death rates → per-year micromorts.

Sources: National Weather Service (lightning), CDC/MMWR drowning, animal-
related fatality study (Langley & Kearney 2025), CDC bicycle safety,
NHTSA pedestrian data.
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_deaths_per, from_rate_per_100k
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCES = {
    "nws_lightning": dict(
        name="NOAA NWS — Lightning Fatalities",
        url="https://www.weather.gov/safety/lightning-fatalities",
        publisher="US NOAA / National Weather Service",
    ),
    "cdc_drowning": dict(
        name="CDC MMWR — Drowning Death Rates (Vital Signs, 2018-2021)",
        url="https://www.cdc.gov/mmwr/volumes/73/wr/mm7320e1.htm",
        publisher="US CDC",
    ),
    "animal_2025": dict(
        name="Langley & Kearney 2025 — Animal-Related Fatalities (2018-2023)",
        url="https://journals.sagepub.com/doi/full/10.1177/11786302251355353",
        publisher="Environmental Health Insights",
    ),
    "iihs_bicyclists": dict(
        name="IIHS — Fatality Facts: Bicyclists 2023",
        url="https://www.iihs.org/research-areas/fatality-statistics/detail/bicyclists",
        publisher="Insurance Institute for Highway Safety",
    ),
}

# Each row: (source_key, slug, name, micromorts/year, original, exposure_detail, tags)
US_POP_2023 = 334_900_000

ROWS = [
    ("nws_lightning",
     "lightning-us",
     "Lightning strike (US)",
     # 18.6 deaths/year on a US population of ~334.9M
     1_000_000 * 18.6 / US_POP_2023,
     "18.6 deaths/year (10-yr avg 2015-2024)",
     "Average US resident",
     ("weather", "natural")),
    ("cdc_drowning",
     "drowning-us",
     "Drowning (US, age-adjusted)",
     from_rate_per_100k(1.31),
     "1.31/100,000/year (2018-2021)",
     "Age-adjusted",
     ("water", "accident")),
    ("animal_2025",
     "animals-all-us",
     "Animal-related death (US, any)",
     1_000_000 * 0.808 / 1_000_000,  # rate per million person-years
     "0.808 deaths per million person-years",
     "Hornets/wasps/bees, mammals, and dogs combined",
     ("natural", "animal")),
    ("animal_2025",
     "animals-bees-wasps",
     "Death by hornet / wasp / bee sting (US)",
     1_000_000 * 0.808 * 0.31 / 1_000_000,
     "31% of 267 deaths/yr",
     "Insect-induced anaphylaxis & trauma",
     ("natural", "animal", "insects")),
    ("animal_2025",
     "animals-dogs",
     "Death by dog (US)",
     1_000_000 * 0.808 * 0.262 / 1_000_000,
     "26.2% of 267 deaths/yr",
     "Dog-attack fatalities",
     ("animal",)),
    ("iihs_bicyclists",
     "bicyclist-us",
     "Bicyclist death (avg US resident, 2023)",
     1_000_000 * 1377 / US_POP_2023,
     "1,377 bicyclist deaths / US pop",
     "Per US resident per year, not normalized to riders",
     ("bicycle",)),
]


def _touch(url: str) -> bool:
    try:
        fetch(url)
        return True
    except Exception:
        return False


def ingest(conn) -> int:
    source_ids: dict[str, int] = {}
    today = dt.date.today().isoformat()
    for key, meta in SOURCES.items():
        alive = _touch(meta["url"])
        source_ids[key] = upsert_source(
            conn,
            accessed_at=today if alive else None,
            **meta,
        )
    n = 0
    with transaction(conn):
        for src_key, slug, name, mm, orig, detail, tags in ROWS:
            risk_id = upsert_risk(
                conn,
                slug=f"hazards:{slug}",
                name=name,
                category="environmental",
                micromorts=mm,
                exposure="per_year",
                exposure_detail=detail,
                region="US",
                year=2023,
                source_id=source_ids[src_key],
                original_value=orig,
                original_unit="deaths per year (normalized)",
                confidence="high",
            )
            add_tags(conn, risk_id, list(tags))
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"CDC hazards: ingested {ingest(conn)} entries.")
