"""BLS Census of Fatal Occupational Injuries (CFOI) — occupational micromorts.

Rates are fatal injuries per 100,000 full-time-equivalent workers per year.
2023 figures from BLS news release T04 (also reported in the BLS 'Economics
Daily' summary for 2023 fatal work injuries).

A 'full-time year' = ~2,000 hours. Per-hour figures are derived assuming
that exposure.
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_rate_per_100k
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCE = dict(
    name="BLS — CFOI Table 4 (fatal work injury rates by occupation, 2023)",
    url="https://www.bls.gov/news.release/cfoi.t04.htm",
    publisher="US Bureau of Labor Statistics",
)
YEAR = 2023
FTE_HOURS_PER_YEAR = 2000.0

# (slug, name, rate per 100k FTE, tags)
OCCUPATIONS: list[tuple[str, str, float, tuple[str, ...]]] = [
    ("logging",        "Logging workers",                       98.9, ("forestry",)),
    ("fishing",        "Fishing & hunting workers",             86.9, ("fishing",)),
    ("roofing",        "Roofers",                               51.8, ("construction",)),
    ("refuse",         "Refuse & recyclable material collectors", 41.4, ("sanitation",)),
    ("pilots",         "Aircraft pilots & flight engineers",    31.3, ("aviation",)),
    ("all-workers",    "All US workers (average)",               3.5, ("baseline",)),
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
        for suffix, name, rate, tags in OCCUPATIONS:
            mm_year = from_rate_per_100k(rate)
            mm_hour = mm_year / FTE_HOURS_PER_YEAR

            ry = upsert_risk(
                conn,
                slug=f"bls:{suffix}-year-{YEAR}",
                name=f"{name} (per FTE year, {YEAR})",
                category="occupation",
                micromorts=mm_year,
                exposure="per_year",
                exposure_detail=f"Per full-time-equivalent work year ({YEAR})",
                region="US",
                year=YEAR,
                source_id=source_id,
                original_value=f"{rate}/100,000 FTE",
                original_unit="deaths per 100k FTE per year",
                confidence="high",
            )
            add_tags(conn, ry, list(tags) + ["occupation"])

            rh = upsert_risk(
                conn,
                slug=f"bls:{suffix}-hour-{YEAR}",
                name=f"{name} (per work hour, {YEAR})",
                category="occupation",
                micromorts=mm_hour,
                exposure="per_hour",
                exposure_detail=f"Derived from {rate}/100k FTE assuming 2000 h/yr",
                region="US",
                year=YEAR,
                source_id=source_id,
                original_value=f"{rate}/100,000 FTE / 2000 h",
                original_unit="derived per work hour",
                confidence="medium",
            )
            add_tags(conn, rh, list(tags) + ["occupation", "derived"])
            n += 2
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"BLS CFOI: ingested {ingest(conn)} entries.")
