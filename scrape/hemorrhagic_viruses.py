"""Highly lethal viral hemorrhagic fevers and historical infectious diseases.

Sources:
- WHO Ebola disease fact sheet (~50% average CFR; 25-90% across outbreaks).
- WHO Marburg virus disease fact sheet (~88% peak CFR).
- Lytras et al. 2025 (JoGH) — global outbreak case fatality summary.
- WHO measles fact sheet (CFR 0.1% high-income; 5-15% in vulnerable populations).
- CDC — Polio paralytic case-fatality.
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_probability
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCES = {
    "who_ebola": dict(
        name="WHO — Ebola disease fact sheet",
        url="https://www.who.int/news-room/fact-sheets/detail/ebola-disease",
        publisher="World Health Organization",
    ),
    "who_marburg": dict(
        name="WHO — Marburg virus disease fact sheet",
        url="https://www.who.int/news-room/fact-sheets/detail/marburg-virus-disease",
        publisher="World Health Organization",
    ),
    "jogh_2025": dict(
        name="JoGH 2025 — Global infectious-disease outbreak case-fatality analysis",
        url="https://jogh.org/2025/jogh-15-04151/",
        publisher="Journal of Global Health",
    ),
    "who_measles": dict(
        name="WHO — Measles fact sheet",
        url="https://www.who.int/news-room/fact-sheets/detail/measles",
        publisher="World Health Organization",
    ),
    "cdc_polio": dict(
        name="CDC Pink Book — Poliomyelitis",
        url="https://www.cdc.gov/pinkbook/hcp/table-of-contents/chapter-18-poliomyelitis.html",
        publisher="US CDC",
    ),
    "wiki_smallpox": dict(
        name="Wikipedia — Smallpox",
        url="https://en.wikipedia.org/wiki/Smallpox",
        publisher="Wikipedia",
    ),
}

ROWS = [
    # source, slug, name, case-fatality probability, tags, note
    ("who_marburg", "marburg-vhf",
     "Marburg virus disease (per case, outbreak avg)",
     0.50, ("infection", "vhf"),
     "Average ≈50%; outbreaks have reached 88%."),
    ("jogh_2025", "marburg-2025-meta",
     "Marburg virus disease (1996-2023 meta-CFR)",
     0.77, ("infection", "vhf"),
     "JoGH 2025 meta-analysis: 76.9% CFR across outbreaks."),
    ("who_ebola", "ebola-vhf",
     "Ebola virus disease (per case, average)",
     0.50, ("infection", "vhf"),
     "Outbreak CFR ranges 25-90%."),
    ("jogh_2025", "ebola-2025-meta",
     "Ebola virus disease (1996-2023 meta-CFR)",
     0.63, ("infection", "vhf"),
     "JoGH 2025 meta-analysis: 63% CFR across outbreaks."),
    ("who_measles", "measles-untreated",
     "Measles (case, low-income/unvaccinated setting)",
     0.10, ("infection", "vaccine-preventable"),
     "5-15% CFR in vulnerable populations without care."),
    ("who_measles", "measles-modern-hic",
     "Measles (case, high-income setting)",
     0.001, ("infection", "vaccine-preventable"),
     "≈0.1% CFR with modern supportive care."),
    ("cdc_polio", "polio-paralytic",
     "Poliomyelitis (paralytic case)",
     0.05, ("infection", "vaccine-preventable"),
     "Bulbar paralytic polio case-fatality 2-10%; midpoint shown."),
    ("wiki_smallpox", "smallpox-variola-major",
     "Smallpox (Variola major, per case, pre-eradication)",
     0.30, ("infection", "historical", "eradicated"),
     "Average CFR ~30% before eradication (1980)."),
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
        for src_key, slug, name, p, tags, note in ROWS:
            risk_id = upsert_risk(
                conn,
                slug=f"vhf:{slug}",
                name=name,
                category="disease",
                micromorts=from_probability(p),
                exposure="per_event",
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
    print(f"hemorrhagic_viruses: ingested {ingest(conn)} entries.")
