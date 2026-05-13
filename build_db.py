"""Build risks.db from scratch: schema → seed → all scrapers.

Run:
    python build_db.py            # rebuild fresh DB
    python build_db.py --no-scrape  # seed only (offline)
"""
from __future__ import annotations

import argparse
from pathlib import Path

from micromort.db import DB_PATH, connect, init_schema
from scrape import (
    aviation_general,
    bls_cfoi,
    cancer_lifetime,
    cardiac,
    cardiac_events_extra,
    child_mortality,
    combat_sports,
    drugs_specific,
    animals_global,
    asbestos,
    cancers_more,
    chronic_diseases,
    diarrheal_global,
    drugs_pharma,
    endurance_sports,
    hemorrhagic_viruses,
    environmental_extra,
    environmental_more,
    extreme_more,
    first_responders,
    historical_disasters,
    infections,
    lifestyle,
    medical_misc,
    road_global,
    food_specific,
    foodborne,
    global_health,
    outdoor_recreation,
    pregnancy_complications,
    transport_extra,
    who_suicide,
    cdc_causes,
    cdc_choking,
    cdc_falls,
    cdc_firearms,
    cdc_hazards,
    cdc_life_table,
    cdc_overdose,
    cdc_weather,
    climbing,
    dan_diving,
    extreme_reference,
    hiv_exposure,
    iata,
    medical_procedures,
    military,
    nhtsa,
    nps_parks,
    nsaa_skiing,
    radiology,
    space_extra,
    spaceflight,
    surgery_extra,
    unodc_homicide,
    vaccines,
    venomous,
    who_maternal,
    wikipedia_micromort,
    wingsuit,
)
from seed.load import load as load_seed

SCRAPERS = [
    ("wikipedia_micromort", wikipedia_micromort.ingest),
    ("nhtsa", nhtsa.ingest),
    ("cdc_causes", cdc_causes.ingest),
    ("bls_cfoi", bls_cfoi.ingest),
    ("cdc_life_table", cdc_life_table.ingest),
    ("iata", iata.ingest),
    ("cdc_firearms", cdc_firearms.ingest),
    ("cdc_overdose", cdc_overdose.ingest),
    ("dan_diving", dan_diving.ingest),
    ("nps_parks", nps_parks.ingest),
    ("who_maternal", who_maternal.ingest),
    ("cdc_hazards", cdc_hazards.ingest),
    ("medical_procedures", medical_procedures.ingest),
    ("extreme_reference", extreme_reference.ingest),
    ("spaceflight", spaceflight.ingest),
    ("space_extra", space_extra.ingest),
    ("aviation_general", aviation_general.ingest),
    ("climbing", climbing.ingest),
    ("wingsuit", wingsuit.ingest),
    ("nsaa_skiing", nsaa_skiing.ingest),
    ("unodc_homicide", unodc_homicide.ingest),
    ("military", military.ingest),
    ("radiology", radiology.ingest),
    ("surgery_extra", surgery_extra.ingest),
    ("vaccines", vaccines.ingest),
    ("cardiac", cardiac.ingest),
    ("cdc_falls", cdc_falls.ingest),
    ("venomous", venomous.ingest),
    ("hiv_exposure", hiv_exposure.ingest),
    ("cdc_weather", cdc_weather.ingest),
    ("cdc_choking", cdc_choking.ingest),
    ("foodborne", foodborne.ingest),
    ("food_specific", food_specific.ingest),
    ("drugs_specific", drugs_specific.ingest),
    ("combat_sports", combat_sports.ingest),
    ("who_suicide", who_suicide.ingest),
    ("cancer_lifetime", cancer_lifetime.ingest),
    ("global_health", global_health.ingest),
    ("child_mortality", child_mortality.ingest),
    ("transport_extra", transport_extra.ingest),
    ("outdoor_recreation", outdoor_recreation.ingest),
    ("environmental_extra", environmental_extra.ingest),
    ("first_responders", first_responders.ingest),
    ("cardiac_events_extra", cardiac_events_extra.ingest),
    ("pregnancy_complications", pregnancy_complications.ingest),
    ("infections", infections.ingest),
    ("historical_disasters", historical_disasters.ingest),
    ("environmental_more", environmental_more.ingest),
    ("medical_misc", medical_misc.ingest),
    ("animals_global", animals_global.ingest),
    ("road_global", road_global.ingest),
    ("cancers_more", cancers_more.ingest),
    ("lifestyle", lifestyle.ingest),
    ("extreme_more", extreme_more.ingest),
    ("drugs_pharma", drugs_pharma.ingest),
    ("hemorrhagic_viruses", hemorrhagic_viruses.ingest),
    ("chronic_diseases", chronic_diseases.ingest),
    ("diarrheal_global", diarrheal_global.ingest),
    ("asbestos", asbestos.ingest),
    ("endurance_sports", endurance_sports.ingest),
]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-scrape", action="store_true", help="Seed only, skip scrapers")
    ap.add_argument("--fresh", action="store_true", help="Delete existing DB first")
    args = ap.parse_args()

    if args.fresh and DB_PATH.exists():
        DB_PATH.unlink()
        print(f"removed {DB_PATH}")

    conn = connect()
    init_schema(conn)

    n_seed = load_seed(conn)
    print(f"seed: {n_seed} risks")

    total = n_seed
    if not args.no_scrape:
        for name, fn in SCRAPERS:
            try:
                n = fn(conn)
                print(f"{name}: {n} risks")
                total += n
            except Exception as exc:  # one scraper failing shouldn't sink the build
                print(f"{name}: FAILED ({exc.__class__.__name__}: {exc})")

    n_all = conn.execute("SELECT COUNT(*) AS c FROM risks").fetchone()["c"]
    print(f"\nrisks rows now in DB: {n_all}")
    print(f"DB at: {DB_PATH}")


if __name__ == "__main__":
    main()
