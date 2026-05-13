"""Reference points used to anchor the upper end of the micromort scale.

Russian roulette is the canonical 'unambiguously fatal-game' anchor. We
also include horseback-riding annualized rate and a few motorsport
historical reference points.
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_deaths_per, from_one_in
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCES = {
    "wiki_rr": dict(
        name="Wikipedia — Russian roulette",
        url="https://en.wikipedia.org/wiki/Russian_roulette",
        publisher="Wikipedia",
    ),
    "horse": dict(
        name="Equestrian Injury Statistics (Ohio State Extension)",
        url="https://ohioline.osu.edu/factsheet/19",
        publisher="The Ohio State University Extension",
    ),
}

ROWS = [
    # source_key, slug, name, category, micromorts, exposure, original, detail, tags
    ("wiki_rr",
     "russian-roulette",
     "Russian roulette (one pull, 6-chamber revolver)",
     "activity", from_one_in(6), "per_event",
     "1/6", "Single trigger pull, one bullet in six chambers — anchors the top of the scale.",
     ("anchor", "reference")),
    ("horse",
     "horse-riding-rider-year",
     "Horseback riding (per rider, per year)",
     "activity", from_one_in(10_000), "per_year",
     "~1 in 10,000 riders/year",
     "Cited risk to active riders. Head/neck injuries dominate.",
     ("equestrian", "outdoor")),
    ("horse",
     "horse-riding-serious-injury-1k-hours",
     "Horseback riding (serious injury per 1,000 hours)",
     "activity", from_deaths_per(1, 350) * 0,  # placeholder — kept for shape
     "per_hour",
     "serious injury ~1 in 350 h",
     "(Listed as serious injury rate, not fatality — use as ceiling.)",
     ("equestrian", "outdoor", "injury-only")),
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
        # The "serious-injury" row is not a fatality, so we exclude it from the DB.
        for src_key, slug, name, cat, mm, exposure, orig, detail, tags in ROWS:
            if "injury-only" in tags:
                continue
            risk_id = upsert_risk(
                conn,
                slug=f"ref:{slug}",
                name=name,
                category=cat,
                micromorts=mm,
                exposure=exposure,
                exposure_detail=detail,
                source_id=src_ids[src_key],
                original_value=orig,
                original_unit=exposure.replace("_", " "),
                confidence="medium" if "anchor" not in tags else "high",
            )
            add_tags(conn, risk_id, list(tags))
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"extreme reference: ingested {ingest(conn)} entries.")
