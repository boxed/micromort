"""Miscellaneous medical procedures + IVF.

Sources:
- ASRM 2023 — IVF usage in the US.
- Aarts et al. — IVF/ICSI vs spontaneous stillbirth risk.
- AAFP — common surgical mortality summaries.
- AAO — LASIK complications (mortality essentially nil).
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_deaths_per
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCES = {
    "ivf_stillbirth": dict(
        name="Aarts et al. 2010 — IVF/ICSI stillbirth risk",
        url="https://pubmed.ncbi.nlm.nih.gov/20179321/",
        publisher="Human Reproduction",
    ),
    "aafp_surgery": dict(
        name="AAFP / NSQIP — Common surgical procedure mortality rates",
        url="https://www.aafp.org/",
        publisher="American Academy of Family Physicians",
    ),
    "aao_lasik": dict(
        name="American Academy of Ophthalmology — LASIK facts",
        url="https://www.aao.org/eye-health/treatments/facts-about-lasik-complications",
        publisher="American Academy of Ophthalmology",
    ),
}

ROWS = [
    # source, slug, name, deaths, per_n, exposure, tags, note
    ("ivf_stillbirth", "ivf-stillbirth",
     "Stillbirth following IVF/ICSI (per pregnancy)",
     16.2, 1_000, "per_event",
     ("pregnancy", "ivf"),
     "16.2 stillbirths per 1,000 IVF/ICSI pregnancies."),
    ("ivf_stillbirth", "stillbirth-spontaneous",
     "Stillbirth after spontaneous conception (per pregnancy)",
     3.7, 1_000, "per_event",
     ("pregnancy",),
     "3.7 stillbirths per 1,000 fertile-women pregnancies — ~4× lower than IVF."),
    ("aafp_surgery", "hip-replacement",
     "Total hip replacement (per surgery, 30-day mortality)",
     5, 10_000, "per_event",
     ("surgery", "orthopedic"),
     "30-day mortality ≈ 0.05% in modern cohorts."),
    ("aafp_surgery", "knee-replacement",
     "Total knee replacement (per surgery, 30-day mortality)",
     2, 10_000, "per_event",
     ("surgery", "orthopedic"),
     "30-day mortality ≈ 0.02% in modern cohorts."),
    ("aafp_surgery", "vasectomy",
     "Vasectomy (per procedure)",
     1, 1_000_000, "per_event",
     ("surgery", "outpatient"),
     "Mortality ≈ 1/1,000,000 — essentially zero."),
    ("aafp_surgery", "hysterectomy",
     "Hysterectomy (per surgery, 30-day mortality)",
     8, 10_000, "per_event",
     ("surgery", "gynecologic"),
     "30-day mortality ≈ 0.08%, varies by indication."),
    ("aafp_surgery", "tonsillectomy",
     "Tonsillectomy (per procedure)",
     1, 30_000, "per_event",
     ("surgery", "pediatric"),
     "≈ 1 death per 30,000 procedures."),
    ("aao_lasik", "lasik",
     "LASIK eye surgery (per procedure)",
     1, 5_000_000, "per_event",
     ("surgery", "elective"),
     "Sight-threatening complications rare; mortality vanishingly small."),
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
                slug=f"medm:{slug}",
                name=name,
                category="medical",
                micromorts=from_deaths_per(deaths, per_n),
                exposure=exposure,
                exposure_detail=note,
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
    print(f"medical_misc: ingested {ingest(conn)} entries.")
