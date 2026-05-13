"""More environmental hazards: carbon monoxide, wildfire smoke, drunk-driving traffic.

Sources:
- CDC MMWR — Carbon monoxide poisoning deaths, 1999-2021.
- Lancet Planetary Health 2021 — Wildfire-related PM2.5 mortality.
- Science Advances 2024 — California wildfire PM2.5 attributable deaths.
- NHTSA — Alcohol-impaired-driving fatalities 2023.
"""
from __future__ import annotations

import datetime as dt

from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCES = {
    "cdc_co": dict(
        name="CDC MMWR — Carbon-monoxide poisoning deaths (US)",
        url="https://www.cdc.gov/mmwr/volumes/66/wr/mm6608a9.htm",
        publisher="US CDC MMWR",
    ),
    "wildfire_pm25": dict(
        name="Science Advances 2024 — California wildfire PM2.5 mortality",
        url="https://www.science.org/doi/10.1126/sciadv.adl1252",
        publisher="Science Advances",
    ),
    "nhtsa_dui": dict(
        name="NHTSA — Alcohol-Impaired Driving 2023 Data (Pub. 813713)",
        url="https://crashstats.nhtsa.dot.gov/Api/Public/Publication/813713",
        publisher="US DOT NHTSA",
    ),
}
US_POP = 334_900_000

ROWS = [
    # source, slug, name, deaths_per_year_us, exposure, tags, note
    ("cdc_co", "co-accidental-us",
     "Carbon-monoxide poisoning (US, accidental, per resident-year)",
     1_000_000 * 438 / US_POP, "per_year",
     ("poisoning", "home", "accident"),
     "≈438 unintentional CO deaths/year; 54% in homes."),
    ("cdc_co", "co-male-65plus",
     "Carbon-monoxide poisoning (US men age 65+, per year)",
     1_000_000 * 0.42 / 100_000, "per_year",
     ("poisoning", "home", "elderly", "demographic"),
     "0.42/100k — highest US sub-group."),
    ("wildfire_pm25", "wildfire-pm25-california-year",
     "Wildfire smoke PM2.5 (California average, per resident-year)",
     1_000_000 * (52_480 / 11) / 39_000_000, "per_year",
     ("air-quality", "wildfire"),
     "≈52,480 attributable deaths 2008-2018 ÷ 11 yrs ÷ CA pop."),
    ("wildfire_pm25", "wildfire-pm25-us-year",
     "Wildfire smoke PM2.5 (US average, per resident-year)",
     1_000_000 * 24_100 / US_POP, "per_year",
     ("air-quality", "wildfire"),
     "≈24,100 US deaths/yr attributable to wildfire PM2.5."),
    ("nhtsa_dui", "dui-fatal-us-mile",
     "Alcohol-impaired driving (per VMT, US, 2023)",
     0.0038, "per_mile",
     ("driving", "alcohol"),
     "0.38 fatalities per 100 million VMT in alcohol-impaired crashes."),
    ("nhtsa_dui", "dui-fatal-us-year",
     "Alcohol-impaired-driving fatality (US, per resident-year)",
     1_000_000 * 11_904 / US_POP, "per_year",
     ("driving", "alcohol", "baseline"),
     "11,904 drunk-driving deaths in 2024."),
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
        for src_key, slug, name, mm, exposure, tags, note in ROWS:
            category = "transport" if "driving" in tags else "environmental"
            risk_id = upsert_risk(
                conn,
                slug=f"envm:{slug}",
                name=name,
                category=category,
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
    print(f"environmental_more: ingested {ingest(conn)} entries.")
