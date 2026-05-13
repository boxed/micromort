"""Endurance-sport mortality — Ironman, triathlon, ultramarathon.

Sources:
- Harris et al. 2017 (Annals of Internal Medicine) — Triathlon US case
  series 1985-2016.
- TrainingPeaks / triathlon SCD rate.
- Ironman aggregate analyses.
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_deaths_per
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCES = {
    "harris_2017": dict(
        name="Harris et al. 2017 — Death & cardiac arrest in US triathlon",
        url="https://www.acpjournals.org/doi/10.7326/M17-0847",
        publisher="Annals of Internal Medicine",
    ),
    "trainingpeaks": dict(
        name="TrainingPeaks — Athlete deaths in triathlon (review)",
        url="https://www.trainingpeaks.com/coach-blog/athlete-deaths-in-triathlon-and-how-to-prevent-them/",
        publisher="TrainingPeaks / endurance coaches",
    ),
}

ROWS = [
    # source, slug, name, deaths, per_n, exposure, tags, note
    ("trainingpeaks", "triathlon-scd",
     "Triathlon (sudden cardiac death, per participant)",
     1.7, 100_000, "per_event",
     ("endurance", "triathlon"),
     "1.7 SCDs per 100k participants; vast majority during swim segment."),
    ("trainingpeaks", "triathlon-overall",
     "Triathlon (any death, per finisher)",
     1, 76_000, "per_event",
     ("endurance", "triathlon"),
     "Recent finisher-mortality estimate: 1 in 76,000."),
    ("trainingpeaks", "ironman-no-swim",
     "Ironman bike+run only (per finisher)",
     6, 100_000, "per_event",
     ("endurance", "triathlon"),
     "Removing swim drops Ironman risk to ~6 per 100k — comparable to ultramarathon."),
    ("trainingpeaks", "ultramarathon",
     "Ultramarathon (per finisher, average)",
     6, 100_000, "per_event",
     ("endurance", "running"),
     "Comparable to Ironman without swim, when no mass-casualty events."),
    ("harris_2017", "triathlon-swim-segment",
     "Triathlon swim segment (per swim entrant)",
     1, 33_000, "per_event",
     ("endurance", "triathlon", "swim"),
     "Most triathlon deaths occur within first minutes of swim entry."),
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
                slug=f"end:{slug}",
                name=name,
                category="activity",
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
    print(f"endurance_sports: ingested {ingest(conn)} entries.")
