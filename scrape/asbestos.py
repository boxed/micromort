"""Asbestos / mesothelioma occupational mortality.

Sources:
- Puntoni et al. (Genoa shipyard cohort, 55-yr follow-up).
- Tagliabue et al. — Shipyard worker mortality, Italy.
- OSHA / NCI summary of asbestos-related cancer risks.
"""
from __future__ import annotations

import datetime as dt

from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCES = {
    "puntoni_genoa": dict(
        name="Puntoni et al. — Genoa shipyard cohort, 55-yr follow-up",
        url="https://pmc.ncbi.nlm.nih.gov/articles/PMC6310930/",
        publisher="Occupational Medicine / Univ. of Genoa",
    ),
    "nci_asbestos": dict(
        name="NCI — Asbestos Exposure & Cancer Risk Fact Sheet",
        url="https://www.cancer.gov/about-cancer/causes-prevention/risk/substances/asbestos/asbestos-fact-sheet",
        publisher="US NCI",
    ),
}

ROWS = [
    # source, slug, name, micromorts (lifetime), tags, note
    ("puntoni_genoa", "shipyard-worker-pleural-meso",
     "Shipyard worker 1960-81 (lifetime pleural-mesothelioma excess)",
     5_000, ("occupation", "asbestos", "cancer", "lifetime"),
     "Genoa cohort: 575 pleural-mesothelioma deaths vs 1 expected — ~0.5% lifetime excess."),
    ("puntoni_genoa", "shipyard-worker-asbestosis",
     "Shipyard worker 1960-81 (lifetime asbestosis excess)",
     20_000, ("occupation", "asbestos", "respiratory", "lifetime"),
     "Genoa cohort: 2,277 asbestosis deaths vs 1 expected — ~2% lifetime excess."),
    ("nci_asbestos", "asbestos-shipyard-secondary",
     "Family member of asbestos worker (lifetime asbestosis)",
     2_000, ("environmental", "asbestos", "lifetime", "secondary"),
     "LA County study: 11% of wives, 2-7% of children showed pulmonary signs."),
    ("nci_asbestos", "mesothelioma-lifetime-us",
     "Mesothelioma (US average resident, lifetime)",
     500, ("cancer", "lifetime", "asbestos"),
     "Lifetime US mesothelioma mortality risk ≈ 0.05% in unexposed population."),
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
        for src_key, slug, name, mm, tags, note in ROWS:
            cat = "occupation" if "occupation" in tags else "environmental"
            risk_id = upsert_risk(
                conn,
                slug=f"asb:{slug}",
                name=name,
                category=cat,
                micromorts=mm,
                exposure="lifetime",
                exposure_detail=note,
                source_id=src_ids[src_key],
                original_value=note,
                original_unit="lifetime excess mortality (µmt)",
                confidence="medium",
            )
            add_tags(conn, risk_id, list(tags))
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"asbestos: ingested {ingest(conn)} entries.")
