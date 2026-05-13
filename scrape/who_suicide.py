"""Suicide mortality by country — per-year micromorts.

Source: WHO Global Health Estimates + Wikipedia 'List of countries by
suicide rate' (compiled from WHO data, most recent available year).

Note: These are baseline-type population averages, not "per attempt"
event probabilities.
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_rate_per_100k
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCE = dict(
    name="WHO Global Health Estimates — Suicide mortality by country",
    url="https://www.who.int/data/gho/data/themes/mental-health/suicide-rates",
    publisher="World Health Organization",
)
YEAR = 2022

# (slug, country, rate per 100k/yr)
ROWS = [
    ("world",        "World (average)",       9.1),
    ("lesotho",      "Lesotho",              72.4),
    ("guyana",       "Guyana",               40.3),
    ("south-korea",  "South Korea",          28.6),
    ("lithuania",    "Lithuania",            26.1),
    ("russia",       "Russia",               25.1),
    ("us",           "United States",        14.2),
    ("japan",        "Japan",                15.4),
    ("germany",      "Germany",              12.3),
    ("uk",           "United Kingdom",        7.9),
    ("italy",        "Italy",                 5.9),
    ("mexico",       "Mexico",                5.4),
    ("turkey",       "Turkey",                2.3),
    ("indonesia",    "Indonesia",             2.0),
    ("jordan",       "Jordan",                1.7),
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
                slug=f"who-suicide:{suffix}-{YEAR}",
                name=f"Suicide — {country} ({YEAR})",
                category="violence",
                micromorts=from_rate_per_100k(rate),
                exposure="per_year",
                exposure_detail="Population-average suicide rate per 100k per year",
                region=country,
                year=YEAR,
                source_id=source_id,
                original_value=f"{rate}/100,000/year",
                original_unit="suicides per 100k per year",
                confidence="high",
            )
            add_tags(conn, risk_id, ["suicide", "violence", "country"])
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"WHO suicide: ingested {ingest(conn)} entries.")
