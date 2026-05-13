"""Historical reference points: war, disasters, pandemics.

Sources:
- Wikipedia 'World War II casualties' + DCAS.
- National WWII Museum — 'US Military by the Numbers'.
- Wikipedia — Titanic, Hindenburg passenger lists & fatality counts.
- Wikipedia — 1918 Spanish-flu pandemic global death tolls.
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_deaths_per, from_probability
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCES = {
    "wwii_museum": dict(
        name="National WWII Museum — US Military by the Numbers",
        url="https://www.nationalww2museum.org/students-teachers/student-resources/research-starters/research-starters-us-military-numbers",
        publisher="National WWII Museum",
    ),
    "wiki_disasters": dict(
        name="Wikipedia — Titanic & Hindenburg disaster pages",
        url="https://en.wikipedia.org/wiki/Hindenburg_disaster",
        publisher="Wikipedia",
    ),
    "wiki_flu": dict(
        name="Wikipedia — 1918 Spanish-flu pandemic",
        url="https://en.wikipedia.org/wiki/Spanish_flu",
        publisher="Wikipedia",
    ),
}

ROWS = [
    # source, slug, name, micromorts, exposure, tags, note
    ("wwii_museum", "wwii-us-soldier",
     "US WWII soldier (per 1000 combatants — KIA)",
     from_deaths_per(8.6, 1_000), "per_event",
     ("war", "historical", "wwii"),
     "8.6 KIA per 1,000 US combatants; 3 additional non-combat deaths."),
    ("wwii_museum", "wwii-us-soldier-allcause",
     "US WWII soldier (all-cause, per combatant)",
     from_deaths_per(11.6, 1_000), "per_event",
     ("war", "historical", "wwii"),
     "KIA + non-combat deaths per 1,000 combatants."),
    ("wwii_museum", "civil-war-soldier",
     "US Civil War soldier (per combatant)",
     from_probability(0.20), "per_event",
     ("war", "historical", "civil-war"),
     "~20% mortality among combatants — far higher than any later US conflict."),
    ("wiki_disasters", "titanic-passenger",
     "Titanic passenger (1912)",
     from_probability(0.68), "per_event",
     ("ship", "historical", "disaster"),
     "1,517 of ~2,224 on board perished — 68% fatality."),
    ("wiki_disasters", "titanic-3rd-class-man",
     "Titanic 3rd-class male passenger",
     from_probability(0.86), "per_event",
     ("ship", "historical", "demographic"),
     "Only ~14% of 3rd-class men (69/476) survived."),
    ("wiki_disasters", "hindenburg-passenger",
     "Hindenburg airship passenger (1937)",
     from_probability(0.36), "per_event",
     ("aviation", "historical", "disaster"),
     "36 of 97 on board perished; survival 64% — better than Titanic."),
    ("wiki_flu", "spanish-flu-1918-19",
     "1918 Spanish-flu pandemic (per person, 2-year exposure)",
     from_probability(0.03), "per_event",
     ("pandemic", "historical", "flu"),
     "~50 million deaths on 1.8 billion population — ~3% global mortality."),
    ("wwii_museum", "wwii-soviet-soldier",
     "Soviet WWII soldier (per combatant)",
     from_probability(0.25), "per_event",
     ("war", "historical", "wwii"),
     "~25% mortality among Soviet combatants — worst of any major belligerent."),
    ("wwii_museum", "wwii-civilian-soviet",
     "Soviet civilian, WWII years (per resident)",
     from_probability(0.13), "per_event",
     ("war", "historical", "wwii"),
     "~13% mortality 1941-45 from war causes."),
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
        for src_key, slug, name, mm, exposure, tags, note in ROWS:
            risk_id = upsert_risk(
                conn,
                slug=f"hist:{slug}",
                name=name,
                category="violence" if "war" in tags else "environmental",
                micromorts=mm,
                exposure=exposure,
                exposure_detail=note,
                source_id=src_ids[src_key],
                original_value=note,
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
    print(f"historical_disasters: ingested {ingest(conn)} entries.")
