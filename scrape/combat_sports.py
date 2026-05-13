"""Combat sports — per-fight and lifetime micromorts.

Sources:
- Boxing: roughly 1,064 ring deaths reported worldwide since 1890;
  globally pro+amateur fights estimated to be 500k-1M cumulative,
  giving a rough 1-2 fatalities per 1,000 sanctioned fights.
- MMA: 16 documented fight-related deaths in MMA history. UFC has had
  zero in over 5,000 sanctioned fights.
- NFL career: ~3× neurodegenerative-disease mortality vs general
  population. Translating to lifetime µmt is approximate.
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_deaths_per
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCES = {
    "wiki_mma_deaths": dict(
        name="Wikipedia — Fatalities in MMA contests",
        url="https://en.wikipedia.org/wiki/Fatalities_in_mixed_martial_arts_contests",
        publisher="Wikipedia",
    ),
    "bu_cte": dict(
        name="BU CTE Center — 345/376 deceased NFL players had CTE (2023)",
        url="https://www.bumc.bu.edu/camed/2023/02/06/researchers-find-cte-in-345-of-376-former-nfl-players-studied/",
        publisher="Boston University CTE Center",
    ),
    "boxing_history": dict(
        name="Wikipedia + Manuel Velazquez Collection — Boxing fatalities",
        url="https://en.wikipedia.org/wiki/List_of_deaths_due_to_injuries_sustained_in_boxing",
        publisher="Wikipedia / Manuel Velazquez Collection",
    ),
}

ROWS = [
    # source, slug, name, deaths, per_N, exposure, tags, note
    ("boxing_history", "boxing-pro-fight",
     "Professional boxing match (per fighter-fight)",
     1.5, 1_000, "per_event",
     ("combat", "boxing"),
     "Rough estimate: ~1-2 deaths per 1,000 pro fights worldwide, all eras."),
    ("wiki_mma_deaths", "mma-fight",
     "MMA sanctioned bout (per fighter-fight)",
     16, 100_000, "per_event",
     ("combat", "mma"),
     "16 documented deaths over ~100k cumulative sanctioned MMA fights."),
    ("wiki_mma_deaths", "ufc-fight",
     "UFC fight (per fighter-fight, upper 95% bound)",
     3, 5_000, "per_event",
     ("combat", "mma", "ufc", "upper-bound"),
     "Zero in-fight deaths over ~5,000 UFC fights. Value is rule-of-three 95% upper bound."),
    ("bu_cte", "nfl-career-cte-lifetime",
     "NFL career — excess neurodegenerative-disease mortality",
     20_000, 1, "lifetime",
     ("football", "career"),
     "~3× higher death rate from Alzheimer/ALS vs population. Rough lifetime excess."),
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
            if per_n == 1:
                mm = float(deaths)
            else:
                mm = from_deaths_per(deaths, per_n)
            risk_id = upsert_risk(
                conn,
                slug=f"combat:{slug}",
                name=name,
                category="activity",
                micromorts=mm,
                exposure=exposure,
                exposure_detail=note,
                source_id=src_ids[src_key],
                original_value=f"{deaths} / {per_n:,}" if per_n != 1 else str(deaths),
                original_unit=exposure,
                confidence="low" if "upper-bound" in tags else "medium",
            )
            add_tags(conn, risk_id, list(tags))
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"combat sports: ingested {ingest(conn)} entries.")
