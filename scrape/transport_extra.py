"""Extra transport modes: micromobility, cruise ships, ferries.

Sources:
- CPSC Micromobility Products Report 2017-2022.
- AJPH 2024 — burden of injury from e-bike / e-scooter / hoverboard.
- CDC / IJTMGH passenger mortality on cruise ships.
- Statista ferry fatalities by region (1966-2017 cumulative totals).
"""
from __future__ import annotations

import datetime as dt

from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCES = {
    "cpsc_micro": dict(
        name="CPSC Micromobility Products-Related Deaths/Injuries (2017-2022)",
        url="https://www.cpsc.gov/s3fs-public/Micromobility-Products-Related-Deaths-Injuries-and-Hazard-Patterns-2017-2022.pdf",
        publisher="US Consumer Product Safety Commission",
    ),
    "cruise_ijt": dict(
        name="Death at Sea — Passenger and Crew Mortality on Cruise Ships",
        url="https://www.ijtmgh.com/article_119591.html",
        publisher="International Journal of Travel Medicine & Global Health",
    ),
    "ferry_statista": dict(
        name="Statista — Ferry fatalities by region (1966-2017)",
        url="https://www.statista.com/statistics/1250799/ferry-fatalities-by-region/",
        publisher="Statista / IMO",
    ),
}
US_POP = 334_900_000

ROWS = [
    # micromobility — convert 6-yr cumulative deaths to annual µmt/yr
    ("cpsc_micro", "e-scooter-us-year",
     "E-scooter fatality (US, per resident per year)",
     1_000_000 * (111 / 6) / US_POP, "per_year",
     "111 e-scooter deaths over 6 yrs (CPSC 2017-22).",
     ("micromobility", "scooter")),
    ("cpsc_micro", "e-bike-us-year",
     "E-bike fatality (US, per resident per year)",
     1_000_000 * (104 / 6) / US_POP, "per_year",
     "104 e-bike deaths over 6 yrs (CPSC 2017-22).",
     ("micromobility", "bicycle")),

    # cruise — 1 death per 150k guests (incl. natural causes onboard)
    ("cruise_ijt", "cruise-passenger",
     "Cruise ship voyage (per guest, all causes)",
     1_000_000 / 150_000, "per_event",
     "1 death per 150,000 guests; mostly age-related natural causes.",
     ("water", "cruise")),

    # ferry — historic cumulative (per resident-year of those countries)
    ("ferry_statista", "ferry-bangladesh-history",
     "Ferry fatality (Bangladesh, 1966-2017 cumulative per population)",
     1_000_000 * (9_886 / 51) / 165_000_000, "per_year",
     "9,886 cumulative ferry deaths over 51 years; modern population.",
     ("water", "ferry", "developing")),
    ("ferry_statista", "ferry-indonesia-history",
     "Ferry fatality (Indonesia, 1966-2017 cumulative per population)",
     1_000_000 * (6_480 / 51) / 273_000_000, "per_year",
     "6,480 cumulative ferry deaths over 51 years; modern population.",
     ("water", "ferry", "developing")),
]


def _touch(url: str) -> bool:
    try:
        fetch(url)
        return True
    except Exception:
        return False


def ingest(conn) -> int:
    today = dt.date.today().isoformat()
    src_ids: dict[str, int] = {}
    for k, meta in SOURCES.items():
        alive = _touch(meta["url"])
        src_ids[k] = upsert_source(
            conn,
            accessed_at=today if alive else None,
            **meta,
        )
    n = 0
    with transaction(conn):
        for src_key, slug, name, mm, exposure, note, tags in ROWS:
            risk_id = upsert_risk(
                conn,
                slug=f"trans:{slug}",
                name=name,
                category="transport",
                micromorts=mm,
                exposure=exposure,
                exposure_detail=note,
                source_id=src_ids[src_key],
                original_value=note,
                original_unit=exposure,
                confidence="medium",
            )
            add_tags(conn, risk_id, list(tags))
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"transport_extra: ingested {ingest(conn)} entries.")
