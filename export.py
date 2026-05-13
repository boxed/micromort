"""Export risks.db → data.json for the Elm frontend."""
from __future__ import annotations

import json
from pathlib import Path

from micromort.db import connect

OUT = Path(__file__).resolve().parent / "data.json"


def export(out_path: Path = OUT) -> int:
    conn = connect()
    rows = conn.execute("""
        SELECT
            r.id,
            r.slug,
            r.name,
            r.description,
            r.category,
            r.micromorts,
            r.exposure,
            r.exposure_detail,
            r.population,
            r.region,
            r.year,
            r.original_value,
            r.original_unit,
            r.confidence,
            r.notes,
            s.name      AS source_name,
            s.url       AS source_url,
            s.publisher AS source_publisher
        FROM risks r
        LEFT JOIN sources s ON s.id = r.source_id
        ORDER BY r.micromorts
    """).fetchall()

    risks = []
    for r in rows:
        tags = [
            t["name"] for t in conn.execute(
                "SELECT t.name FROM tags t "
                "JOIN risk_tags rt ON rt.tag_id = t.id "
                "WHERE rt.risk_id = ? ORDER BY t.name",
                (r["id"],),
            )
        ]
        risks.append({
            "slug":            r["slug"],
            "name":            r["name"],
            "description":     r["description"],
            "category":        r["category"],
            "micromorts":      r["micromorts"],
            "exposure":        r["exposure"],
            "exposureDetail":  r["exposure_detail"],
            "population":      r["population"],
            "region":          r["region"],
            "year":            r["year"],
            "originalValue":   r["original_value"],
            "originalUnit":    r["original_unit"],
            "confidence":      r["confidence"],
            "notes":           r["notes"],
            "source": {
                "name":      r["source_name"],
                "url":       r["source_url"],
                "publisher": r["source_publisher"],
            },
            "tags": tags,
        })

    payload = {
        "version": 1,
        "count": len(risks),
        "risks": risks,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return len(risks)


if __name__ == "__main__":
    n = export()
    print(f"wrote {n} risks → {OUT}")
