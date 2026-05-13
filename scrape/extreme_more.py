"""More extreme-sport / adventure-recreation per-participant risks.

Sources:
- Hardclimbs / AAC accident reports — free solo deaths.
- Statistics Canada — snowmobile fatalities (Canada).
- US snowmobile fatalities (~200 annual NA average).
- Mei-Dan et al. — bungee-jumping risk profile (very low fatal).
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_deaths_per
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCES = {
    "hardclimbs": dict(
        name="HardClimbs.info / AAC — Free solo death statistics",
        url="https://hardclimbs.info/free-solo-deaths/",
        publisher="American Alpine Club / Climbing magazine",
    ),
    "statcan_snowmobile": dict(
        name="Statistics Canada — Snowmobile fatalities 2013-2019",
        url="https://www150.statcan.gc.ca/n1/daily-quotidien/210122/dq210122d-eng.htm",
        publisher="Statistics Canada",
    ),
    "ridesafe": dict(
        name="RideSafe / BRP — North American snowmobile fatality figures",
        url="https://ridesafefoundation.org/snowmobiling-deaths-see-increase-in-2023/",
        publisher="RideSafe Foundation",
    ),
    "mei_dan_bungee": dict(
        name="Mei-Dan et al. — Bungee, BASE & skydiving injury epidemiology",
        url="https://pubmed.ncbi.nlm.nih.gov/22824842/",
        publisher="Wilderness & Environmental Medicine",
    ),
}
US_POP = 334_900_000
CANADA_POP = 40_000_000

ROWS = [
    ("hardclimbs", "free-solo-climb",
     "Free solo rock climb (per attempt)",
     1, 2_000, "per_climb",
     ("climbing", "extreme-sports"),
     "Approx 1 fatal fall per 2,000 free-solo attempts."),
    ("statcan_snowmobile", "snowmobile-canada",
     "Snowmobile (per Canadian resident-year)",
     73, CANADA_POP, "per_year",
     ("vehicle", "snow"),
     "73 deaths/yr in Canada (2013-19), per resident."),
    ("ridesafe", "snowmobile-us",
     "Snowmobile (per US resident-year)",
     127, US_POP, "per_year",
     ("vehicle", "snow"),
     "~127 US snowmobile deaths/year (200 NA total minus ~73 Canada)."),
    ("mei_dan_bungee", "bungee-jump",
     "Bungee jump (per jump)",
     1, 500_000, "per_jump",
     ("extreme-sports", "elastic"),
     "Very rare; pooled estimate ≈ 1 fatality per 500,000 jumps."),
    ("hardclimbs", "mountain-bike-park-day",
     "Mountain biking (per visit, lift-served bike park)",
     1, 200_000, "per_event",
     ("cycling", "extreme-sports"),
     "Rough estimate from US bike-park incident reports."),
    ("hardclimbs", "free-diving",
     "Free diving (per dive, advanced/competition)",
     1, 50_000, "per_dive",
     ("water", "extreme-sports", "free-diving"),
     "Higher-end estimate for breath-hold competitive dives."),
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
        for src_key, slug, name, deaths, per_n, exposure, tags, note in ROWS:
            risk_id = upsert_risk(
                conn,
                slug=f"xtr:{slug}",
                name=name,
                category="parachute" if "elastic" in tags else "activity",
                micromorts=from_deaths_per(deaths, per_n),
                exposure=exposure,
                exposure_detail=note,
                source_id=src_ids[src_key],
                original_value=f"{deaths} / {per_n:,}",
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
    print(f"extreme_more: ingested {ingest(conn)} entries.")
