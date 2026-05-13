-- One micromort = a one-in-a-million chance of death.
--
-- A risk is a single normalized estimate: how many micromorts you incur from
-- some exposure (one trip, one hour, one year of life, one activity, ...).
-- All values are stored as micromorts; the original_value / original_unit
-- columns preserve how the source phrased it.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sources (
    id           INTEGER PRIMARY KEY,
    name         TEXT NOT NULL,
    url          TEXT,
    publisher    TEXT,
    accessed_at  TEXT,         -- ISO-8601 date
    notes        TEXT,
    UNIQUE (name, url)
);

CREATE TABLE IF NOT EXISTS risks (
    id              INTEGER PRIMARY KEY,
    slug            TEXT UNIQUE NOT NULL,    -- stable identifier
    name            TEXT NOT NULL,
    description     TEXT,
    category        TEXT NOT NULL,           -- transport | activity | disease | occupation | environmental | medical | violence | misc
    micromorts      REAL NOT NULL,           -- normalized risk
    exposure        TEXT NOT NULL,           -- per_event | per_hour | per_km | per_mile | per_trip | per_year | lifetime | per_day | per_jump | per_dive | per_climb
    exposure_detail TEXT,                    -- "one jump", "one marathon", "one year, age 25–34, US", ...
    population      TEXT,                    -- e.g. "US, all ages", "UK males 30–39"
    region          TEXT,                    -- ISO country / region code or freeform
    year            INTEGER,                 -- year the underlying data is from
    source_id       INTEGER REFERENCES sources(id),
    original_value  TEXT,                    -- e.g. "1 in 11,000"
    original_unit   TEXT,                    -- exactly how the source phrased it
    confidence      TEXT,                    -- low | medium | high
    notes           TEXT,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_risks_category ON risks(category);
CREATE INDEX IF NOT EXISTS idx_risks_exposure ON risks(exposure);
CREATE INDEX IF NOT EXISTS idx_risks_micromorts ON risks(micromorts);

CREATE TABLE IF NOT EXISTS tags (
    id   INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS risk_tags (
    risk_id INTEGER NOT NULL REFERENCES risks(id) ON DELETE CASCADE,
    tag_id  INTEGER NOT NULL REFERENCES tags(id)  ON DELETE CASCADE,
    PRIMARY KEY (risk_id, tag_id)
);
