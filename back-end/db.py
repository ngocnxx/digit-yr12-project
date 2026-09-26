"""SQLite access that include connection helper, per-request lifecycle, and init_db().

"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from flask import current_app, g

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

#finding the database path
def _database_path() -> str:

    if current_app:
        return current_app.config["DATABASE_PATH"]
    path = Path(os.environ.get("DATABASE_PATH", "navigator.db"))
    return str(path if path.is_absolute() else Path(__file__).parent / path)

#open connection -> if connection is not present then create it
def get_db() -> sqlite3.Connection:

    if "db" not in g:
        # When the database lives in S3 (s3db.py), open the latest local copy of it
        sync = current_app.config.get("DB_SYNC")
        conn = sqlite3.connect(sync.pull() if sync is not None else _database_path())
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON") #turn on relational link
        g.db = conn
    return g.db

#pull the data then completely destroy it (close connection)
def close_db(_exception: BaseException | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()

# Columns added to schema.sql after navigator.db was first created. 
_NEW_COLUMNS = {
    "users": [("daily_cap", "INTEGER NOT NULL DEFAULT 5")],
    "subjects": [("internal_mode", "INTEGER NOT NULL DEFAULT 0")],
    "reviews": [
        ("evidence", "TEXT"),
        ("reflection", "TEXT"),
        ("attachment", "TEXT"),
        ("attachment_name", "TEXT"),
    ],
}


def _migrate(conn: sqlite3.Connection) -> None:
    for table, columns in _NEW_COLUMNS.items():
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        for name, ddl in columns:
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
    conn.commit()


# build the tables
def init_db(database_path: str | None = None) -> None:
    """Create all tables from schema.sql, then migrate any pre-existing database
    to pick up columns added since it was first created. Safe to run repeatedly."""
    path = database_path or _database_path()
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.commit()
        _migrate(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    # Allow:  python -c "import db; db.init_db()"  and  python db.py
    init_db()
    print(f"Initialised database at {_database_path()!r}")
