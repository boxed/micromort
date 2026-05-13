"""Human spaceflight fatality rates.

Sources:
- All-time aggregated fatality rate: 19 deaths / 791 person-flights (2.4%).
- Space Shuttle 1980s era: 3.1% per mission (Challenger).
- Space Shuttle 2000s era: 2.8% per mission (Columbia).
- Per-mission rates for the Space Shuttle programme (2 catastrophic
  losses / 135 missions = 14,815 µmt per launch on a per-vehicle basis).
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_deaths_per
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCE = dict(
    name="Wikipedia — List of spaceflight-related accidents and incidents",
    url="https://en.wikipedia.org/wiki/List_of_spaceflight-related_accidents_and_incidents",
    publisher="Wikipedia",
)

ROWS = [
    ("spaceflight-all-time",
     "Crewed spaceflight (all-time per-person)",
     19, 791, "per_event",
     "1961-2024: 19 in-flight deaths / 791 distinct astronauts who reached space",
     ("space", "aviation", "historical")),
    ("space-shuttle-vehicle",
     "Space Shuttle launch (per vehicle, 1981-2011)",
     2, 135, "per_event",
     "2 catastrophic losses (Challenger 1986, Columbia 2003) over 135 flights.",
     ("space", "aviation", "historical")),
    ("space-shuttle-crew-1980s",
     "Space Shuttle crew (1980s era, per-person)",
     0.031, 1, "per_event",
     "Per-person fatality rate, Shuttle 1980s era (Challenger).",
     ("space", "aviation", "historical")),
    ("space-shuttle-crew-2000s",
     "Space Shuttle crew (2000s era, per-person)",
     0.028, 1, "per_event",
     "Per-person fatality rate, Shuttle 2000s era (Columbia).",
     ("space", "aviation", "historical")),
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
        for suffix, name, deaths, per_n, exposure, note, tags in ROWS:
            mm = from_deaths_per(deaths, per_n) if per_n != 1 else deaths * 1_000_000
            risk_id = upsert_risk(
                conn,
                slug=f"space:{suffix}",
                name=name,
                category="space",
                micromorts=mm,
                exposure=exposure,
                exposure_detail=note,
                source_id=source_id,
                original_value=(
                    f"{deaths}/{per_n:,}" if per_n != 1 else f"{deaths*100:.1f}%/mission"
                ),
                original_unit="deaths per mission/person",
                confidence="medium",
            )
            add_tags(conn, risk_id, list(tags))
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"spaceflight: ingested {ingest(conn)} entries.")
