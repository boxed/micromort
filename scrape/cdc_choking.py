"""Accidental choking / asphyxiation by food — US per-year micromorts.

Source: NSC, CDC NCHS unintentional injury / suffocation tables.
"""
from __future__ import annotations

import datetime as dt

from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCE = dict(
    name="NSC + CDC — Choking & accidental suffocation",
    url="https://www.nsc.org/community-safety/safety-topics/choking",
    publisher="US National Safety Council / CDC",
)
US_POP = 334_900_000

ROWS = [
    ("choking-all",        "Choking on food / object (US, any age)",  5_500, "All-ages average."),
    ("choking-child-day",  "Child choking on food (US, per child-day)", 73, "Approximate, one child dies every ~5 days."),
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
        # All-ages
        all_deaths = 5_500
        risk_id = upsert_risk(
            conn,
            slug="choke:all-us",
            name="Choking / asphyxiation on food or object (US)",
            category="environmental",
            micromorts=1_000_000 * all_deaths / US_POP,
            exposure="per_year",
            exposure_detail="≈5,500 deaths/yr; rises sharply after age 71.",
            region="US",
            source_id=source_id,
            original_value=f"{all_deaths}/{US_POP:,}/yr",
            original_unit="US deaths per year per population",
            confidence="high",
        )
        add_tags(conn, risk_id, ["accident", "asphyxia"])
        n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"choking: ingested {ingest(conn)} entries.")
