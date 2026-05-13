"""SQLite helpers."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "risks.db"
SCHEMA_PATH = ROOT / "schema.sql"


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text())
    conn.commit()


@contextmanager
def transaction(conn: sqlite3.Connection):
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def upsert_source(conn: sqlite3.Connection, *, name: str, url: str | None = None,
                  publisher: str | None = None, accessed_at: str | None = None,
                  notes: str | None = None) -> int:
    cur = conn.execute(
        "SELECT id FROM sources WHERE name = ? AND IFNULL(url,'') = IFNULL(?, '')",
        (name, url),
    )
    row = cur.fetchone()
    if row:
        return row["id"]
    cur = conn.execute(
        "INSERT INTO sources (name, url, publisher, accessed_at, notes) "
        "VALUES (?, ?, ?, ?, ?)",
        (name, url, publisher, accessed_at, notes),
    )
    return cur.lastrowid


def upsert_risk(conn: sqlite3.Connection, *, slug: str, **fields) -> int:
    """Insert-or-replace a risk by slug. Returns the row id."""
    cols = ["slug"] + list(fields.keys())
    placeholders = ", ".join("?" for _ in cols)
    assignments = ", ".join(f"{c}=excluded.{c}" for c in cols if c != "slug")
    sql = (
        f"INSERT INTO risks ({', '.join(cols)}) VALUES ({placeholders}) "
        f"ON CONFLICT(slug) DO UPDATE SET {assignments}, updated_at = CURRENT_TIMESTAMP"
    )
    conn.execute(sql, [slug, *fields.values()])
    return conn.execute("SELECT id FROM risks WHERE slug = ?", (slug,)).fetchone()["id"]


def add_tags(conn: sqlite3.Connection, risk_id: int, tags: list[str]) -> None:
    for tag in tags:
        conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
        tag_id = conn.execute("SELECT id FROM tags WHERE name = ?", (tag,)).fetchone()["id"]
        conn.execute(
            "INSERT OR IGNORE INTO risk_tags (risk_id, tag_id) VALUES (?, ?)",
            (risk_id, tag_id),
        )
