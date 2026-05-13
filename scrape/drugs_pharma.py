"""Pharmaceutical drug overdose & related mortality.

Sources:
- StatPearls — Acetaminophen toxicity epidemiology.
- CDC NCHS — Benzodiazepine-involved overdose deaths.
- DEA / NIDA — Fentanyl per-dose toxicity references.
"""
from __future__ import annotations

import datetime as dt

from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCES = {
    "statpearls_apap": dict(
        name="StatPearls — Acetaminophen Toxicity",
        url="https://www.ncbi.nlm.nih.gov/books/NBK441917/",
        publisher="StatPearls",
    ),
    "cdc_benzo": dict(
        name="CDC NCHS — Benzodiazepine overdose deaths",
        url="https://www.cdc.gov/nchs/data/nvsr/nvsr67/nvsr67_09-508.pdf",
        publisher="US CDC NCHS",
    ),
    "nida_fent": dict(
        name="NIDA — Fentanyl & synthetic opioid overdose trends",
        url="https://nida.nih.gov/research-topics/trends-statistics/overdose-death-rates",
        publisher="NIH NIDA",
    ),
}
US_POP = 334_900_000

ROWS = [
    # source, slug, name, micromorts (per unit), exposure, tags, note
    ("statpearls_apap", "acetaminophen-overdose-us-year",
     "Acetaminophen / paracetamol overdose (US, per resident-year)",
     1_000_000 * 500 / US_POP, "per_year",
     ("drugs", "pharmaceutical"),
     "≈500 US deaths/yr (50% unintentional)."),
    ("cdc_benzo", "benzo-od-us-year",
     "Benzodiazepine-involved overdose (US, per resident-year)",
     1_000_000 * 12_000 / US_POP, "per_year",
     ("drugs", "pharmaceutical", "depressant"),
     "~12,000 benzo-involved overdose deaths/yr in recent CDC data."),
    ("nida_fent", "fentanyl-od-us-year",
     "Fentanyl / synthetic opioid overdose (US, per resident-year)",
     1_000_000 * 72_776 / US_POP, "per_year",
     ("drugs", "pharmaceutical", "opioid"),
     "72,776 synthetic-opioid overdose deaths in 2023 (CDC)."),
    ("statpearls_apap", "acetaminophen-single-dose-10g",
     "Acute acetaminophen ingestion ≥10g (per event, untreated)",
     200_000, "per_event",
     ("drugs", "pharmaceutical"),
     "Without treatment >10 g ingestion causes severe hepatic toxicity in ~20% of adults."),
    ("nida_fent", "illicit-fentanyl-dose",
     "Illicit fentanyl (single street dose, opioid-naive)",
     30_000, "per_event",
     ("drugs", "opioid", "fentanyl"),
     "Crude estimate: ~3% mortality per illicit dose in opioid-naive users."),
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
                slug=f"pharma:{slug}",
                name=name,
                category="drugs",
                micromorts=mm,
                exposure=exposure,
                exposure_detail=note,
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
    print(f"drugs_pharma: ingested {ingest(conn)} entries.")
