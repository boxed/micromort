"""More human-spaceflight risks: vehicle programs + in-orbit radiation.

Sources:
- Wikipedia: 'List of spaceflight-related accidents and incidents'.
- NASA OCHMO-TB-020 — Ionizing radiation protection (ISS exposures).
- Cucinotta et al. — astronaut cancer-mortality framework.
- PLOS One 2013 — Radiation risk for a Mars mission.
- IAA / SpaceX / NASA / Roscosmos mission counts.

Radiation → micromorts uses the BEIR VII population coefficient of 5 %/Sv
for fatal cancer (50 µmt per mSv), the same factor used in the medical
imaging scraper. This is a population average; astronauts are healthier
than average so the actual personal risk may be modestly lower.
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_deaths_per
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCES = {
    "wiki_accidents": dict(
        name="Wikipedia — List of spaceflight-related accidents and incidents",
        url="https://en.wikipedia.org/wiki/List_of_spaceflight-related_accidents_and_incidents",
        publisher="Wikipedia",
    ),
    "nasa_radiation": dict(
        name="NASA OCHMO-TB-020 — Ionizing-Radiation Protection",
        url="https://www.nasa.gov/wp-content/uploads/2023/03/radiation-protection-technical-brief-ochmo.pdf",
        publisher="NASA Office of the Chief Health and Medical Officer",
    ),
    "plos_mars": dict(
        name="Cucinotta et al. 2013 — Radiation risk for a Mars mission",
        url="https://pmc.ncbi.nlm.nih.gov/articles/PMC3797711/",
        publisher="PLOS One",
    ),
    "iaa_60yrs": dict(
        name="MDPI 2022 — Sixty Years of Manned Spaceflight",
        url="https://www.mdpi.com/2226-4310/9/11/675",
        publisher="MDPI Aerospace",
    ),
}
MM_PER_MSV = 50.0  # BEIR VII low-dose fatal-cancer mortality

# -----------------------------------------------------------------------------
# Per-mission program rates (per crew member per launch unless noted)
# -----------------------------------------------------------------------------
PROGRAM_ROWS = [
    # source_key, slug, name, deaths, crew_slots, year, tags, note
    ("wiki_accidents", "soyuz-program",
     "Soyuz programme (per crew slot, all-time)",
     4, 290, 2024,
     ("space", "soyuz", "historical"),
     "4 cosmonauts lost (Soyuz 1, Soyuz 11) over ~290 crewed slots since 1967."),
    ("wiki_accidents", "soyuz-modern",
     "Soyuz programme (per crew slot, post-1971, upper 95% bound)",
     0, 220, 2024,
     ("space", "soyuz", "upper-bound"),
     "Zero in-flight fatalities since 1971 over ~220 crewed slots. Value shown is rule-of-three 95% upper bound (3/N), not a point estimate."),
    ("wiki_accidents", "apollo-program",
     "Apollo programme (per crew slot, incl. Apollo 1 fire)",
     3, 33, 1972,
     ("space", "apollo", "historical"),
     "11 crewed Apollo missions × 3 seats = 33 crew slots; 3 deaths in Apollo 1 ground test."),
    ("wiki_accidents", "mercury-gemini",
     "Mercury + Gemini (per crew slot, upper 95% bound)",
     0, 26, 1966,
     ("space", "mercury", "gemini", "historical", "upper-bound"),
     "6 Mercury + 10 Gemini crewed flights × avg seats = 26 slots; 0 fatalities. Value is rule-of-three 95% upper bound — the true rate could be anywhere from 0 up to this number."),
    ("wiki_accidents", "dragon-crew",
     "SpaceX Crew Dragon (per crew slot, upper 95% bound)",
     0, 60, 2024,
     ("space", "spacex", "upper-bound"),
     "Demo-2 + Crew-1…Crew-9 + commercial = roughly 60 crew slots, 0 fatalities. Value is rule-of-three 95% upper bound."),
    ("wiki_accidents", "virgin-galactic-pilot",
     "Virgin Galactic SpaceShipTwo (per pilot-flight)",
     1, 100, 2014,
     ("space", "virgin-galactic", "suborbital"),
     "Single in-flight pilot fatality (2014) over ≈100 test pilot-flights; passenger flights distinct."),
    ("wiki_accidents", "blue-origin-new-shepard",
     "Blue Origin New Shepard (per crew slot, upper 95% bound)",
     0, 60, 2024,
     ("space", "blue-origin", "suborbital", "upper-bound"),
     "No fatalities to date over ~10 crewed flights × 6 seats. Value is rule-of-three 95% upper bound."),
]


# -----------------------------------------------------------------------------
# Radiation exposure (cancer-mortality risk only — does not include
# launch/landing risk, which is captured separately above)
# -----------------------------------------------------------------------------
RAD_ROWS = [
    # slug, name, mSv equivalent dose, exposure, source_key, tags, note
    ("iss-1-day",      "ISS — 1 day on orbit (radiation)",         0.5, "per_day",
     "nasa_radiation", ("space", "iss", "radiation"),
     "Daily effective dose ≈ 0.5 mSv aboard the ISS."),
    ("iss-6mo-solar-max","ISS — 6-month mission (solar max)",       80, "per_event",
     "nasa_radiation", ("space", "iss", "radiation"),
     "Effective dose ≈ 80 mSv during solar maximum (lower GCR)."),
    ("iss-6mo-solar-min","ISS — 6-month mission (solar min)",      160, "per_event",
     "nasa_radiation", ("space", "iss", "radiation"),
     "Effective dose ≈ 160 mSv during solar minimum (higher GCR)."),
    ("lunar-1-year",   "Lunar surface — 1 year (radiation)",        110, "per_year",
     "plos_mars",     ("space", "moon", "radiation"),
     "Estimated 100-120 mGy / yr from GCR + secondaries."),
    ("mars-roundtrip-rad","Mars mission — 3-yr roundtrip (radiation only)", 375, "per_event",
     "plos_mars",     ("space", "mars", "radiation"),
     "Transit + surface stay total, midpoint of 300-450 mGy range. NASA REID estimates 3-10%."),
    ("mars-roundtrip-reid","Mars mission — total REID estimate (NASA central)", 1, "per_event",
     "plos_mars",     ("space", "mars", "radiation"),
     "NASA central REID 5%; upper-95% CI of order 10%."),
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
        # Program rows: per crew slot.
        for src_key, slug, name, deaths, slots, year, tags, note in PROGRAM_ROWS:
            if deaths == 0:
                # Rule of three: 95% upper bound for 0/N observations is 3/N.
                # We're explicit about this being an upper bound in the name + notes.
                mm = from_deaths_per(3, slots)
                orig = f"0 deaths / {slots} crew slots → rule-of-three upper bound 3/{slots}"
                confidence = "low"
            else:
                mm = from_deaths_per(deaths, slots)
                orig = f"{deaths} deaths / {slots} crew slots"
                confidence = "medium"

            risk_id = upsert_risk(
                conn,
                slug=f"space:{slug}",
                name=name,
                category="space",
                micromorts=mm,
                exposure="per_event",
                exposure_detail=note,
                year=year,
                source_id=src_ids[src_key],
                original_value=orig,
                original_unit="per crew slot",
                confidence=confidence,
            )
            add_tags(conn, risk_id, list(tags))
            n += 1

        # Radiation rows: convert mSv → µmt.
        for slug, name, dose_msv, exposure, src_key, tags, note in RAD_ROWS:
            if slug == "mars-roundtrip-reid":
                # Direct REID expression — 5% mortality.
                mm = 50_000
                orig = "5% REID (NASA central estimate)"
            else:
                mm = dose_msv * MM_PER_MSV
                orig = f"{dose_msv} mSv → ×{int(MM_PER_MSV)} µmt/mSv"

            risk_id = upsert_risk(
                conn,
                slug=f"space:{slug}",
                name=name,
                category="space",
                micromorts=mm,
                exposure=exposure,
                exposure_detail=note,
                source_id=src_ids[src_key],
                original_value=orig,
                original_unit="effective dose (mSv) / REID",
                confidence="medium",
                notes="Cancer-mortality contribution only; launch/landing risk separate.",
            )
            add_tags(conn, risk_id, list(tags))
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"space_extra: ingested {ingest(conn)} entries.")
