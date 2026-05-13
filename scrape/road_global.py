"""Road traffic fatality rates by country — per-resident-year micromorts.

Source: WHO Global Status Report on Road Safety 2023 + Ministry of Road
Transport and Highways (India) + national equivalents.
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_rate_per_100k
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCE = dict(
    name="WHO — Global Status Report on Road Safety 2023",
    url="https://www.who.int/teams/social-determinants-of-health/safety-and-mobility/global-status-report-on-road-safety-2023",
    publisher="World Health Organization",
)
YEAR = 2022

# (slug, country, rate/100k/yr)
ROWS = [
    ("world",        "World (avg)",               15.0),
    ("india",        "India",                     12.0),
    ("china",        "China",                     17.4),
    ("pakistan",     "Pakistan",                  14.3),
    ("brazil",       "Brazil",                    16.3),
    ("south-africa", "South Africa",              22.2),
    ("us",           "United States",             12.9),
    ("russia",       "Russia",                    15.0),
    ("nigeria",      "Nigeria",                   21.4),
    ("thailand",     "Thailand",                  25.4),
    ("japan",        "Japan",                      3.0),
    ("uk",           "United Kingdom",             2.7),
    ("germany",      "Germany",                    3.7),
    ("sweden",       "Sweden",                     2.0),
    ("norway",       "Norway",                     1.9),
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
                slug=f"road-global:{suffix}-{YEAR}",
                name=f"Road traffic death — {country} ({YEAR})",
                category="transport",
                micromorts=from_rate_per_100k(rate),
                exposure="per_year",
                exposure_detail=f"Per-resident road traffic mortality, {country}",
                region=country,
                year=YEAR,
                source_id=source_id,
                original_value=f"{rate}/100,000/year",
                original_unit="road traffic deaths per 100k per year",
                confidence="high",
            )
            add_tags(conn, risk_id, ["road", "country"])
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"road_global: ingested {ingest(conn)} entries.")
