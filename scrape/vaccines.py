"""Vaccine adverse-event mortality — per dose.

Sources: ACIP statements, CDC Pink Book, Yellow Book.
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_deaths_per
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCE = dict(
    name="CDC ACIP / Yellow Book — Vaccine adverse-event background rates",
    url="https://www.cdc.gov/yellow-book/hcp/preparing-international-travelers/vaccination-and-immunoprophylaxis-general-principles.html",
    publisher="US CDC",
)

# (slug, name, deaths, per_n, tags, note)
ROWS = [
    ("smallpox-first",  "Smallpox vaccine (primary dose)",   1, 1_000_000, ("vaccine", "historical"),
     "~1 death per million primary recipients."),
    ("smallpox-revacc", "Smallpox vaccine (revaccination)",  1, 4_000_000, ("vaccine", "historical"),
     "~1 death per 4 million in revaccinated."),
    ("yellow-fever",    "Yellow fever vaccine (any dose)",   1, 250_000, ("vaccine", "travel"),
     "Yellow fever vaccine-associated viscerotropic / neurologic disease, ~1/250k."),
    ("yellow-fever-60", "Yellow fever vaccine (age 60+)",    1, 100_000, ("vaccine", "travel"),
     "Risk elevated in adults ≥60 (estimated ~1/100k)."),
    ("astrazeneca-vax", "AstraZeneca COVID-19 (per dose)",   2.9, 1_000_000, ("vaccine", "covid"),
     "Thrombotic events; matches Wikipedia table entry."),
    ("mmr",             "MMR vaccine",                       1, 1_000_000, ("vaccine",),
     "Severe allergic reaction mortality, conservative upper bound."),
    ("flu-vaccine",     "Influenza vaccine (inactivated)",   1, 10_000_000, ("vaccine",),
     "Anaphylaxis-related mortality is exceedingly rare."),
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
        for suffix, name, deaths, per_n, tags, note in ROWS:
            risk_id = upsert_risk(
                conn,
                slug=f"vax:{suffix}",
                name=name,
                category="medical",
                micromorts=from_deaths_per(deaths, per_n),
                exposure="per_event",
                exposure_detail=note,
                source_id=source_id,
                original_value=f"{deaths}/{per_n:,}",
                original_unit="deaths per dose",
                confidence="medium",
            )
            add_tags(conn, risk_id, list(tags))
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"vaccines: ingested {ingest(conn)} entries.")
