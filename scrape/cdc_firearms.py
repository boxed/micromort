"""US firearm deaths — per-year micromorts.

Source: CDC NCHS WISQARS / Fast Facts on firearm injury (2022 figures).
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_rate_per_100k
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCE = dict(
    name="CDC — Firearm Injury Fast Facts (2022 age-adjusted rates)",
    url="https://www.cdc.gov/firearm-violence/data-research/facts-stats/index.html",
    publisher="US CDC / NCHS",
)
YEAR = 2022

ROWS = [
    ("firearm-total", "Firearm death (all intents)",      14.4, ("firearms",)),
    ("firearm-suicide", "Firearm suicide",                  7.6, ("firearms", "suicide")),
    ("firearm-homicide", "Firearm homicide",                6.2, ("firearms", "homicide")),
    ("firearm-homicide-black", "Firearm homicide (Black, all ages)", 27.0, ("firearms", "homicide", "demographic")),
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
        for suffix, name, rate, tags in ROWS:
            mm = from_rate_per_100k(rate)
            risk_id = upsert_risk(
                conn,
                slug=f"cdc:{suffix}-us-{YEAR}",
                name=f"{name} (US, {YEAR})",
                category="violence",
                micromorts=mm,
                exposure="per_year",
                exposure_detail="Age-adjusted to 2000 US standard population",
                population="US, age-adjusted" if "demographic" not in tags else "US Black, all ages",
                region="US",
                year=YEAR,
                source_id=source_id,
                original_value=f"{rate}/100,000/year",
                original_unit="deaths per 100k per year",
                confidence="high",
            )
            add_tags(conn, risk_id, list(tags))
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"CDC firearms: ingested {ingest(conn)} entries.")
