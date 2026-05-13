"""Outdoor recreation: surfing, shark attacks, ATV, hunting, boating.

Sources:
- ISAF (Florida Museum) — shark attack statistics.
- CDC / CPSC — ATV / OHV fatality data.
- US Coast Guard — Recreational Boating Statistics 2024.
- IHEA / CDC — hunting injury / fatality estimates.
"""
from __future__ import annotations

import datetime as dt

from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCES = {
    "isaf": dict(
        name="ISAF — International Shark Attack File",
        url="https://www.floridamuseum.ufl.edu/shark-attacks/yearly-worldwide-summary/",
        publisher="Florida Museum of Natural History",
    ),
    "cpsc_atv": dict(
        name="CPSC — Off-Highway Vehicle Annual Report 2022",
        url="https://www.cpsc.gov/s3fs-public/OHV-Annual-Report-2022.pdf",
        publisher="US Consumer Product Safety Commission",
    ),
    "uscg_boat": dict(
        name="USCG — Recreational Boating Statistics 2024",
        url="https://www.uscgboating.org/library/accident-statistics/Recreational-Boating-Statistics-2024.pdf",
        publisher="US Coast Guard",
    ),
    "ihea": dict(
        name="IHEA / NSC — Hunting incident statistics",
        url="https://ihea-usa.org/",
        publisher="International Hunter Education Association",
    ),
}
US_POP = 334_900_000

ROWS = [
    ("isaf", "shark-attack-us-year",
     "Shark fatal attack (US, per resident per year)",
     1_000_000 * 0.5 / US_POP, "per_year",
     "~1 US fatality per 2 years across whole population.",
     ("animal", "ocean")),
    ("isaf", "shark-surfer-lifetime",
     "Shark fatal attack (US surfer, lifetime)",
     1_000_000 / 25_641, "lifetime",
     "~1 in 25,641 lifetime risk for an American surfer.",
     ("animal", "ocean", "surfing")),
    ("cpsc_atv", "atv-us-year",
     "ATV / off-highway vehicle (per US resident per year)",
     1_000_000 * 800 / US_POP, "per_year",
     "~800 annual OHV deaths, ~2/3 ATV.",
     ("vehicle", "off-road")),
    ("cpsc_atv", "atv-male-us-year",
     "ATV / OHV fatality (US male per year)",
     1_000_000 * 0.55 / 100_000, "per_year",
     "0.55/100k for males (~6× female rate).",
     ("vehicle", "off-road", "demographic")),
    ("uscg_boat", "boating-per-registered-2024",
     "Recreational boating (per registered boat-year, 2024)",
     1_000_000 * 4.8 / 100_000, "per_year",
     "4.8 deaths per 100k registered vessels; 76% drowning.",
     ("water", "boating")),
    ("ihea", "hunting-us-year",
     "Hunting incident fatality (US, per hunter per year)",
     1_000_000 * 100 / 15_000_000, "per_year",
     "~100 hunting deaths/yr / ~15M active US hunters.",
     ("hunting", "firearms")),
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
                slug=f"rec:{slug}",
                name=name,
                category="activity",
                micromorts=mm,
                exposure=exposure,
                exposure_detail=note,
                region="US",
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
    print(f"outdoor recreation: ingested {ingest(conn)} entries.")
