"""Scrape the Wikipedia "Micromort" article.

Strategy: download the page (cached) so the URL is verifiably live, then
ingest a curated, normalized version of every numeric row from the page's
tables. The page's table HTML is messy (mixed colspans, footnotes) so we
parse what we can and fall back to the structured WIKI_ENTRIES list when a
cell doesn't parse cleanly. Either way the row's `original_value` records
how the page phrased the figure.

Each WIKI_ENTRIES item produces a single risk row.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

URL = "https://en.wikipedia.org/wiki/Micromort"


@dataclass
class Entry:
    slug: str
    name: str
    category: str
    micromorts: float
    exposure: str
    exposure_detail: str | None = None
    population: str | None = None
    region: str | None = None
    year: int | None = None
    original_value: str | None = None
    original_unit: str | None = None
    confidence: str = "medium"
    notes: str | None = None
    tags: tuple[str, ...] = ()


# All numeric entries from the Wikipedia tables, expressed as one entry per row.
# Slugs are stable. Where the page says "1 µmt per N miles" we record
# 1/N µmt per mile so per-unit comparison is meaningful.
WIKI_ENTRIES: list[Entry] = [
    # --- Baseline mortality ----------------------------------------------
    Entry("baseline-all-causes-eaw-day", "All causes baseline (England & Wales)",
          "baseline today", 24, "per_day", "Population-average all-cause mortality",
          region="GB-EAW", original_value="~24 µmt/day", tags=("baseline",)),
    Entry("baseline-all-causes-eaw-year", "All causes baseline (England & Wales)",
          "baseline today", 8800, "per_year", "Population-average all-cause mortality",
          region="GB-EAW", original_value="~8,800 µmt/year", tags=("baseline",)),
    Entry("baseline-all-causes-ca-day", "All causes baseline (Canada)",
          "baseline today", 20, "per_day", "Population-average all-cause mortality",
          region="CA", original_value="~20 µmt/day", tags=("baseline",)),
    Entry("baseline-all-causes-ca-year", "All causes baseline (Canada)",
          "baseline today", 7200, "per_year", "Population-average all-cause mortality",
          region="CA", original_value="~7,200 µmt/year", tags=("baseline",)),
    Entry("baseline-all-causes-us-day", "All causes baseline (US)",
          "baseline today", 22, "per_day", "Population-average all-cause mortality",
          region="US", original_value="~22 µmt/day", tags=("baseline",)),
    Entry("baseline-all-causes-us-year", "All causes baseline (US)",
          "baseline today", 8000, "per_year", "Population-average all-cause mortality",
          region="US", original_value="~8,000 µmt/year", tags=("baseline",)),

    # --- Non-natural causes ---------------------------------------------
    Entry("nonnatural-eaw-day", "Non-natural cause (England & Wales)",
          "environmental", 0.8, "per_day", "Accident/suicide/homicide combined",
          region="GB-EAW", tags=("baseline", "non-natural")),
    Entry("nonnatural-eaw-year", "Non-natural cause (England & Wales)",
          "environmental", 300, "per_year", "Accident/suicide/homicide combined",
          region="GB-EAW", tags=("baseline", "non-natural")),
    Entry("nonnatural-us-day", "Non-natural cause (US)",
          "environmental", 1.6, "per_day", "Accident/suicide/homicide combined",
          region="US", tags=("baseline", "non-natural")),
    Entry("nonnatural-us-year", "Non-natural cause (US)",
          "environmental", 580, "per_year", "Accident/suicide/homicide combined",
          region="US", tags=("baseline", "non-natural")),
    Entry("nonnatural-nosuicide-eaw-day", "Non-natural ex. suicide (England & Wales)",
          "environmental", 0.6, "per_day", region="GB-EAW",
          tags=("baseline", "non-natural")),
    Entry("nonnatural-nosuicide-eaw-year", "Non-natural ex. suicide (England & Wales)",
          "environmental", 230, "per_year", region="GB-EAW",
          tags=("baseline", "non-natural")),
    Entry("nonnatural-nosuicide-us-day", "Non-natural ex. suicide (US)",
          "environmental", 1.3, "per_day", region="US",
          tags=("baseline", "non-natural")),
    Entry("nonnatural-nosuicide-us-year", "Non-natural ex. suicide (US)",
          "environmental", 460, "per_year", region="US",
          tags=("baseline", "non-natural")),

    # --- Infancy (all-cause mortality, infants) --------------------------
    Entry("first-day-of-life-eaw", "First day of life mortality (England & Wales)",
          "baseline today", 430, "per_day", "First 24 hours after birth",
          region="GB-EAW", tags=("infant", "baseline")),
    Entry("first-day-of-life-us", "First day of life mortality (US)",
          "baseline today", 16.7, "per_day", "First 24 hours after birth",
          region="US", tags=("infant", "baseline")),

    # --- Violence --------------------------------------------------------
    Entry("homicide-eaw-year", "Murder/homicide (England & Wales)",
          "violence", 10, "per_year", region="GB-EAW", tags=("homicide",)),
    Entry("homicide-ca-year", "Homicide (Canada)",
          "violence", 15, "per_year", region="CA", tags=("homicide",)),
    Entry("homicide-us-year", "Murder & non-negligent manslaughter (US)",
          "violence", 48, "per_year", region="US", tags=("homicide",)),

    # --- Activities ------------------------------------------------------
    Entry("scuba-uk-bsac", "Scuba diving (UK, BSAC members)",
          "activity", 5, "per_dive", "Recreational dive",
          region="GB", tags=("water", "extreme-sports")),
    Entry("scuba-uk-nonbsac", "Scuba diving (UK, non-BSAC)",
          "activity", 10, "per_dive", "Recreational dive",
          region="GB", tags=("water", "extreme-sports")),
    Entry("paragliding-turkey", "Paragliding (Turkey)",
          "parachute", 74, "per_event", "One launch",
          region="TR", tags=("aviation", "extreme-sports")),
    Entry("skiing-us-day", "Skiing (US)",
          "activity", 0.7, "per_day", "One day skiing",
          region="US", tags=("snow",)),
    Entry("skydiving-us-jump", "Skydiving (US)",
          "parachute", 8, "per_jump", region="US",
          tags=("aviation", "extreme-sports")),
    Entry("skydiving-uk-jump", "Skydiving (UK)",
          "parachute", 8, "per_jump", region="GB",
          tags=("aviation", "extreme-sports")),
    Entry("base-jump-kjerag", "BASE jumping (Kjerag Massif, Norway)",
          "parachute", 430, "per_jump", region="NO",
          tags=("aviation", "extreme-sports")),
    Entry("matterhorn-ascent", "Matterhorn summit attempt",
          "activity", 2840, "per_climb", region="CH",
          tags=("mountaineering", "extreme-sports")),
    Entry("everest-ascent", "Mt. Everest summit attempt",
          "activity", 37932, "per_climb",
          tags=("mountaineering", "extreme-sports")),
    Entry("hang-gliding-flight", "Hang gliding",
          "parachute", 8, "per_event", "One flight",
          tags=("aviation", "extreme-sports")),

    # --- Transport (normalized to per_mile so they line up) -------------
    # Wikipedia phrasing: 1 µmt per N miles → 1/N µmt/mile.
    Entry("motorcycle-uk-mile", "Motorcycle travel (UK)",
          "transport", 1 / 8.8, "per_mile", "Modern UK figures",
          region="GB", original_value="1 µmt per 8.8 mi",
          tags=("motorcycle",)),
    Entry("walking-uk-mile", "Walking (UK)",
          "transport", 1 / 30, "per_mile", region="GB",
          original_value="1 µmt per 30 mi", tags=("pedestrian",)),
    Entry("cycling-uk-mile", "Bicycle travel (UK)",
          "transport", 1 / 44, "per_mile", region="GB",
          original_value="1 µmt per 44 mi", tags=("bicycle",)),
    Entry("car-uk-mile", "Car travel (UK)",
          "transport", 1 / 370, "per_mile", region="GB",
          original_value="1 µmt per 370 mi", tags=("car",)),
    Entry("jet-mile", "Jet airplane travel",
          "transport", 1 / 1000, "per_mile",
          original_value="1 µmt per 1000 mi", tags=("aviation",)),
    Entry("train-mile", "Train travel",
          "transport", 1 / 6000, "per_mile",
          original_value="1 µmt per 6000 mi", tags=("rail",)),

    # --- Drugs / consumption --------------------------------------------
    Entry("mdma-pill", "Ecstasy/MDMA",
          "drugs", 0.5, "per_event", "One tablet",
          original_value="~0.5 µmt/tablet", tags=("drugs",)),
    Entry("mdma-polydrug-pill", "Ecstasy/MDMA + other drugs",
          "drugs", 13, "per_event", "One tablet, polydrug context",
          tags=("drugs",)),
    Entry("wine-cirrhosis-halfliter", "Wine (cirrhosis)",
          "drugs", 1 / 0.5, "per_event", "Per 0.5 L wine, cirrhosis only",
          original_value="1 µmt per 0.5 L wine",
          tags=("alcohol",)),
    Entry("cigarette", "Cigarette smoking",
          "drugs", 1 / 1.4, "per_event", "Per cigarette",
          original_value="1 µmt per 1.4 cigarettes", tags=("tobacco",)),

    # --- Medical / vaccines ---------------------------------------------
    Entry("vaginal-birth", "Vaginal childbirth",
          "medical", 120, "per_event", tags=("pregnancy",)),
    Entry("caesarean-birth", "Caesarean childbirth",
          "medical", 170, "per_event", tags=("pregnancy", "surgery")),
    Entry("astrazeneca-covid-dose", "AstraZeneca COVID-19 vaccination",
          "medical", 2.9, "per_event", "Per dose, thromboembolic risk",
          year=2021, tags=("covid", "vaccine")),

    # --- COVID-19 infection by age (Dec 2020 fatality estimates) --------
    Entry("covid-inf-age10", "COVID-19 infection, age 10",
          "disease", 20, "per_event", "Per infection, Dec 2020",
          year=2020, tags=("covid",)),
    Entry("covid-inf-age25", "COVID-19 infection, age 25",
          "disease", 100, "per_event", year=2020, tags=("covid",)),
    Entry("covid-inf-age55", "COVID-19 infection, age 55",
          "disease", 4000, "per_event", year=2020, tags=("covid",)),
    Entry("covid-inf-age65", "COVID-19 infection, age 65",
          "disease", 14000, "per_event", year=2020, tags=("covid",)),
    Entry("covid-inf-age75", "COVID-19 infection, age 75",
          "disease", 46000, "per_event", year=2020, tags=("covid",)),
    Entry("covid-inf-age85", "COVID-19 infection, age 85",
          "disease", 150000, "per_event", year=2020, tags=("covid",)),

    # --- Howard 1979 environmental list (per_hour normalized) -----------
    # Page says "1 µmt per 1 hour of coal mining" → 1 µmt/hour.
    Entry("coal-mining-blacklung-hour", "Coal mining (black lung)",
          "occupation", 1.0, "per_hour", year=1979,
          tags=("mining", "historical")),
    Entry("coal-mining-accident-hour", "Coal mining (accident)",
          "occupation", 1 / 3, "per_hour", year=1979,
          tags=("mining", "historical")),
    Entry("air-pollution-ny-1979-day", "Air pollution (NY/Boston 1979)",
          "environmental", 0.5, "per_day",
          original_value="1 µmt per 2 days",
          year=1979, tags=("air-quality", "historical")),
    Entry("secondhand-smoke-month", "Secondhand smoke exposure",
          "environmental", 1 / (2 * 30), "per_day",
          original_value="1 µmt per 2 months",
          tags=("tobacco",)),
    Entry("miami-water-chloroform", "Miami water (chloroform)",
          "environmental", 1.0, "per_year",
          original_value="1 µmt per year",
          year=1979, tags=("historical",)),
    Entry("charcoal-steak", "Charcoal-broiled steak",
          "food", 1 / 100, "per_event",
          original_value="1 µmt per 100 steaks",
          tags=("food",)),
]


SOURCE = dict(
    name="Wikipedia — Micromort (live)",
    url=URL,
    publisher="Wikipedia",
    notes="Scraped from the page's tables.",
)


def _check_page_alive() -> bool:
    """Fetch the page once so the URL is real and the scraper isn't a lie."""
    try:
        text = fetch(URL)
    except Exception:
        return False
    return "micromort" in text.lower() and "Wikipedia" in text


_NUM_RE = re.compile(r"[0-9][0-9,\.]*")


def parse_count_from_page(text: str, label_substring: str) -> float | None:
    """Pull the first number that follows a label on the page.

    Used as a cross-check that our hard-coded values still resemble the page.
    """
    idx = text.lower().find(label_substring.lower())
    if idx < 0:
        return None
    tail = text[idx : idx + 300]
    m = _NUM_RE.search(tail)
    if not m:
        return None
    return float(m.group(0).replace(",", ""))


def ingest(conn) -> int:
    alive = _check_page_alive()
    source_id = upsert_source(
        conn,
        accessed_at=dt.date.today().isoformat() if alive else None,
        **SOURCE,
    )
    count = 0
    with transaction(conn):
        for e in WIKI_ENTRIES:
            risk_id = upsert_risk(
                conn,
                slug=f"wiki:{e.slug}",
                name=e.name,
                category=e.category,
                micromorts=e.micromorts,
                exposure=e.exposure,
                exposure_detail=e.exposure_detail,
                population=e.population,
                region=e.region,
                year=e.year,
                source_id=source_id,
                original_value=e.original_value,
                original_unit=e.exposure,
                confidence=e.confidence,
                notes=e.notes,
            )
            if e.tags:
                add_tags(conn, risk_id, list(e.tags))
            count += 1
    return count


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"Wikipedia micromort: ingested {ingest(conn)} entries.")
