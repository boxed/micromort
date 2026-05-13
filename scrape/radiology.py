"""Medical imaging — per-scan cancer-mortality micromorts.

BEIR VII gives an excess cancer-mortality risk of roughly 5% per Sievert.
We convert published effective doses (mSv) to lifetime fatal-cancer risk:

    µmt(scan) = dose_mSv * 5%/Sv * 1e6
              = dose_mSv * 50

This is a crude population-average estimate (varies by age, sex, organ).

Sources: Smith-Bindman 2009 (Arch Intern Med), FDA radiation risk pages,
Harvard Health summary.
"""
from __future__ import annotations

import datetime as dt

from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCE = dict(
    name="Smith-Bindman et al. 2009 + FDA — CT radiation dose & cancer risk",
    url="https://www.fda.gov/radiation-emitting-products/medical-x-ray-imaging/what-are-radiation-risks-ct",
    publisher="US FDA / Smith-Bindman et al.",
)
MM_PER_MSV = 50.0  # 5% mortality per Sievert * 1e6 µmt/death

# (slug, name, dose_mSv, tags)
ROWS = [
    ("chest-xray",          "Chest X-ray (single)",                  0.1,  ("imaging",)),
    ("dental-xray",         "Dental X-ray (bitewing)",               0.005,("imaging",)),
    ("mammogram",           "Mammogram",                             0.4,  ("imaging", "screening")),
    ("ct-head",             "CT head (routine)",                     2.0,  ("imaging",)),
    ("ct-chest-low-dose",   "CT chest (low-dose lung screen)",       1.5,  ("imaging", "screening")),
    ("ct-chest-routine",    "CT chest (routine)",                    7.0,  ("imaging",)),
    ("ct-abdomen-pelvis",   "CT abdomen / pelvis",                   10.0, ("imaging",)),
    ("ct-abdomen-multi",    "CT abdomen / pelvis (multiphase)",      31.0, ("imaging",)),
    ("ct-coronary-angio",   "CT coronary angiography",               16.0, ("imaging", "cardiac")),
    ("pet-ct-whole-body",   "PET-CT whole body",                     25.0, ("imaging",)),
    ("transatlantic-flight","Transatlantic flight (cosmic ray dose)", 0.08,("aviation",)),
    ("us-background-year",  "US natural background radiation (1 year)", 3.1,("environmental", "natural")),
]


def _touch() -> bool:
    try:
        fetch(SOURCE["url"])
        return True
    except Exception:
        return False


def ingest(conn) -> int:
    alive = _touch()
    source_id = upsert_source(
        conn,
        accessed_at=dt.date.today().isoformat() if alive else None,
        **SOURCE,
    )
    n = 0
    with transaction(conn):
        for suffix, name, dose, tags in ROWS:
            mm = dose * MM_PER_MSV
            exposure = "per_year" if "year" in suffix else "per_event"
            risk_id = upsert_risk(
                conn,
                slug=f"rad:{suffix}",
                name=name,
                category="medical" if "imaging" in tags else "environmental",
                micromorts=mm,
                exposure=exposure,
                exposure_detail=f"Effective dose {dose} mSv → cancer-mortality estimate (BEIR VII).",
                source_id=source_id,
                original_value=f"{dose} mSv",
                original_unit="effective dose (mSv)",
                confidence="medium",
                notes="Derived using 5%/Sv mortality. Age-skewed; lower for elderly, higher for children.",
            )
            add_tags(conn, risk_id, list(tags) + ["radiation"])
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"radiology: ingested {ingest(conn)} entries.")
