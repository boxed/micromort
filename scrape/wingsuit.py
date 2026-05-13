"""Wingsuit BASE jumping — among the most lethal sports per attempt.

Source: Mei-Dan et al. 2013, 'Fatalities in Wingsuit BASE Jumping',
plus contemporary reporting estimating ~1 death per 50-100 jumps.
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_deaths_per
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCE = dict(
    name="Mei-Dan et al. 2013 — Fatalities in Wingsuit BASE Jumping",
    url="https://pubmed.ncbi.nlm.nih.gov/24238216/",
    publisher="Wilderness & Environmental Medicine",
)

ROWS = [
    ("wingsuit-base-optimistic",
     "Wingsuit BASE jump (lower bound)",
     1, 100, "Optimistic estimate."),
    ("wingsuit-base-typical",
     "Wingsuit BASE jump (mid range)",
     1, 75, "Mid-range commonly cited figure."),
    ("wingsuit-base-pessimistic",
     "Wingsuit BASE jump (upper bound)",
     1, 50, "Pessimistic estimate matching recent fatality clusters."),
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
                slug=f"wingsuit:{suffix}",
                name=name,
                category="parachute",
                micromorts=from_deaths_per(deaths, per_n),
                exposure="per_jump",
                exposure_detail=note,
                source_id=source_id,
                original_value=f"{deaths} in {per_n} jumps",
                original_unit="per jump",
                confidence="low",
                notes="Wide uncertainty range; pick the figure that matches your prior.",
            )
            add_tags(conn, risk_id, ["aviation", "extreme-sports", "wingsuit"])
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"wingsuit: ingested {ingest(conn)} entries.")
