"""Marathon-running cardiac arrest & death — per finisher.

Source: RACER cohort (Kim et al.), updated to 2010-2023 analysis showing
0.60 cardiac arrests / 100k runners and 0.20 deaths / 100k runners.
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_deaths_per
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCE = dict(
    name="RACER study + 2025 update — Marathon cardiac arrests",
    url="https://www.tctmd.com/news/racer-no-change-cardiac-arrests-during-marathons-survival",
    publisher="Kim et al. (NEJM / TCTMD coverage)",
)

ROWS = [
    ("marathon-scd-2010-23",  "Marathon: sudden cardiac death (2010-23)",  0.20, 100_000,
     "Death rate per 100k finishers, 2010-2023."),
    ("marathon-sca-2010-23",  "Marathon: sudden cardiac arrest (2010-23)", 0.60, 100_000,
     "Cardiac-arrest rate (some survive)."),
    ("marathon-scd-historic", "Marathon: sudden cardiac death (pre-2000)", 1, 50_000,
     "Older estimate, 1 in 50,000 finishers."),
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
        for suffix, name, deaths, per_n, note in ROWS:
            risk_id = upsert_risk(
                conn,
                slug=f"cardiac:{suffix}",
                name=name,
                category="activity",
                micromorts=from_deaths_per(deaths, per_n),
                exposure="per_event",
                exposure_detail=note,
                source_id=source_id,
                original_value=f"{deaths}/{per_n:,}",
                original_unit="per marathon finish",
                confidence="medium",
            )
            add_tags(conn, risk_id, ["running", "endurance", "cardiac"])
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"cardiac: ingested {ingest(conn)} entries.")
