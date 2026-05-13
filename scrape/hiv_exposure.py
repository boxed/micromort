"""HIV transmission risk per exposure event.

These are transmission-probability figures, NOT death rates. We treat
acquisition of HIV from a single exposure as an event whose probability
× modern long-term mortality (variable, often near baseline on ART) is
hard to express as a single micromort number. We record the *transmission*
probability as the event's risk for now, with a clear note in `notes`.

Sources: CDC HIV transmission risk estimates; aidsmap occupational
exposure summary.
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_probability
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCE = dict(
    name="CDC — HIV transmission risk per exposure (occupational + sexual)",
    url="https://www.cdc.gov/hiv/causes/occupational-transmission.html",
    publisher="US CDC",
)
NOTES = (
    "Values are HIV-acquisition probability, NOT death probability. "
    "Modern ART makes long-term mortality near baseline; treat as "
    "upper-bound 'event seriousness' rather than direct micromorts."
)

ROWS = [
    ("needlestick",          "Needle stick from HIV+ source",       0.003,   ("hiv", "occupational")),
    ("receptive-anal",       "Unprotected receptive anal sex",       0.0138, ("hiv", "sexual")),
    ("insertive-anal",       "Unprotected insertive anal sex",       0.0011, ("hiv", "sexual")),
    ("receptive-vaginal",    "Unprotected receptive vaginal sex",    0.0008, ("hiv", "sexual")),
    ("insertive-vaginal",    "Unprotected insertive vaginal sex",    0.0004, ("hiv", "sexual")),
    ("shared-needle",        "Sharing injecting equipment",          0.0063, ("hiv", "drug-use")),
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
                slug=f"hiv:{suffix}",
                name=name,
                category="disease",
                micromorts=from_probability(p),
                exposure="per_event",
                exposure_detail="HIV-acquisition probability per exposure (no PrEP/PEP).",
                source_id=source_id,
                original_value=f"{p*100:.3f}%",
                original_unit="HIV-acquisition probability per act",
                confidence="medium",
                notes=NOTES,
            )
            add_tags(conn, risk_id, list(tags) + ["transmission-not-mortality"])
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"HIV exposure: ingested {ingest(conn)} entries.")
