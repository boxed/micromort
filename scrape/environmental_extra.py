"""Environmental hazards: radon, ambient PM2.5 air pollution.

Sources:
- EPA — 'Health Risk of Radon' fact sheet.
- WHO — Ambient air pollution mortality.
- IHME GBD — PM2.5 attributable deaths 2021.
"""
from __future__ import annotations

import datetime as dt

from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCES = {
    "epa_radon": dict(
        name="US EPA — Health Risk of Radon",
        url="https://www.epa.gov/radon/health-risk-radon",
        publisher="US EPA",
    ),
    "who_air": dict(
        name="WHO — Ambient air pollution",
        url="https://www.who.int/news-room/fact-sheets/detail/ambient-(outdoor)-air-quality-and-health",
        publisher="World Health Organization",
    ),
    "gbd_pm25": dict(
        name="Lancet — GBD 2021 (PM2.5 attributable mortality)",
        url="https://pmc.ncbi.nlm.nih.gov/articles/PMC12041061/",
        publisher="Lancet / IHME",
    ),
}
WORLD_POP = 7_950_000_000

ROWS = [
    # (source, slug, name, micromorts, exposure, note, tags)
    ("epa_radon", "radon-home-4pci-population",
     "Radon at EPA action level (4 pCi/L, lifetime, population avg)",
     23_000, "lifetime",
     "2.3% lifetime lung-cancer risk at 4 pCi/L for general US population (EPA).",
     ("radon", "radiation", "lung-cancer")),
    ("epa_radon", "radon-home-4pci-smoker",
     "Radon at 4 pCi/L (lifetime, ever-smoker)",
     62_000, "lifetime",
     "6.2% lifetime lung-cancer risk for ever-smokers at 4 pCi/L.",
     ("radon", "radiation", "lung-cancer")),
    ("epa_radon", "radon-home-4pci-neversmoker",
     "Radon at 4 pCi/L (lifetime, never-smoker)",
     7_000, "lifetime",
     "0.7% lifetime lung-cancer risk for never-smokers at 4 pCi/L.",
     ("radon", "radiation", "lung-cancer")),
    ("gbd_pm25", "pm25-global-year",
     "Ambient PM2.5 air pollution (global, per resident-year)",
     1_000_000 * 7_830_000 / WORLD_POP, "per_year",
     "7.83 million deaths globally attributable to PM2.5 in 2021.",
     ("air-quality", "pollution")),
    ("gbd_pm25", "pm25-india-year",
     "Ambient PM2.5 air pollution (India, per resident-year)",
     1_000_000 * 1_700_000 / 1_400_000_000, "per_year",
     "~1.7M Indian deaths attributable to PM2.5 annually.",
     ("air-quality", "pollution")),
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
                slug=f"env:{slug}",
                name=name,
                category="environmental",
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
    print(f"environmental_extra: ingested {ingest(conn)} entries.")
