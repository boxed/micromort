"""Severe infections — per-episode mortality.

Sources:
- UKHSA — 30-day all-cause mortality after MRSA / MSSA / Gram-negative
  bacteraemia and C. difficile infections (2022-2023 report).
- StatPearls — MRSA case-fatality summaries.
- WHO Rabies Fact Sheet — 99%+ case fatality once symptoms appear.
- WHO/CDC — Tetanus case fatality.
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_probability
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCES = {
    "ukhsa": dict(
        name="UKHSA — 30-day all-cause mortality after MRSA/MSSA/C diff (2022-23)",
        url="https://www.gov.uk/government/statistics/mrsa-mssa-and-e-coli-bacteraemia-and-c-difficile-infection-30-day-all-cause-fatality",
        publisher="UK Health Security Agency",
    ),
    "who_rabies": dict(
        name="WHO — Rabies fact sheet",
        url="https://www.who.int/news-room/fact-sheets/detail/rabies",
        publisher="World Health Organization",
    ),
    "cdc_tetanus": dict(
        name="CDC Pink Book — Tetanus",
        url="https://www.cdc.gov/pinkbook/hcp/table-of-contents/chapter-21-tetanus.html",
        publisher="US CDC",
    ),
    "statpearls": dict(
        name="StatPearls — MRSA epidemiology",
        url="https://www.ncbi.nlm.nih.gov/books/NBK482221/",
        publisher="StatPearls",
    ),
}

ROWS = [
    # source, slug, name, mortality probability, exposure, tags, note
    ("ukhsa", "mrsa-bacteremia-30d",
     "MRSA bacteraemia (per episode, 30-day)",
     0.34, "per_event",
     ("infection", "mrsa"),
     "30-day all-cause mortality ≈ 34% (UK 2022-23)."),
    ("ukhsa", "mssa-bacteremia-30d",
     "MSSA bacteraemia (per episode, 30-day)",
     0.27, "per_event",
     ("infection", "mrsa"),
     "30-day all-cause mortality ≈ 27%."),
    ("ukhsa", "c-difficile-30d",
     "C. difficile infection (per case, 30-day)",
     0.13, "per_event",
     ("infection", "cdiff"),
     "Approximate 30-day mortality across cohorts; varies 7-20%."),
    ("statpearls", "sepsis-severe",
     "Severe sepsis / septic shock (per episode)",
     0.40, "per_event",
     ("infection", "sepsis"),
     "Case-fatality 25-50% depending on severity."),
    ("who_rabies", "rabies-symptomatic",
     "Rabies (per case once symptoms appear)",
     0.999, "per_event",
     ("infection", "rabies"),
     "≥99% case-fatality once symptoms appear; preventable by timely PEP."),
    ("who_rabies", "rabies-dog-bite-endemic",
     "Dog bite in rabies-endemic area (no PEP)",
     0.18, "per_event",
     ("infection", "rabies", "animal"),
     "~15-20% of untreated bites by a confirmed-rabid dog result in rabies death."),
    ("cdc_tetanus", "tetanus-untreated",
     "Tetanus (per case, no medical care)",
     0.50, "per_event",
     ("infection", "tetanus"),
     "Generalised tetanus case-fatality ≈ 50% without modern care."),
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
                slug=f"inf:{slug}",
                name=name,
                category="disease",
                micromorts=from_probability(p),
                exposure=exposure,
                exposure_detail=note,
                source_id=src_ids[src_key],
                original_value=f"{p*100:.1f}% case-fatality",
                original_unit="case-fatality probability",
                confidence="medium",
            )
            add_tags(conn, risk_id, list(tags))
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"infections: ingested {ingest(conn)} entries.")
