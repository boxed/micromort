"""Global animal-attributable mortality — mosquitoes, hippos, snakes, deer collisions.

Sources:
- WHO World Malaria Report (mosquito-borne deaths).
- WHO Neglected Tropical Diseases — snakebite envenoming.
- Suraweera et al. 2020 (eLife) — Snakebite deaths in India 2000-2019.
- US III / IIHS — deer-vehicle collisions in the US.
- Africa Freak / Altezza Travel — hippo, elephant, lion, crocodile attack stats.
"""
from __future__ import annotations

import datetime as dt

from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCES = {
    "who_vector": dict(
        name="WHO — Vector-borne diseases",
        url="https://www.who.int/news-room/fact-sheets/detail/vector-borne-diseases",
        publisher="World Health Organization",
    ),
    "who_snakebite": dict(
        name="WHO — Snakebite envenoming",
        url="https://www.who.int/teams/control-of-neglected-tropical-diseases/snakebite-envenoming/prevalence",
        publisher="World Health Organization",
    ),
    "elife_india": dict(
        name="Suraweera et al. 2020 (eLife) — India snakebite deaths",
        url="https://elifesciences.org/articles/54076",
        publisher="eLife",
    ),
    "africa_freak": dict(
        name="Compiled Africa wildlife attack statistics",
        url="https://africafreak.com/most-dangerous-animals-in-africa",
        publisher="Multiple field surveys",
    ),
    "iii_deer": dict(
        name="Insurance Information Institute — Deer-vehicle collisions",
        url="https://www.iii.org/fact-statistic/facts-statistics-deer-vehicle-collisions",
        publisher="III",
    ),
}
WORLD_POP = 7_950_000_000
AFRICA_POP = 1_400_000_000
INDIA_POP = 1_400_000_000
US_POP = 334_900_000

ROWS = [
    # source, slug, name, deaths/yr, population, exposure, tags, note
    ("who_vector", "mosquito-global",
     "Mosquito-borne diseases (global average per resident-year)",
     725_000, WORLD_POP, "per_year",
     ("animal", "vector", "insects"),
     "≥725k annual global deaths from mosquito-borne diseases."),
    ("who_vector", "mosquito-africa",
     "Mosquito-borne diseases (Africa average per resident-year)",
     569_000, AFRICA_POP, "per_year",
     ("animal", "vector", "insects", "africa"),
     "Africa accounts for ~95% of global malaria deaths."),
    ("who_snakebite", "snakebite-global",
     "Snakebite envenoming (global average per resident-year)",
     100_000, WORLD_POP, "per_year",
     ("animal", "snake", "venomous"),
     "WHO range 81-138k deaths/year; midpoint shown."),
    ("elife_india", "snakebite-india",
     "Snakebite envenoming (India per resident-year)",
     58_000, INDIA_POP, "per_year",
     ("animal", "snake", "venomous"),
     "Suraweera 2020: average 58,000 snakebite deaths/year in India 2000-2019."),
    ("africa_freak", "hippo-attack-africa",
     "Hippopotamus attack (Africa per resident-year)",
     1_500, AFRICA_POP, "per_year",
     ("animal", "africa", "mammal"),
     "Estimates range 500-3,000 per year; midpoint shown."),
    ("africa_freak", "crocodile-attack-africa",
     "Crocodile attack (Africa per resident-year)",
     1_000, AFRICA_POP, "per_year",
     ("animal", "africa", "reptile"),
     "~1,000 crocodile-attack deaths/year in Africa."),
    ("africa_freak", "elephant-attack-africa",
     "Elephant attack (Africa per resident-year)",
     500, AFRICA_POP, "per_year",
     ("animal", "africa", "mammal"),
     "~500 elephant-attack deaths/year in Africa."),
    ("africa_freak", "lion-attack-africa",
     "Lion attack (Africa per resident-year)",
     250, AFRICA_POP, "per_year",
     ("animal", "africa", "mammal"),
     "~250 lion-attack deaths/year in Africa."),
    ("iii_deer", "deer-collision-us",
     "Deer-vehicle collision (US per resident-year)",
     440, US_POP, "per_year",
     ("animal", "vehicle"),
     "≈440 deaths/year from deer-vehicle collisions in the US."),
]


def _touch(url: str) -> bool:
    try:
        fetch(url)
        return True
    except Exception:
        return False


def ingest(conn) -> int:
    today = dt.date.today().isoformat()
    src_ids: dict[str, int] = {}
    for k, meta in SOURCES.items():
        alive = _touch(meta["url"])
        src_ids[k] = upsert_source(
            conn,
            accessed_at=today if alive else None,
            **meta,
        )
    n = 0
    with transaction(conn):
        for src_key, slug, name, deaths, pop, exposure, tags, note in ROWS:
            mm = 1_000_000 * deaths / pop
            risk_id = upsert_risk(
                conn,
                slug=f"animg:{slug}",
                name=name,
                category="environmental",
                micromorts=mm,
                exposure=exposure,
                exposure_detail=note,
                source_id=src_ids[src_key],
                original_value=f"~{deaths:,} deaths/yr / {pop:,} pop",
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
    print(f"animals_global: ingested {ingest(conn)} entries.")
