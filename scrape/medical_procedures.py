"""Common medical procedures — per-procedure micromorts.

Sources:
- Colonoscopy: pooled 0.074 deaths/1,000 patients (~30 µmt). Reichert &
  ASGE estimates.
- Living kidney donor nephrectomy: 3.1 per 10,000 perioperative deaths
  (Segev et al., JAMA 2010 — long-standing benchmark, ≈ 30 µmt).
- General anaesthesia (modern, healthy patient): 5 µmt (already in seed).
- Endoscopy: ~1/16,000 mortality (≈ 60 µmt) — Sherwinter review.
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_deaths_per
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCES = {
    "colon": dict(
        name="Reichert et al. 2020 — Colonoscopy mortality",
        url="https://www.cghjournal.org/article/S1542-3565(20)31076-4/fulltext",
        publisher="Clinical Gastroenterology and Hepatology",
    ),
    "kidney": dict(
        name="Segev et al. 2010 — Perioperative live kidney donor mortality",
        url="https://jamanetwork.com/journals/jama/fullarticle/185508",
        publisher="JAMA",
    ),
    "endoscopy": dict(
        name="ASGE / Sherwinter — Endoscopy adverse events",
        url="https://www.asge.org/home/resources/key-resources/quality-and-safety",
        publisher="American Society for Gastrointestinal Endoscopy",
    ),
}

ROWS = [
    ("colon",     "colonoscopy",                  "Colonoscopy",                                   0.074, 1_000,
     ("medical", "screening"), "Pooled mortality ≈ 0.074/1,000 patients."),
    ("kidney",    "live-kidney-donor",            "Live kidney donor nephrectomy",                 3.1,   10_000,
     ("medical", "surgery", "donor"), "Perioperative mortality, both sexes pooled."),
    ("kidney",    "live-kidney-donor-male",       "Live kidney donor nephrectomy (male)",          5.1,   10_000,
     ("medical", "surgery", "donor", "demographic"), "Male donor perioperative mortality."),
    ("kidney",    "live-kidney-donor-female",     "Live kidney donor nephrectomy (female)",        1.7,   10_000,
     ("medical", "surgery", "donor", "demographic"), "Female donor perioperative mortality."),
    ("kidney",    "live-kidney-donor-hypertensive","Live kidney donor (hypertensive)",             36.7,  10_000,
     ("medical", "surgery", "donor", "demographic"), "Perioperative mortality with hypertension."),
    ("endoscopy", "upper-endoscopy",              "Upper GI endoscopy (diagnostic)",               1,     16_000,
     ("medical", "screening"), "≈ 1/16,000 mortality across published cohorts."),
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
        for src_key, slug, name, deaths, per_n, tags, note in ROWS:
            risk_id = upsert_risk(
                conn,
                slug=f"med:{slug}",
                name=name,
                category="medical",
                micromorts=from_deaths_per(deaths, per_n),
                exposure="per_event",
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
    print(f"medical procedures: ingested {ingest(conn)} entries.")
