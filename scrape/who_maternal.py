"""Global maternal mortality — per-delivery micromorts by region.

Source: WHO/UNICEF/UNFPA/World Bank, 'Trends in Maternal Mortality 2000-2023',
released 2024. MMR is maternal deaths per 100,000 live births.
"""
from __future__ import annotations

import datetime as dt

from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCE = dict(
    name="WHO — Trends in Maternal Mortality 2000-2023",
    url="https://www.who.int/publications/i/item/9789240108462",
    publisher="WHO / UNICEF / UNFPA / World Bank Group",
)
YEAR = 2023

# Region / country -> MMR per 100k live births.  1 µmt = 1 death / million,
# so MMR/100k * 10 = µmt per live birth.
ROWS = [
    ("world",                          "World (avg)",                            197),
    ("subsaharan-africa",              "Sub-Saharan Africa",                     454),
    ("low-income-countries",           "Low-income countries",                   346),
    ("high-income-countries",          "High-income countries",                   10),
    ("australia-nz",                   "Australia & New Zealand",                  3),
    ("liberia",                        "Liberia",                                652),
    ("somalia",                        "Somalia",                                621),
    ("afghanistan",                    "Afghanistan",                            620),
    ("lesotho",                        "Lesotho",                                566),
    ("guinea",                         "Guinea",                                 553),
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
        for suffix, region, mmr in ROWS:
            micromorts = mmr * 10  # MMR per 100k → µmt per live birth
            risk_id = upsert_risk(
                conn,
                slug=f"who-maternal:{suffix}-{YEAR}",
                name=f"Childbirth — {region} ({YEAR})",
                category="medical",
                micromorts=micromorts,
                exposure="per_event",
                exposure_detail=f"Maternal death per live birth, {region}",
                region=region,
                year=YEAR,
                source_id=source_id,
                original_value=f"MMR {mmr}/100,000 live births",
                original_unit="maternal deaths per 100k live births",
                confidence="high",
            )
            add_tags(conn, risk_id, ["pregnancy", "maternal"])
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"WHO maternal: ingested {ingest(conn)} entries.")
