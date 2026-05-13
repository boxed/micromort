"""CDC NCHS leading causes of death — age-adjusted rates → annual micromorts.

Numbers from NCHS Data Brief No. 521 (Dec 2024), "Mortality in the United
States, 2023". Rates are age-adjusted to the 2000 US standard population.
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_rate_per_100k
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCE = dict(
    name="CDC NCHS — Mortality in the United States, 2023",
    url="https://www.cdc.gov/nchs/products/databriefs/db521.htm",
    publisher="US CDC / NCHS",
)
YEAR = 2023

# (slug-suffix, name, age-adjusted rate per 100,000, tags)
CAUSES: list[tuple[str, str, float, tuple[str, ...]]] = [
    ("heart-disease",  "Heart disease",                   162.1, ("cardiovascular",)),
    ("cancer",         "Cancer (malignant neoplasms)",    141.8, ("cancer",)),
    ("accidents",      "Unintentional injuries",           62.3, ("accident",)),
    ("stroke",         "Stroke (cerebrovascular)",         39.0, ("cardiovascular",)),
    ("clrd",           "Chronic lower respiratory",        33.4, ("respiratory",)),
    ("alzheimer",      "Alzheimer disease",                27.7, ("neuro",)),
    ("diabetes",       "Diabetes mellitus",                22.4, ("metabolic",)),
    ("kidney",         "Kidney disease (nephritis etc.)",  13.1, ("renal",)),
    ("liver",          "Chronic liver disease / cirrhosis",13.0, ("alcohol",)),
    ("covid19",        "COVID-19",                         11.9, ("covid", "infectious")),
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
        for suffix, name, rate, tags in CAUSES:
            micromorts = from_rate_per_100k(rate)
            risk_id = upsert_risk(
                conn,
                slug=f"cdc:{suffix}-us-{YEAR}",
                name=f"{name} (US, {YEAR})",
                category="disease",
                micromorts=micromorts,
                exposure="per_year",
                exposure_detail=f"Age-adjusted US mortality, {YEAR}",
                population="US, age-adjusted (2000 std)",
                region="US",
                year=YEAR,
                source_id=source_id,
                original_value=f"{rate}/100,000",
                original_unit="age-adjusted deaths per 100k per year",
                confidence="high",
            )
            add_tags(conn, risk_id, list(tags))
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"CDC causes: ingested {ingest(conn)} entries.")
