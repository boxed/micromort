"""Chronic-disease lifetime mortality contributions.

Sources:
- Nature Medicine 2024 — Lifetime dementia risk after age 55.
- Alzheimer's Association — 2025 Facts and Figures.
- Lancet Diabetes & Endocrinology 2022 — Type-2 diabetes years of life lost.
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_probability
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCES = {
    "nat_med_2024": dict(
        name="Nature Medicine 2024 — Lifetime dementia risk after age 55",
        url="https://www.nature.com/articles/s41591-024-03340-9",
        publisher="Nature Medicine",
    ),
    "alz_facts_2025": dict(
        name="Alzheimer's Association — 2025 Facts and Figures",
        url="https://www.alz.org/alzheimers-dementia/facts-figures",
        publisher="Alzheimer's Association",
    ),
    "lancet_t2dm": dict(
        name="Lancet Diabetes & Endocrinology — T2DM 23-jurisdiction study",
        url="https://www.thelancet.com/journals/landia/article/PIIS2213-8587(22)00252-2/abstract",
        publisher="Lancet Diabetes & Endocrinology",
    ),
}

ROWS = [
    # source, slug, name, lifetime probability, tags, note
    ("nat_med_2024", "dementia-lifetime-55",
     "Dementia (any cause) — lifetime risk after age 55",
     0.42, ("chronic", "dementia", "lifetime"),
     "42% lifetime risk; substantially higher in women, Black adults, APOE ε4 carriers."),
    ("alz_facts_2025", "alzheimer-lifetime-women",
     "Alzheimer's disease — lifetime risk, women age 45",
     0.20, ("chronic", "dementia", "demographic", "lifetime"),
     "Women age 45 face ~1 in 5 lifetime risk."),
    ("alz_facts_2025", "alzheimer-lifetime-men",
     "Alzheimer's disease — lifetime risk, men age 45",
     0.10, ("chronic", "dementia", "demographic", "lifetime"),
     "Men age 45 face ~1 in 10 lifetime risk."),
    ("alz_facts_2025", "alzheimer-65y-man",
     "Alzheimer's disease — remaining lifetime risk, 65-yr-old man",
     0.063, ("chronic", "dementia", "demographic", "lifetime"),
     "Conditional risk from age 65."),
    ("alz_facts_2025", "alzheimer-65y-woman",
     "Alzheimer's disease — remaining lifetime risk, 65-yr-old woman",
     0.12, ("chronic", "dementia", "demographic", "lifetime"),
     "Conditional risk from age 65."),
    ("lancet_t2dm", "t2dm-singapore-men",
     "Type-2 diabetes lifetime risk (Singaporean men)",
     0.596, ("chronic", "diabetes", "lifetime", "demographic"),
     "59.6% lifetime risk — highest across 23 high-income jurisdictions."),
    ("lancet_t2dm", "t2dm-scotland-women",
     "Type-2 diabetes lifetime risk (Scottish women)",
     0.163, ("chronic", "diabetes", "lifetime", "demographic"),
     "16.3% — lowest across 23 high-income jurisdictions."),
    ("lancet_t2dm", "t2dm-yll-diag30",
     "Type-2 diabetes diagnosed at age 30 — excess lifetime mortality",
     0.14 * 8000 * 80 / 1_000_000,  # 14 years lost * baseline yearly µmt / 1e6 → scale to µmt
     ("chronic", "diabetes", "lifetime"),
     "Mean 14 years of life lost when T2DM is diagnosed at age 30 (USA rates)."),
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
        for src_key, slug, name, val, tags, note in ROWS:
            # First seven rows have probabilities; t2dm-yll-diag30 has direct µmt already.
            if slug == "t2dm-yll-diag30":
                # Translate "14 years lost" into approximate lifetime µmt overhead.
                # 14 years × baseline ~8,000 µmt/yr ≈ 112,000 µmt cumulative.
                mm = 14 * 8000
            else:
                mm = from_probability(val)
            risk_id = upsert_risk(
                conn,
                slug=f"chronic:{slug}",
                name=name,
                category="disease",
                micromorts=mm,
                exposure="lifetime",
                exposure_detail=note,
                source_id=src_ids[src_key],
                original_value=note,
                original_unit="lifetime probability / excess µmt",
                confidence="medium",
            )
            add_tags(conn, risk_id, list(tags))
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"chronic_diseases: ingested {ingest(conn)} entries.")
