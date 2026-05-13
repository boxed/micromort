# micromort

A database + visualization of mortality risks, every entry normalized to
**micromorts** (1 µmt = a one-in-a-million chance of death).

```
seed/         curated, well-attested values (Howard 1979, Wikipedia table, ...)
scrape/       fetchers for live sources (Wikipedia, NHTSA, CDC NCHS, BLS CFOI, …)
micromort/    shared library: SQLite helpers + conversion utilities
src/Main.elm  Elm 0.19 frontend (consumes data.json)
index.html    entry point — deployable as-is to GitHub Pages / any static host
schema.sql    SQLite schema
build_db.py   pipeline: schema → seed → scrapers → risks.db
export.py     risks.db → data.json
```

The frontend is fully static. The repo root *is* the deployable bundle —
push to GitHub Pages from the root of `main` (or any branch you point Pages
at) and it serves directly. `index.html`, `elm.js`, `style.css`, and
`data.json` are the four files actually needed at runtime.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

Frontend needs Elm 0.19.1: `brew install elm`.

## Build

```bash
scripts/build.sh           # rebuild DB, re-export JSON, recompile Elm
scripts/serve.sh           # serve repo root on http://localhost:8765
```

Or step-by-step:

```bash
.venv/bin/python build_db.py --fresh   # write risks.db
.venv/bin/python export.py             # emit data.json
elm make src/Main.elm --optimize --output=elm.js
```

## How risks are normalized

Every row in `risks` is a single `(micromorts, exposure)` pair plus the
context that pins it down (population, year, region). Original phrasings
are preserved in `original_value` / `original_unit`. Conversion helpers
live in `micromort/convert.py`:

- `from_one_in(N)` — "1 in N" probability
- `from_probability(p)` / `from_percent(pct)`
- `from_deaths_per(deaths, exposures)`
- `from_rate_per_100k(rate)` — CDC/WHO style annual rate
- `hourly_to_activity`, `lifetime_to_annual`, `annual_to_daily`, etc.
- `parse("1 in 11,000")` — best-effort string parsing

`exposure` values: `per_event`, `per_year`, `per_day`, `per_hour`,
`per_mile`, `per_km`, `per_trip`, `per_jump`, `per_dive`, `per_climb`,
`lifetime`.

## Adding sources

Drop a new module under `scrape/` that exposes `ingest(conn) -> int` and
add it to `SCRAPERS` in `build_db.py`. See `scrape/cdc_causes.py` for the
minimal template. Use `scrape/_http.fetch(url)` to get on-disk caching for
free.

## Tests

```bash
.venv/bin/python -m pytest -q
```
