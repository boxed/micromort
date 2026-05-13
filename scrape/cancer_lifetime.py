"""Lifetime cancer mortality risk by site (US).

Source: SEER Cancer Stat Facts (NCI) + American Cancer Society 'Cancer
Facts & Figures' annual reports. Lifetime risk-of-dying figures are the
absolute cumulative probability that a US resident will die from the
named cancer.
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_probability
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCE = dict(
    name="SEER + ACS — Cancer Facts & Figures (lifetime risks)",
    url="https://seer.cancer.gov/statfacts/html/common.html",
    publisher="NCI SEER / American Cancer Society",
)
YEAR = 2024

# (slug, name, lifetime mortality probability, tags)
# Combined lifetime cancer mortality is ~20%. Site-specific mortality from
# ACS/SEER period life tables.
ROWS = [
    ("any-cancer",      "Any cancer death (lifetime)",           0.197, ("cancer", "lifetime")),
    ("any-cancer-male", "Any cancer death (lifetime, male)",     0.216, ("cancer", "lifetime", "demographic")),
    ("any-cancer-female","Any cancer death (lifetime, female)",   0.181, ("cancer", "lifetime", "demographic")),
    ("lung",            "Lung & bronchus cancer (lifetime)",      0.061, ("cancer", "lifetime", "lung")),
    ("colorectal",      "Colorectal cancer (lifetime)",           0.018, ("cancer", "lifetime")),
    ("pancreas",        "Pancreatic cancer (lifetime)",           0.011, ("cancer", "lifetime")),
    ("breast-female",   "Breast cancer (lifetime, women)",        0.026, ("cancer", "lifetime", "demographic")),
    ("prostate-male",   "Prostate cancer (lifetime, men)",        0.025, ("cancer", "lifetime", "demographic")),
    ("liver",           "Liver cancer (lifetime)",                0.010, ("cancer", "lifetime")),
    ("leukemia",        "Leukemia (lifetime)",                    0.008, ("cancer", "lifetime")),
    ("brain",           "Brain & nervous-system cancer (lifetime)",0.005,("cancer", "lifetime", "neuro")),
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
                slug=f"cancer-life:{suffix}-us-{YEAR}",
                name=name,
                category="disease",
                micromorts=from_probability(p),
                exposure="lifetime",
                exposure_detail="Cumulative US lifetime probability of dying from this cancer site",
                population="US, both sexes" if "demographic" not in tags else None,
                region="US",
                year=YEAR,
                source_id=source_id,
                original_value=f"{p*100:.2f}% lifetime mortality risk",
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
    print(f"cancer lifetime: ingested {ingest(conn)} entries.")
