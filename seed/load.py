"""Load the canonical seed dataset into the SQLite DB."""
from __future__ import annotations

import datetime as dt

from micromort.db import add_tags, transaction, upsert_risk, upsert_source
from seed.canonical import RISKS, SOURCES


def load(conn) -> int:
    """Insert seed sources + risks. Returns number of risks written."""
    today = dt.date.today().isoformat()
    source_ids: dict[str, int] = {}
    with transaction(conn):
        for key, meta in SOURCES.items():
            source_ids[key] = upsert_source(
                conn,
                accessed_at=today,
                **meta,
            )

        count = 0
        for r in RISKS:
            row = dict(r)
            tags = row.pop("tags", []) or []
            source_key = row.pop("source_key")
            row["source_id"] = source_ids[source_key]
            slug = row.pop("slug")
            risk_id = upsert_risk(conn, slug=slug, **row)
            add_tags(conn, risk_id, tags)
            count += 1
    return count


if __name__ == "__main__":
    from micromort.db import connect, init_schema

    conn = connect()
    init_schema(conn)
    n = load(conn)
    print(f"Seeded {n} risks.")
