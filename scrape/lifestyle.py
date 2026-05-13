"""Lifestyle / chronic exposure risks: obesity, sedentary lifestyle, alcohol use.

Sources:
- Bhaskaran et al. 2018 (Lancet Diabetes & Endocrinology) — BMI vs mortality
  in 3.6M UK adults.
- Borrell & Samuel 2014 — Obesity & mortality in US adults.
- Various meta-analyses of physical-activity mortality.

Lifetime years lost are converted to total lifetime µmt by dividing by
typical population life expectancy (~80 yrs) and multiplying by ~8000
µmt/year baseline → years_lost × 100,000.
"""
from __future__ import annotations

import datetime as dt

from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCES = {
    "bhaskaran_2018": dict(
        name="Bhaskaran et al. 2018 — UK BMI cohort (3.6M adults)",
        url="https://www.thelancet.com/journals/landia/article/PIIS2213-8587(18)30288-2/fulltext",
        publisher="Lancet Diabetes & Endocrinology",
    ),
    "khan_2018": dict(
        name="Khan et al. 2018 — Lifetime CVD risk by BMI",
        url="https://pmc.ncbi.nlm.nih.gov/articles/PMC5875319/",
        publisher="JAMA Cardiology",
    ),
    "borrell_2014": dict(
        name="Borrell & Samuel 2014 — US BMI mortality",
        url="https://pmc.ncbi.nlm.nih.gov/articles/PMC3953803/",
        publisher="American Journal of Public Health",
    ),
}

# (slug, name, micromorts (lifetime), tags, note, source)
ROWS = [
    ("bhaskaran_2018", "obese-man-lifetime",
     "Obese man (BMI 30+, lifetime excess mortality)",
     420_000, ("lifestyle", "obesity", "lifetime", "demographic"),
     "4.2 years life-expectancy lost from age 40 (UK 3.6M cohort)."),
    ("bhaskaran_2018", "obese-woman-lifetime",
     "Obese woman (BMI 30+, lifetime excess mortality)",
     350_000, ("lifestyle", "obesity", "lifetime", "demographic"),
     "3.5 years life-expectancy lost from age 40 (UK 3.6M cohort)."),
    ("borrell_2014", "morbid-obese-young-adult",
     "Morbid obesity (BMI ≥40, young adult, lifetime)",
     700_000, ("lifestyle", "obesity", "lifetime"),
     "≥7 years life-expectancy lost when morbid obesity begins age 18-29."),
    ("khan_2018", "overweight-man-cvd",
     "Overweight man (BMI 25-30, lifetime CVD excess)",
     50_000, ("lifestyle", "obesity", "cardiovascular"),
     "Hazard ratio 1.21 for CVD vs normal weight; rough lifetime µmt."),
    ("khan_2018", "obese-man-cvd",
     "Obese man (BMI 30-35, lifetime CVD excess)",
     150_000, ("lifestyle", "obesity", "cardiovascular"),
     "Hazard ratio 1.67 for CVD vs normal weight."),
    ("bhaskaran_2018", "sedentary-lifestyle",
     "Sedentary lifestyle (vs active, lifetime)",
     200_000, ("lifestyle", "exercise"),
     "Estimated ~2 years life-expectancy loss from never meeting activity guidelines."),
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
            risk_id = upsert_risk(
                conn,
                slug=f"life:{slug}",
                name=name,
                category="disease",
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
    print(f"lifestyle: ingested {ingest(conn)} entries.")
