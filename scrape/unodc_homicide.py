"""UNODC homicide rates — per-resident-year micromorts by country.

Source: UNODC Global Study on Homicide 2023 (covers up to 2022 data).
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_rate_per_100k
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCE = dict(
    name="UNODC — Global Study on Homicide 2023",
    url="https://www.unodc.org/documents/data-and-analysis/gsh/2023/Global_study_on_homicide_2023_web.pdf",
    publisher="United Nations Office on Drugs and Crime",
)
YEAR = 2022

# Country/region, rate per 100,000 in 2022 (UNODC + national equivalents).
ROWS = [
    ("world",          "World (avg)",                5.61),
    ("honduras",       "Honduras",                  35.1),
    ("mexico",         "Mexico",                    25.2),
    ("south-africa",   "South Africa",              43.7),
    ("brazil",         "Brazil",                    21.3),
    ("us",             "United States",              6.3),
    ("el-salvador",    "El Salvador",                7.8),
    ("uk",             "United Kingdom",             1.0),
    ("germany",        "Germany",                    0.9),
    ("france",         "France",                     1.4),
    ("switzerland",    "Switzerland",                0.5),
    ("japan",          "Japan",                      0.23),
    ("norway",         "Norway",                     0.51),
    ("iceland",        "Iceland",                    0.30),
    ("singapore",      "Singapore",                  0.16),
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
        for suffix, country, rate in ROWS:
            risk_id = upsert_risk(
                conn,
                slug=f"unodc:homicide-{suffix}-{YEAR}",
                name=f"Homicide — {country} ({YEAR})",
                category="violence",
                micromorts=from_rate_per_100k(rate),
                exposure="per_year",
                exposure_detail="Intentional homicide rate per 100k population per year",
                region=country,
                year=YEAR,
                source_id=source_id,
                original_value=f"{rate}/100,000/year",
                original_unit="intentional homicides per 100k per year",
                confidence="high",
            )
            add_tags(conn, risk_id, ["homicide", "violence", "country"])
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"UNODC homicide: ingested {ingest(conn)} entries.")
