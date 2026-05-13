"""Acute cardiac & cerebrovascular events — per-event mortality.

Sources:
- AHA — CPR / OHCA facts and stats.
- CMS / Stroke 30-day mortality reports.
- CARES registry.
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_probability
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCES = {
    "aha_cpr": dict(
        name="AHA — CPR facts & stats / OHCA outcomes",
        url="https://cpr.heart.org/en/resources/cpr-facts-and-stats",
        publisher="American Heart Association",
    ),
    "stroke_30d": dict(
        name="Stroke 30-day case-fatality (multiple cohorts)",
        url="https://www.ahajournals.org/doi/10.1161/strokeaha.107.510362",
        publisher="Stroke (AHA Journal)",
    ),
}

ROWS = [
    # source, slug, name, mortality probability, exposure, tags, note
    ("aha_cpr", "ohca-overall",
     "Out-of-hospital cardiac arrest (per event, US)",
     0.90, "per_event",
     ("cardiac", "ohca"),
     "≈90% mortality before hospital discharge from OHCA."),
    ("aha_cpr", "ohca-witnessed",
     "OHCA, bystander-witnessed (per event)",
     0.84, "per_event",
     ("cardiac", "ohca"),
     "16% survival if a bystander witnesses the arrest."),
    ("aha_cpr", "ohca-unwitnessed",
     "OHCA, unwitnessed (per event)",
     0.955, "per_event",
     ("cardiac", "ohca"),
     "4.5% survival if the arrest is unwitnessed."),
    ("stroke_30d", "stroke-ischemic-30d",
     "Ischemic stroke 30-day mortality (per event)",
     0.126, "per_event",
     ("stroke",),
     "Pooled 30-day case-fatality ≈ 12.6%."),
    ("stroke_30d", "stroke-65-74-30d",
     "Stroke 30-day mortality, age 65-74 (per event)",
     0.09, "per_event",
     ("stroke", "demographic"),
     "9% 30-day mortality in 65-74 age band."),
    ("stroke_30d", "stroke-85plus-30d",
     "Stroke 30-day mortality, age 85+ (per event)",
     0.23, "per_event",
     ("stroke", "demographic"),
     "23% 30-day mortality in age 85+ band."),
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
        for src_key, slug, name, p, exposure, tags, note in ROWS:
            risk_id = upsert_risk(
                conn,
                slug=f"acute:{slug}",
                name=name,
                category="disease",
                micromorts=from_probability(p),
                exposure=exposure,
                exposure_detail=note,
                source_id=src_ids[src_key],
                original_value=f"{p*100:.1f}% mortality",
                original_unit="case-fatality probability",
                confidence="high",
            )
            add_tags(conn, risk_id, list(tags))
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"cardiac_events_extra: ingested {ingest(conn)} entries.")
