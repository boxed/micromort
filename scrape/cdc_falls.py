"""Falls in older adults — per-year micromorts by age band.

Source: CDC NCHS Data Brief 532, 'Unintentional Fall Deaths in Adults Aged
65 and Older' (2023 data).
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_rate_per_100k
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCE = dict(
    name="CDC NCHS Data Brief 532 — Fall deaths, US adults 65+ (2023)",
    url="https://www.cdc.gov/nchs/products/databriefs/db532.htm",
    publisher="US CDC / NCHS",
)
YEAR = 2023

# (slug, name, rate/100k, demographic, tags)
ROWS = [
    ("falls-65plus-all",       "Fatal fall, age 65+ (US)",              69.9, "all 65+ adults",      ("falls", "elderly")),
    ("falls-65plus-men",       "Fatal fall, age 65+ men (US)",          74.2, "men 65+",             ("falls", "elderly", "demographic")),
    ("falls-65plus-women",     "Fatal fall, age 65+ women (US)",        66.3, "women 65+",           ("falls", "elderly", "demographic")),
    ("falls-65-74-men",        "Fatal fall, men 65-74 (US)",            24.7, "men 65-74",           ("falls", "elderly", "demographic")),
    ("falls-65-74-women",      "Fatal fall, women 65-74 (US)",          14.2, "women 65-74",         ("falls", "elderly", "demographic")),
    ("falls-85plus-men",       "Fatal fall, men 85+ (US)",             373.3, "men 85+",             ("falls", "elderly", "demographic")),
    ("falls-85plus-women",     "Fatal fall, women 85+ (US)",           319.7, "women 85+",           ("falls", "elderly", "demographic")),
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
        for suffix, name, rate, demo, tags in ROWS:
            risk_id = upsert_risk(
                conn,
                slug=f"falls:{suffix}",
                name=name,
                category="environmental",
                micromorts=from_rate_per_100k(rate),
                exposure="per_year",
                exposure_detail=f"Unintentional fall fatality rate, {demo}",
                population=demo,
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
    print(f"CDC falls: ingested {ingest(conn)} entries.")
