"""First-responder occupational mortality (US): police + firefighter.

Sources:
- NLEOMF (Officer Down Memorial Page).
- USFA — Firefighter Fatalities in the US (annual).
- Ruderman Family Foundation — First-responder suicide rates.
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_rate_per_100k
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCES = {
    "usfa": dict(
        name="USFA — Annual Firefighter Fatalities Report",
        url="https://www.usfa.fema.gov/statistics/reports/firefighters-departments/firefighter-fatalities.html",
        publisher="US Fire Administration",
    ),
    "bls_cfoi": dict(
        name="BLS CFOI — Police & firefighter occupational mortality",
        url="https://www.bls.gov/iif/oshcfoi1.htm",
        publisher="US Bureau of Labor Statistics",
    ),
    "ruderman": dict(
        name="Ruderman White Paper — First responder mental health & suicide",
        url="https://rudermanfoundation.org/white_papers/police-officers-and-firefighters-are-more-likely-to-die-by-suicide-than-in-line-of-duty/",
        publisher="Ruderman Family Foundation",
    ),
}

ROWS = [
    # source, slug, name, rate/100k, exposure, tags, note
    ("bls_cfoi", "police-officer-line-of-duty",
     "Police officer (line-of-duty, US, per FTE year)",
     14.0, "per_year",
     ("occupation", "police"),
     "Long-run average; combines hostile + non-hostile on-duty deaths."),
    ("usfa", "firefighter-line-of-duty",
     "Firefighter (line-of-duty, US, per FTE year)",
     13.0, "per_year",
     ("occupation", "firefighter"),
     "Long-run average; includes career + volunteer."),
    ("ruderman", "police-suicide",
     "Police officer suicide (US, per FTE year)",
     17.0, "per_year",
     ("occupation", "police", "suicide"),
     "Suicide mortality slightly above line-of-duty rate."),
    ("ruderman", "firefighter-suicide",
     "Firefighter suicide (US, per FTE year)",
     18.0, "per_year",
     ("occupation", "firefighter", "suicide"),
     "Suicide mortality exceeds line-of-duty rate."),
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
        for src_key, slug, name, rate, exposure, tags, note in ROWS:
            risk_id = upsert_risk(
                conn,
                slug=f"resp:{slug}",
                name=name,
                category="occupation",
                micromorts=from_rate_per_100k(rate),
                exposure=exposure,
                exposure_detail=note,
                region="US",
                source_id=src_ids[src_key],
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
    print(f"first_responders: ingested {ingest(conn)} entries.")
