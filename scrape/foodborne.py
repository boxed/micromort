"""Foodborne illness — per US-resident-year micromorts.

Source: CDC, 'Burden of Foodborne Illness in the US' (~1,300 deaths/yr from
known pathogens) plus FoodNet 2022 pathogen-specific rates.
"""
from __future__ import annotations

import datetime as dt

from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCE = dict(
    name="CDC — Burden of Foodborne Illness (US estimates) + FoodNet 2022",
    url="https://www.cdc.gov/food-safety/php/data-research/foodborne-illness-burden/index.html",
    publisher="US CDC",
)
US_POP = 334_900_000

# (slug, name, US deaths/year, tags, note)
ROWS = [
    ("foodborne-all",     "Foodborne illness (US, all known pathogens)", 1_300, ("food", "pathogen"),
     "≈1,300 deaths/year from known foodborne pathogens."),
    ("salmonella",        "Salmonella (foodborne, US)",                    238, ("food", "pathogen"),
     "Leading cause of foodborne illness death in the US."),
    ("listeria",          "Listeria monocytogenes (foodborne, US)",        260, ("food", "pathogen"),
     "Highest case-fatality (18-30%) among foodborne pathogens; ~1,600 cases/yr."),
    ("vibrio",            "Vibrio (foodborne, US)",                         50, ("food", "pathogen"),
     "Mostly V. vulnificus from raw shellfish (Gulf, summer)."),
    ("stec",              "Shiga-toxin E. coli (STEC, US)",                 30, ("food", "pathogen"),
     "Includes E. coli O157:H7 plus other Shiga-toxin strains."),
    ("norovirus",         "Norovirus foodborne (US)",                      570, ("food", "pathogen"),
     "Most common foodborne illness overall; rarely lethal but high case load."),
    ("campylobacter",     "Campylobacter (US)",                             76, ("food", "pathogen"),
     "Common from undercooked poultry."),
    ("toxoplasma",        "Toxoplasma gondii (foodborne, US)",             327, ("food", "pathogen"),
     "Largely from undercooked meat; severe in immunocompromised."),
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
                slug=f"food:{suffix}",
                name=name,
                category="food",
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
    print(f"foodborne: ingested {ingest(conn)} entries.")
