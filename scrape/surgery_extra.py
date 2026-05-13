"""Common surgical procedures — per-operation micromorts.

Sources are cited per-row; figures are 30-day perioperative mortality for
otherwise-healthy adult populations unless noted.
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_deaths_per
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCES = {
    "sts_cabg": dict(
        name="STS Adult Cardiac Surgery Database (2023 update)",
        url="https://www.annalsthoracicsurgery.org/article/S0003-4975(23)01219-5/fulltext",
        publisher="Society of Thoracic Surgeons",
    ),
    "bbl_2022": dict(
        name="Cansancao et al. 2022 — BBL Mortality, South Florida",
        url="https://pmc.ncbi.nlm.nih.gov/articles/PMC9896146/",
        publisher="Aesthetic Surgery Journal",
    ),
    "asps_cosmetic": dict(
        name="American Society of Plastic Surgeons — Cosmetic Surgery Safety",
        url="https://www.plasticsurgery.org/news/press-releases/plastic-surgery-societies-issue-urgent-warning-about-the-risks-associated-with-brazilian-butt-lifts",
        publisher="ASPS",
    ),
    "columbia_appy": dict(
        name="Columbia Surgery — Appendicitis & Appendectomy",
        url="https://columbiasurgery.org/conditions-and-treatments/appendicitis",
        publisher="Columbia University",
    ),
    "njem_chole": dict(
        name="NEJM — Cholecystectomy outcomes (Maryland cohort)",
        url="https://www.nejm.org/doi/full/10.1056/NEJM199402103300607",
        publisher="New England Journal of Medicine",
    ),
}

# (source_key, slug, name, deaths, per_n, year, tags, note)
ROWS = [
    ("sts_cabg",
     "cabg-isolated", "Coronary artery bypass graft (isolated CABG)",
     2.5, 100, 2021,
     ("cardiac", "surgery"),
     "STS isolated CABG 30-day op mortality, 2021."),
    ("bbl_2022",
     "bbl-current", "Brazilian Butt Lift (current technique)",
     1, 14_900, 2022,
     ("cosmetic", "surgery"),
     "Per-procedure mortality after recent technique changes."),
    ("bbl_2022",
     "bbl-historic", "Brazilian Butt Lift (older technique)",
     1, 3_000, 2017,
     ("cosmetic", "surgery", "historical"),
     "Historic per-procedure mortality before deep-injection ban."),
    ("asps_cosmetic",
     "liposuction-low", "Liposuction (low-end estimate)",
     2.6, 100_000, 2020,
     ("cosmetic", "surgery"),
     "Reported lower-bound mortality across cohorts."),
    ("asps_cosmetic",
     "liposuction-high", "Liposuction (high-end estimate)",
     20.6, 100_000, 2020,
     ("cosmetic", "surgery"),
     "Reported upper-bound mortality across cohorts."),
    ("columbia_appy",
     "appendectomy", "Appendectomy",
     0.5, 100, 2020,
     ("surgery", "emergency"),
     "Mortality across all patients (range 0.2-0.8%)."),
    ("njem_chole",
     "cholecystectomy", "Cholecystectomy (gallbladder removal)",
     0.5, 1_000, 1994,
     ("surgery",),
     "30-day perioperative mortality, mixed laparoscopic/open."),
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
        for src_key, slug, name, deaths, per_n, year, tags, note in ROWS:
            risk_id = upsert_risk(
                conn,
                slug=f"surg:{slug}",
                name=name,
                category="medical",
                micromorts=from_deaths_per(deaths, per_n),
                exposure="per_event",
                exposure_detail=note,
                year=year,
                source_id=src_ids[src_key],
                original_value=f"{deaths}/{per_n:,}",
                original_unit="deaths per procedure",
                confidence="medium",
            )
            add_tags(conn, risk_id, list(tags))
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"surgery_extra: ingested {ingest(conn)} entries.")
