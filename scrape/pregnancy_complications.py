"""Pregnancy-related complications — per-event and per-pregnancy.

Sources:
- CDC NCHS — Maternal mortality data.
- ACOG, Preeclampsia Foundation, CDC MMWR ectopic-pregnancy surveillance.
"""
from __future__ import annotations

import datetime as dt

from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCES = {
    "cdc_mat": dict(
        name="CDC NCHS — Maternal Mortality 2020 (US)",
        url="https://www.cdc.gov/nchs/maternal-mortality/index.htm",
        publisher="US CDC / NCHS",
    ),
    "cdc_ectopic": dict(
        name="CDC MMWR — Ectopic Pregnancy Surveillance",
        url="https://www.cdc.gov/mmwr/preview/mmwrhtml/00031632.htm",
        publisher="US CDC MMWR",
    ),
    "preeclampsia": dict(
        name="Preeclampsia Foundation — Maternal Burden Facts",
        url="https://www.preeclampsia.org/the-news/legislative-advocacy/preeclampsia-and-maternal-mortality-a-global-burden",
        publisher="Preeclampsia Foundation",
    ),
}

ROWS = [
    # source, slug, name, micromorts, exposure, tags, note
    ("cdc_mat", "maternal-us-2020",
     "Maternal death (US, 2020, per pregnancy)",
     1_000_000 * 23.8 / 100_000, "per_event",
     ("pregnancy", "maternal"),
     "23.8 maternal deaths per 100k live births (2020)."),
    ("cdc_mat", "maternal-us-black-2020",
     "Maternal death (US Black women, per pregnancy)",
     1_000_000 * 55.3 / 100_000, "per_event",
     ("pregnancy", "maternal", "demographic"),
     "55.3/100k live births — 2.3× US average."),
    ("cdc_ectopic", "ectopic-pregnancy-case-fatality",
     "Ectopic pregnancy (per case, US)",
     1_000_000 * 0.0003, "per_event",
     ("pregnancy", "complication"),
     "~30 deaths per 100k ectopic pregnancies (modern US)."),
    ("preeclampsia", "preeclampsia-case-fatality",
     "Severe pre-eclampsia / eclampsia (per case, US)",
     1_000_000 * 0.002, "per_event",
     ("pregnancy", "complication"),
     "Approx 0.2% case-fatality with modern care (much higher historically)."),
    ("preeclampsia", "abortion-induced-us",
     "Induced abortion (US, per procedure)",
     1_000_000 * 0.6 / 100_000, "per_event",
     ("pregnancy", "procedure"),
     "Legal induced abortion mortality, CDC long-run average."),
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
        for src_key, slug, name, mm, exposure, tags, note in ROWS:
            risk_id = upsert_risk(
                conn,
                slug=f"preg:{slug}",
                name=name,
                category="medical",
                micromorts=mm,
                exposure=exposure,
                exposure_detail=note,
                region="US",
                source_id=src_ids[src_key],
                original_value=note,
                original_unit=exposure,
                confidence="medium",
            )
            add_tags(conn, risk_id, list(tags))
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"pregnancy_complications: ingested {ingest(conn)} entries.")
