"""Global health risks — malaria, TB, HIV by region (per resident-year).

Sources: WHO World Malaria Report 2023; WHO Global TB Report 2023;
UNAIDS Global AIDS Update 2023.

Numbers are 2022 estimates.
"""
from __future__ import annotations

import datetime as dt

from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCES = {
    "who_malaria": dict(
        name="WHO World Malaria Report 2023",
        url="https://www.who.int/news-room/fact-sheets/detail/malaria",
        publisher="World Health Organization",
    ),
    "who_tb": dict(
        name="WHO Global Tuberculosis Report 2023",
        url="https://www.who.int/teams/global-tuberculosis-programme/tb-reports",
        publisher="World Health Organization",
    ),
    "unaids": dict(
        name="UNAIDS Global AIDS Update 2023",
        url="https://www.unaids.org/en/resources/documents/2023/2023_unaids_data",
        publisher="UNAIDS",
    ),
}
YEAR = 2022

# (source, slug, name, deaths/year, population, region, tags, note)
ROWS = [
    ("who_malaria",
     "malaria-world",
     "Malaria (global average)",
     608_000, 7_950_000_000, "world",
     ("infectious", "malaria"),
     "608,000 global deaths; 96% in WHO African Region."),
    ("who_malaria",
     "malaria-africa",
     "Malaria (WHO African Region)",
     584_000, 1_290_000_000, "africa",
     ("infectious", "malaria"),
     "94% of global malaria deaths concentrated in Sub-Saharan Africa."),
    ("who_malaria",
     "malaria-african-child",
     "Malaria (Sub-Saharan African child under 5)",
     440_000, 130_000_000, "africa",
     ("infectious", "malaria", "child"),
     "Three-quarters of malaria deaths are children under 5."),
    ("who_tb",
     "tb-world",
     "Tuberculosis (global average)",
     1_300_000, 7_950_000_000, "world",
     ("infectious", "tb"),
     "1.3 million TB deaths globally in 2022."),
    ("who_tb",
     "tb-lesotho",
     "Tuberculosis (Lesotho)",
     5_000, 2_300_000, "Lesotho",
     ("infectious", "tb"),
     "Among highest TB death rates globally (~220/100k)."),
    ("unaids",
     "hiv-world",
     "HIV/AIDS (global average)",
     630_000, 7_950_000_000, "world",
     ("infectious", "hiv"),
     "630k AIDS-related deaths globally in 2022; declining trend."),
    ("unaids",
     "hiv-eswatini",
     "HIV/AIDS (Eswatini — highest prevalence)",
     2_400, 1_200_000, "Eswatini",
     ("infectious", "hiv"),
     "Highest HIV prevalence globally (~26% of adults)."),
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
        for src_key, slug, name, deaths, pop, region, tags, note in ROWS:
            mm = 1_000_000 * deaths / pop
            risk_id = upsert_risk(
                conn,
                slug=f"global:{slug}-{YEAR}",
                name=f"{name} ({YEAR})",
                category="disease",
                micromorts=mm,
                exposure="per_year",
                exposure_detail=note,
                region=region,
                year=YEAR,
                source_id=src_ids[src_key],
                original_value=f"{deaths:,} deaths / {pop:,} pop",
                original_unit="deaths per year per population",
                confidence="medium",
            )
            add_tags(conn, risk_id, list(tags))
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"global health: ingested {ingest(conn)} entries.")
