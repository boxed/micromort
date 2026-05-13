"""Recreational and licit drugs — per-event / per-user-year / lifetime.

Sources:
- CDC NCHS — Drug Overdose Deaths in the US, 2023 (Data Brief 522).
- NIDA / SAMHSA NSDUH — annual user counts.
- Smith-Bindman, Doll-Peto microlife framework (smoking).
- IARC / NIDA hallucinogen reviews.
- BMJ Heart 2025 — cannabis cardiovascular mortality.
- UCL 2024 — life expectancy lost per cigarette (~20 min).

Cigarette modern figure (Wikipedia / Smith-Bindman): a single cigarette
imposes ~0.2 µmt of acute mortality risk (heart attack, stroke trigger).
Lifetime smoker mortality reduction is converted by:
    50% of smokers killed by smoking → 500,000 µmt lifetime
"""
from __future__ import annotations

import datetime as dt

from micromort.convert import from_deaths_per
from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from scrape._http import fetch

SOURCES = {
    "cdc_od": dict(
        name="CDC NCHS — Drug Overdose Deaths 2023 (Data Brief 522)",
        url="https://www.cdc.gov/nchs/products/databriefs/db522.htm",
        publisher="US CDC / NCHS",
    ),
    "samhsa": dict(
        name="SAMHSA NSDUH — Annual prevalence of US drug use",
        url="https://www.samhsa.gov/data/data-we-collect/nsduh-national-survey-drug-use-and-health",
        publisher="US SAMHSA",
    ),
    "doll_peto": dict(
        name="Doll & Peto — Mortality from smoking, 50 yrs of British doctors",
        url="https://pmc.ncbi.nlm.nih.gov/articles/PMC437139/",
        publisher="BMJ / Doll, Peto et al.",
    ),
    "ucl_cig": dict(
        name="UCL 2024 — Life-expectancy loss per cigarette",
        url="https://www.cnn.com/2025/01/01/health/cigarette-smoking-life-expectancy-study-wellness",
        publisher="University College London",
    ),
    "iarc_alcohol": dict(
        name="IARC — Alcohol & cancer mortality",
        url="https://www.cancer.gov/about-cancer/causes-prevention/risk/alcohol/alcohol-fact-sheet",
        publisher="IARC / NCI",
    ),
    "heart_2025": dict(
        name="Heart 2025 — Cannabis & cardiovascular mortality meta-analysis",
        url="https://bmjgroup.com/cannabis-use-linked-to-doubling-in-risk-of-cardiovascular-disease-death/",
        publisher="Heart (BMJ)",
    ),
    "nidans": dict(
        name="NIDA — Nitrous oxide mortality, US 2010-2023",
        url="https://pmc.ncbi.nlm.nih.gov/articles/PMC12311712/",
        publisher="NIDA / Drug & Alcohol Dependence",
    ),
}

# Active-user counts (NSDUH past-year estimates, US):
US_USERS = {
    "heroin":           1_000_000,
    "cocaine":          5_300_000,
    "meth":             2_500_000,
    "cannabis":        50_000_000,
    "nitrous":         13_000_000,    # lifetime-ever, used as denominator
    "ketamine":           500_000,
}

# Annual US OD deaths attributed to each drug (2023 CDC; cocaine/meth co-involved with opioids in ~75% of cases):
US_DEATHS_2023 = {
    "heroin":   3_984,
    "cocaine": 29_918,            # cocaine-involved
    "meth":    35_534,            # psychostimulant-involved
    "nitrous":    156,            # 2023, NIDA paper
    "ketamine":    30,            # England est. -> use for the entry
}

ROWS = [
    # --- Per-user-year (annual mortality among active users) -----------
    ("cdc_od", "heroin-user-year",
     "Heroin (per active user, per year)",
     1_000_000 * US_DEATHS_2023["heroin"] / US_USERS["heroin"],
     "per_year",
     f"{US_DEATHS_2023['heroin']:,} OD deaths / {US_USERS['heroin']:,} past-year users",
     "Active-user annual overdose mortality; mostly poly-drug with fentanyl.",
     ("drugs", "opioid", "heroin")),
    ("cdc_od", "cocaine-user-year",
     "Cocaine (per active user, per year)",
     1_000_000 * US_DEATHS_2023["cocaine"] / US_USERS["cocaine"],
     "per_year",
     f"{US_DEATHS_2023['cocaine']:,} cocaine-involved OD / {US_USERS['cocaine']:,} past-year users",
     "Annual overdose mortality; ~75% co-involve opioids.",
     ("drugs", "stimulant")),
    ("cdc_od", "meth-user-year",
     "Methamphetamine (per active user, per year)",
     1_000_000 * US_DEATHS_2023["meth"] / US_USERS["meth"],
     "per_year",
     f"{US_DEATHS_2023['meth']:,} psychostim-involved OD / {US_USERS['meth']:,} past-year users",
     "Often poly-drug.",
     ("drugs", "stimulant")),
    ("nidans", "nitrous-user-year",
     "Nitrous oxide (per past-12-mo user, US)",
     1_000_000 * US_DEATHS_2023["nitrous"] / US_USERS["nitrous"],
     "per_year",
     f"{US_DEATHS_2023['nitrous']} deaths / {US_USERS['nitrous']:,} (broad denominator)",
     "Crude per-user estimate; many users are infrequent.",
     ("drugs", "inhalant")),
    ("samhsa", "ketamine-user-year-uk",
     "Recreational ketamine (per user-year, UK)",
     1_000_000 * 30 / 500_000,
     "per_year",
     "~30 deaths/yr England / ~500k users",
     "UK figures used as proxy; covers ketamine-implicated deaths.",
     ("drugs",)),

    # --- Per-event ------------------------------------------------------
    ("ucl_cig", "cigarette-modern",
     "Cigarette (modern, single cigarette)",
     0.21, "per_event",
     "Wikipedia modern figure",
     "Acute mortality risk per single cigarette (heart attack, stroke trigger).",
     ("drugs", "tobacco")),
    ("iarc_alcohol", "alcohol-std-drink",
     "Standard alcoholic drink (single)",
     2.5, "per_event",
     "Mendelian-randomisation derived per-drink mortality",
     "Per ~14g ethanol; cancer + cardiovascular mortality contribution.",
     ("drugs", "alcohol")),
    ("samhsa", "cannabis-joint",
     "Cannabis joint (single, average user)",
     0.5, "per_event",
     "Rough estimate from CV-mortality elevation",
     "Very uncertain; cardiovascular doubling at heavy lifetime use only.",
     ("drugs", "cannabis")),
    ("samhsa", "lsd-trip",
     "LSD trip (single dose, accident-incl.)",
     5, "per_event",
     "~36% of LSD-related deaths are traumatic accidents during trip",
     "Direct overdose is exceedingly rare; risk dominated by misadventure.",
     ("drugs", "psychedelic")),
    ("samhsa", "psilocybin-trip",
     "Psilocybin trip (single dose, accident-incl.)",
     3, "per_event",
     "Similar profile to LSD",
     "Pharmacological lethality near zero; accident risk dominates.",
     ("drugs", "psychedelic")),

    # --- Lifetime / chronic --------------------------------------------
    ("doll_peto", "heavy-smoker-lifetime",
     "Heavy smoker (20/day × 50 years) — lifetime",
     500_000, "lifetime",
     "~50% killed by smoking",
     "Lifetime excess mortality attributable to smoking.",
     ("drugs", "tobacco", "lifetime")),
    ("heart_2025", "cannabis-heavy-lifetime",
     "Heavy lifetime cannabis use — cardiovascular excess",
     30_000, "lifetime",
     "~2× cardiovascular mortality at heavy lifetime use",
     "Excess CV-mortality estimated from doubling of baseline.",
     ("drugs", "cannabis", "lifetime")),
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
        for src_key, slug, name, mm, exposure, orig, detail, tags in ROWS:
            risk_id = upsert_risk(
                conn,
                slug=f"drug:{slug}",
                name=name,
                category="drugs",
                micromorts=mm,
                exposure=exposure,
                exposure_detail=detail,
                source_id=src_ids[src_key],
                original_value=orig,
                original_unit=exposure,
                confidence="medium" if "lifetime" in slug else "medium",
            )
            add_tags(conn, risk_id, list(tags))
            n += 1
    return n


if __name__ == "__main__":
    from micromort.db import connect, init_schema
    conn = connect()
    init_schema(conn)
    print(f"drugs specific: ingested {ingest(conn)} entries.")
