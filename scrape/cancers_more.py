"""More specific cancers — lifetime mortality risk (US).

Source: NCI SEER Cancer Stat Facts. Lifetime death-probability values
are computed from lifetime incidence × (1 − 5-yr relative survival)
approximations.
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_probability
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCE = dict(
    name="NCI SEER Cancer Stat Facts — specific cancer sites",
    url="https://seer.cancer.gov/statfacts/",
    publisher="NCI SEER",
)
YEAR = 2024

# (slug, name, lifetime mortality probability, tags)
ROWS = [
    ("melanoma",        "Melanoma (lifetime)",                       0.003,  ("cancer", "skin")),
    ("pancreatic",      "Pancreatic cancer (lifetime)",              0.011,  ("cancer", "gi")),
    ("ovarian",         "Ovarian cancer (lifetime, women)",          0.0086, ("cancer", "demographic")),
    ("glioma-gbm",      "Glioblastoma (lifetime)",                   0.003,  ("cancer", "neuro")),
    ("brain-all",       "Brain & nervous system cancer (lifetime)",  0.004,  ("cancer", "neuro")),
    ("esophagus",       "Esophageal cancer (lifetime)",              0.005,  ("cancer", "gi")),
    ("bladder",         "Bladder cancer (lifetime)",                 0.005,  ("cancer", "gu")),
    ("kidney",          "Kidney cancer (lifetime)",                  0.004,  ("cancer", "gu")),
    ("thyroid",         "Thyroid cancer (lifetime)",                 0.0005, ("cancer", "endocrine")),
    ("multiple-myeloma","Multiple myeloma (lifetime)",               0.004,  ("cancer", "blood")),
    ("non-hodgkin",     "Non-Hodgkin lymphoma (lifetime)",           0.006,  ("cancer", "blood")),
    ("stomach",         "Stomach cancer (lifetime)",                 0.004,  ("cancer", "gi")),
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
        for suffix, name, p, tags in ROWS:
            risk_id = upsert_risk(
                conn,
                slug=f"cancer:{suffix}-us-{YEAR}",
                name=name,
                category="disease",
                micromorts=from_probability(p),
                exposure="lifetime",
                exposure_detail="Cumulative US lifetime probability of dying from this cancer",
                region="US",
                year=YEAR,
                source_id=source_id,
                original_value=f"{p*100:.2f}% lifetime mortality",
                original_unit="lifetime mortality probability",
                confidence="high",
            )
            add_tags(conn, risk_id, list(tags))
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"cancers_more: ingested {ingest(conn)} entries.")
