"""Diarrheal disease mortality by region — per-resident-year.

Source: GBD 2019/2021; BMC Public Health 2024 sub-Saharan systematic
review; WHO Diarrhoeal Disease fact sheet.
"""
from __future__ import annotations

import datetime as dt

from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCE = dict(
    name="GBD 2019 + WHO + BMC Public Health 2024 — Diarrheal mortality",
    url="https://www.who.int/news-room/fact-sheets/detail/diarrhoeal-disease",
    publisher="World Health Organization / IHME",
)
WORLD_POP = 7_950_000_000
AFRICA_POP = 1_400_000_000

ROWS = [
    # slug, name, deaths/year, population, region, tags, note
    ("diarrheal-world",   "Diarrheal disease (global avg per resident-year)",
     1_300_000, WORLD_POP, "world",
     ("infection", "diarrhea", "wash"),
     "~1.3 million annual global deaths; concentrated in young children."),
    ("diarrheal-africa",  "Diarrheal disease (Africa avg per resident-year)",
     515_031, AFRICA_POP, "africa",
     ("infection", "diarrhea", "wash"),
     "515k annual deaths in WHO African Region (2020 estimate)."),
    ("diarrheal-u5-global","Diarrheal disease (global child under 5)",
     443_832, 660_000_000, "world",
     ("infection", "diarrhea", "child", "wash"),
     "Global U5 diarrhea deaths divided by ~660M children under 5."),
    ("diarrheal-u5-africa","Diarrheal disease (African child under 5)",
     330_000, 130_000_000, "africa",
     ("infection", "diarrhea", "child", "wash"),
     "330k African U5 deaths attributable to diarrhea annually."),
    ("cholera-deaths-world","Cholera (global avg per resident-year)",
     143_000, WORLD_POP, "world",
     ("infection", "cholera", "wash"),
     "WHO estimated cholera deaths in recent global outbreaks."),
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
        for slug, name, deaths, pop, region, tags, note in ROWS:
            mm = 1_000_000 * deaths / pop
            risk_id = upsert_risk(
                conn,
                slug=f"diarr:{slug}",
                name=name,
                category="disease",
                micromorts=mm,
                exposure="per_year",
                exposure_detail=note,
                region=region,
                source_id=source_id,
                original_value=f"{deaths:,} deaths/yr / {pop:,} pop",
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
    print(f"diarrheal_global: ingested {ingest(conn)} entries.")
