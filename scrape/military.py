"""US military service — annualized fatality rates.

Sources:
- Non-hostile mortality rate, Iraq 2003-2007: 81.5 per 100,000 troop-years.
- Active-duty peacetime mortality 1997-2000: 53.0 per 100,000 troop-years.
- Total Afghanistan deaths 2001-2021: 2,402 across roughly 800,000
  cumulative deployed person-years (rough overall rate ≈ 300/100k/yr while
  forward-deployed).
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_rate_per_100k
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCE = dict(
    name="Belmont et al. 2014 + DCAS — US military mortality rates",
    url="https://pubmed.ncbi.nlm.nih.gov/34238813/",
    publisher="DoD / Costs of War project",
)

ROWS = [
    ("us-mil-peacetime-97-00",  "US military, active duty, peacetime (1997-2000)",  53.0, 2000,
     "Active-duty peacetime mortality."),
    ("us-mil-iraq-nonhostile",  "US military, Iraq theatre, non-hostile (2003-07)",  81.5, 2005,
     "Non-hostile deaths only; combat deaths additional."),
    ("us-mil-iraq-overall",     "US military, Iraq theatre, all causes (2003-07)",  386.0, 2005,
     "Approx. combined hostile+non-hostile rate for deployed force."),
    ("us-mil-afghanistan-overall","US military, Afghanistan theatre, all causes (2001-14)", 300.0, 2010,
     "Approx. deployed-force annualised mortality across war."),
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
        for suffix, name, rate, year, note in ROWS:
            risk_id = upsert_risk(
                conn,
                slug=f"mil:{suffix}",
                name=name,
                category="occupation",
                micromorts=from_rate_per_100k(rate),
                exposure="per_year",
                exposure_detail=note,
                region="US",
                year=year,
                source_id=source_id,
                original_value=f"{rate}/100,000 troop-years",
                original_unit="deaths per 100k troop-years",
                confidence="medium",
            )
            add_tags(conn, risk_id, ["military", "occupation"])
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"military: ingested {ingest(conn)} entries.")
