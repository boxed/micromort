"""US drug overdose deaths — per-year micromorts.

Source: CDC NCHS Data Brief No. 522 (2024), "Drug Overdose Deaths in the
United States, 2003-2023". Age-adjusted rates per 100,000 standard pop.
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_rate_per_100k
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCE = dict(
    name="CDC NCHS — Drug Overdose Deaths, 2023 (Data Brief 522)",
    url="https://www.cdc.gov/nchs/products/databriefs/db522.htm",
    publisher="US CDC / NCHS",
)
YEAR = 2023

# Age-adjusted rates per 100k. Synthetic-opioid figure derived from
# 72,776 deaths / age-adjusted standard pop ≈ 22.1/100k.
ROWS = [
    ("overdose-total",         "Drug overdose death (all)",            31.3, ("drugs",)),
    ("overdose-synth-opioids", "Synthetic-opioid overdose (mainly fentanyl)", 22.1, ("drugs", "opioids")),
    ("overdose-cocaine",       "Cocaine overdose",                      8.6, ("drugs", "stimulants")),
    ("overdose-heroin",        "Heroin overdose",                       1.2, ("drugs", "opioids")),
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
        for suffix, name, rate, tags in ROWS:
            risk_id = upsert_risk(
                conn,
                slug=f"cdc:{suffix}-us-{YEAR}",
                name=f"{name} (US, {YEAR})",
                category="disease",
                micromorts=from_rate_per_100k(rate),
                exposure="per_year",
                exposure_detail="Age-adjusted US mortality, 2023",
                population="US, age-adjusted",
                region="US",
                year=YEAR,
                source_id=source_id,
                original_value=f"{rate}/100,000/year",
                original_unit="deaths per 100k per year",
                confidence="high",
            )
            add_tags(conn, risk_id, list(tags))
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"CDC overdose: ingested {ingest(conn)} entries.")
