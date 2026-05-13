"""Under-5 mortality by country — cumulative per live-birth micromorts.

Source: UNICEF Child Mortality 2023 estimates (under-5 mortality rate per
1,000 live births).

Expressed as cumulative µmt over the first 5 years of life — i.e. the
probability that a newborn does not survive to age 5.
"""
from __future__ import annotations

import datetime as dt

from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCE = dict(
    name="UNICEF — Levels & Trends in Child Mortality 2023",
    url="https://data.unicef.org/topic/child-survival/under-five-mortality/",
    publisher="UNICEF Child Mortality Estimation",
)
YEAR = 2023

# (slug, country/region, U5MR per 1,000 live births in 2023)
ROWS = [
    ("world",              "World (average)",                    36.7),
    ("somalia",            "Somalia",                           114.6),
    ("niger",              "Niger",                              105.0),
    ("chad",               "Chad",                               105.0),
    ("nigeria",            "Nigeria",                             107.2),
    ("sub-saharan-africa", "Sub-Saharan Africa (region)",         70.0),
    ("south-asia",         "South Asia (region)",                 32.0),
    ("low-income",         "Low-income countries",                65.0),
    ("middle-income",      "Middle-income countries",             34.0),
    ("high-income",        "High-income countries",                4.4),
    ("us",                 "United States",                        6.3),
    ("china",              "China",                                6.5),
    ("uk",                 "United Kingdom",                       4.0),
    ("japan",              "Japan",                                2.4),
    ("sweden",             "Sweden",                               2.4),
    ("singapore",          "Singapore",                            2.1),
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
            # rate per 1,000 → micromorts (multiply by 1000)
            mm = rate * 1000
            risk_id = upsert_risk(
                conn,
                slug=f"u5:{suffix}-{YEAR}",
                name=f"Under-5 mortality — {country} ({YEAR})",
                category="baseline",
                micromorts=mm,
                exposure="lifetime",
                exposure_detail="Cumulative probability of dying before age 5",
                region=country,
                year=YEAR,
                source_id=source_id,
                original_value=f"{rate}/1,000 live births",
                original_unit="under-5 mortality rate (per 1k LB)",
                confidence="high",
            )
            add_tags(conn, risk_id, ["child", "u5mr", "baseline", "country"])
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"child mortality: ingested {ingest(conn)} entries.")
