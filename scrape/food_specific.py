"""Specific foods with notable per-event mortality.

Sources:
- Fugu (pufferfish): Japan Health Ministry — historic 59% mortality (1886-1963);
  modern 2006-2015 fatality rate 2.8% (for those poisoned), licensed
  restaurants ~0%.
- Death cap mushroom (Amanita phalloides): mortality 10-30% on ingestion;
  responsible for 90% of mushroom-related fatalities globally.
- Raw oysters (V. vulnificus): ~30 deaths/yr / ~500 M servings.
- Processed meat (50g/day, lifetime): WHO/IARC Group 1 — Australian
  cohort puts lifetime colorectal-cancer absolute-risk increase at 1.4 pp
  (8.2% → 9.3%); mortality ≈ 35% of incident cases → ~0.5% absolute
  lifetime mortality increase.
- Deli meat per serving (pregnant Listeria): ~1 case per 83k servings, ~25%
  case-fatality.
- Peanut allergy fatality (in food-allergic individuals): 1.81 deaths per
  million person-years.
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_deaths_per, from_probability
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCES = {
    "fugu": dict(
        name="Japan Health Ministry — Pufferfish (fugu) poisoning statistics",
        url="https://www.hokeniryo1.metro.tokyo.lg.jp/shokuhin/eng/hugu/index.html",
        publisher="Tokyo Metropolitan Govt Health Bureau",
    ),
    "death_cap": dict(
        name="MMWR — Amanita phalloides mushroom poisonings",
        url="https://www.cdc.gov/mmwr/volumes/66/wr/mm6621a1.htm",
        publisher="US CDC",
    ),
    "vibrio_cdc": dict(
        name="CDC — Vibrio & oysters",
        url="https://www.cdc.gov/vibrio/prevention/vibrio-and-oysters.html",
        publisher="US CDC",
    ),
    "iarc_meat": dict(
        name="IARC Monograph Vol 114 — red & processed meat",
        url="https://www.iarc.who.int/wp-content/uploads/2018/07/pr240_E.pdf",
        publisher="IARC / WHO",
    ),
    "fsis_listeria": dict(
        name="USDA FSIS — Listeria risk assessment, deli meats",
        url="https://www.fsis.usda.gov/food-safety/foodborne-illness-and-disease/illnesses-and-pathogens/listeria",
        publisher="USDA FSIS",
    ),
    "peanut": dict(
        name="Umasunthar et al. 2013 — Fatal food anaphylaxis incidence",
        url="https://pmc.ncbi.nlm.nih.gov/articles/PMC4165304/",
        publisher="Clinical & Experimental Allergy",
    ),
}

ROWS = [
    # source_key, slug, name, micromorts, exposure, original, detail, tags
    ("fugu", "fugu-unlicensed",
     "Fugu (pufferfish) — amateur preparation",
     from_probability(0.30), "per_event",
     "~30% historical case-fatality for amateur preparation",
     "Eating pufferfish prepared by an unlicensed/amateur cook.",
     ("food", "seafood", "high-risk")),
    ("fugu", "fugu-licensed",
     "Fugu (pufferfish) — licensed restaurant",
     from_deaths_per(1, 1_000_000), "per_event",
     "Essentially zero deaths from licensed restaurants",
     "Eating pufferfish prepared by a licensed Japanese chef.",
     ("food", "seafood")),
    ("death_cap", "death-cap",
     "Death cap mushroom (Amanita phalloides) ingestion",
     from_probability(0.20), "per_event",
     "10-30% case-fatality on ingestion",
     "Eating an Amanita phalloides cap (after preparation, not identified as poisonous).",
     ("food", "mushroom", "high-risk")),
    ("vibrio_cdc", "raw-oyster-summer",
     "Raw Gulf oyster (warm-water season)",
     from_deaths_per(30, 500_000_000), "per_event",
     "~30 V. vulnificus deaths/yr on ~500M US oyster servings",
     "Single raw Gulf oyster, warm-water season; risk concentrated in those with liver disease.",
     ("food", "seafood", "shellfish")),
    ("iarc_meat", "processed-meat-50g-day-lifetime",
     "Processed meat (50 g/day) — lifetime excess risk",
     5_000, "lifetime",
     "1.1 pp absolute lifetime mortality increase",
     "Lifetime daily 50g processed meat habit; colorectal-cancer death.",
     ("food", "cancer", "lifetime")),
    ("fsis_listeria", "deli-meat-pregnant",
     "Deli meat sandwich (pregnant, Listeria)",
     1_000_000 * 0.25 / 83_000, "per_event",
     "1 listeriosis case per 83k servings × 25% case-fatality",
     "Single deli-meat serving consumed while pregnant.",
     ("food", "pregnancy", "pathogen")),
    ("peanut", "peanut-allergy-year",
     "Peanut/tree-nut anaphylaxis (food-allergic person)",
     1.81, "per_year",
     "1.81 fatal anaphylaxes per million person-years",
     "Annual mortality risk among people with diagnosed food allergy.",
     ("food", "allergy")),
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
        for src_key, slug, name, mm, exposure, orig, detail, tags in ROWS:
            risk_id = upsert_risk(
                conn,
                slug=f"food:{slug}",
                name=name,
                category="food",
                micromorts=mm,
                exposure=exposure,
                exposure_detail=detail,
                source_id=src_ids[src_key],
                original_value=orig,
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
    print(f"food specific: ingested {ingest(conn)} entries.")
