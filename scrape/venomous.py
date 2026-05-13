"""Venomous animal fatalities — per-year, US population baseline.

Source: Langley & Kearney 2025, 'Animal-Related Fatalities in the United
States 2018-2023' (267 deaths/yr; 0.808/M person-years).
"""
from __future__ import annotations

import datetime as dt

from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCE = dict(
    name="Langley & Kearney 2025 — Animal-Related Fatalities, US 2018-2023",
    url="https://journals.sagepub.com/doi/full/10.1177/11786302251355353",
    publisher="Environmental Health Insights",
)
US_POP = 334_900_000
TOTAL_ANIMAL_DEATHS_PER_YEAR = 267

# (slug, name, share, tags)
ROWS = [
    ("snake-bite",      "Snake/lizard fatal envenomation (US)",  0.019, ("animal", "venomous")),
    ("spider-bite",     "Spider fatal envenomation (US)",         0.016, ("animal", "venomous")),
    ("other-arthropod", "Other venomous arthropods (US)",         0.049, ("animal", "venomous")),
    # Manually add categories not in shares table
]

# Standalone constants (not a percentage of 267):
SNAKE_BITE_DEATHS_PER_YEAR = 5   # CDC: ~5 deaths/yr from snake bites
JELLYFISH_DEATHS_GLOBAL = 100    # box jellyfish global estimate; treat as per ~7.95B

ADDITIONAL = [
    # slug, name, deaths/yr, denom, region, tags, note
    ("snake-cdc",  "Snake bite fatality (US, CDC)",
     5, US_POP, "US",
     ("animal", "venomous", "snake"),
     "5 deaths from 7-8k venomous snake bites/year."),
    ("jellyfish-global", "Box-jellyfish fatality (global avg resident)",
     100, 7_950_000_000, "world",
     ("animal", "venomous", "marine"),
     "≈100 fatalities/yr globally (concentrated in Indo-Pacific)."),
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
        # Share-of-267 rows
        for suffix, name, share, tags in ROWS:
            yearly_deaths = TOTAL_ANIMAL_DEATHS_PER_YEAR * share
            mm = 1_000_000 * yearly_deaths / US_POP
            risk_id = upsert_risk(
                conn,
                slug=f"venom:{suffix}",
                name=name,
                category="environmental",
                micromorts=mm,
                exposure="per_year",
                exposure_detail=f"{share*100:.1f}% of 267 animal-related deaths/year, US",
                region="US",
                source_id=source_id,
                original_value=f"{yearly_deaths:.1f}/{US_POP:,}/yr",
                original_unit="US deaths per year per population",
                confidence="medium",
            )
            add_tags(conn, risk_id, list(tags))
            n += 1

        # Standalone rows
        for suffix, name, d, denom, region, tags, note in ADDITIONAL:
            mm = 1_000_000 * d / denom
            risk_id = upsert_risk(
                conn,
                slug=f"venom:{suffix}",
                name=name,
                category="environmental",
                micromorts=mm,
                exposure="per_year",
                exposure_detail=note,
                region=region,
                source_id=source_id,
                original_value=f"{d}/{denom:,}/yr",
                original_unit="deaths per year per population",
                confidence="medium",
            )
            add_tags(conn, risk_id, list(tags))
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"venomous: ingested {ingest(conn)} entries.")
