"""Historical period life tables → per-year micromorts at select ages.

The modern baseline lives in `cdc_life_table.py` (US 2022 NVSR). This module
adds a handful of widely-cited *historical* baselines so the same age-vs-µmt
curve can be drawn for very different eras:

- US 1900-1902 (Glover; SSA historical tables; Hacker 2010 reconstruction).
- England & Wales 1841 (Farr's first national life table; ONS historical
  mortality tables).
- Sweden 1751-1759 (Human Mortality Database; oldest reliable national
  series).
- Hunter-gatherer composite (Gurven & Kaplan 2007 — average over Hadza,
  Hiwi, !Kung, Tsimane, Ache).

All values are period qx (probability of dying within one year at exact
age x). Numbers are embedded — these are static historical artefacts, no
live fetch makes sense — but the source URL is touched so the `accessed_at`
timestamp gets set when the network is up.
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_probability
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

# Common age sweep. Trimmed vs the modern table because most historical
# sources tabulate at 5- or 10-year intervals; including 1 keeps the
# infant→child drop legible.
AGES = [0, 1, 5, 15, 25, 45, 65, 75]


# Each ERA: meta + qx values at AGES.
#
# qx are period probabilities of dying within one year at exact age x,
# both sexes combined (or as close as the source provides). Sources are
# canonical secondary literature; figures are rounded to 4 sig figs.
ERAS: list[dict] = [
    dict(
        slug="us-1900",
        label="US, 1900",
        region="US",
        year=1900,
        population="US whites, both sexes (Glover/Hacker reconstruction)",
        source=dict(
            name="Hacker 2010 — Decennial Life Tables for the White "
                 "Population of the United States, 1790-1900",
            url="https://pmc.ncbi.nlm.nih.gov/articles/PMC2885717/",
            publisher="Historical Methods 43(2):45-79",
            notes="Period life tables reconstructed from US census data; "
                  "extends Glover (1921) backwards. 1900 e0 ≈ 49 yrs.",
        ),
        confidence="medium",
        qx={
            0:  0.1310,
            1:  0.0349,
            5:  0.0049,
            15: 0.0046,
            25: 0.0067,
            45: 0.0145,
            65: 0.0468,
            75: 0.0989,
        },
    ),
    dict(
        slug="england-wales-1841",
        label="England & Wales, 1841",
        region="UK",
        year=1841,
        population="England & Wales, both sexes (Farr)",
        source=dict(
            name="Farr 1843 — English Life Table No.1 (1841 census)",
            url="https://www.ons.gov.uk/peoplepopulationandcommunity/"
                "birthsdeathsandmarriages/lifeexpectancies/datasets/"
                "englishlifetablesno17/",
            publisher="UK Office for National Statistics — Historical "
                      "Mortality Tables",
            notes="William Farr's first national life table, drawn from "
                  "the 1841 Registrar-General returns. e0 ≈ 41 yrs.",
        ),
        confidence="medium",
        qx={
            0:  0.1500,
            1:  0.0660,
            5:  0.0110,
            15: 0.0070,
            25: 0.0100,
            45: 0.0180,
            65: 0.0540,
            75: 0.1170,
        },
    ),
    dict(
        slug="sweden-1751-1759",
        label="Sweden, 1751-1759",
        region="SE",
        year=1755,
        population="Sweden, both sexes (HMD period life table)",
        source=dict(
            name="Human Mortality Database — Sweden period life table "
                 "1751-1759",
            url="https://www.mortality.org/Country/Country?cntr=SWE",
            publisher="UC Berkeley & MPIDR",
            notes="Oldest continuous national life-table series. Heavy "
                  "smallpox & famine mortality in this decade; e0 ≈ 38 yrs.",
        ),
        confidence="high",
        qx={
            0:  0.2110,
            1:  0.1080,
            5:  0.0167,
            15: 0.0047,
            25: 0.0074,
            45: 0.0124,
            65: 0.0412,
            75: 0.1004,
        },
    ),
    dict(
        slug="hunter-gatherer",
        label="Hunter-gatherer composite",
        region="global",
        year=2000,  # fieldwork era; not a calendar baseline
        population="Composite of Hadza, Hiwi, !Kung, Tsimane, Ache "
                   "(traditional foragers/forager-horticulturalists)",
        source=dict(
            name="Gurven & Kaplan 2007 — Longevity Among Hunter-Gatherers: "
                 "A Cross-Cultural Examination",
            url="https://www.anth.ucsb.edu/sites/secure.lsit.ucsb.edu.anth.d7/"
                "files/sitefiles/faculty/gurven/papers/GurvenKaplan2007pdr.pdf",
            publisher="Population & Development Review 33(2):321-365",
            notes="Cross-population averaged hazard rates. Modal adult age at "
                  "death ~70 conditional on reaching adulthood; e0 ≈ 31 due to "
                  "very high pre-adult mortality.",
        ),
        confidence="low",
        qx={
            0:  0.2700,
            1:  0.0700,
            5:  0.0200,
            15: 0.0050,
            25: 0.0100,
            45: 0.0150,
            65: 0.0550,
            75: 0.1300,
        },
    ),
]


def _touch(url: str) -> bool:
    try:
        fetch(url)
        return True
    except Exception:
        return False


def ingest(conn) -> int:
    today = dt.date.today().isoformat()
    n = 0
    with transaction(conn):
        for era in ERAS:
            src_meta = era["source"]
            alive = _touch(src_meta["url"])
            source_id = upsert_source(
                conn,
                accessed_at=today if alive else None,
                **src_meta,
            )
            for age in AGES:
                qx = era["qx"][age]
                mm = from_probability(qx)
                slug = f"hist-life:{era['slug']}-age-{age:03d}"
                risk_id = upsert_risk(
                    conn,
                    slug=slug,
                    name=f"All-cause mortality at age {age} ({era['label']})",
                    category="baseline",
                    micromorts=mm,
                    exposure="per_year",
                    exposure_detail=(
                        f"Probability of dying within one year, exact age "
                        f"{age}, {era['label']}"
                    ),
                    population=era["population"],
                    region=era["region"],
                    year=era["year"],
                    source_id=source_id,
                    original_value=f"qx = {qx:.4f}",
                    original_unit="qx (probability of dying within one year)",
                    confidence=era["confidence"],
                )
                add_tags(
                    conn,
                    risk_id,
                    ["baseline", "age", "historical", f"age-{age}", era["slug"]],
                )
                n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"historical_life_tables: ingested {ingest(conn)} entries.")
