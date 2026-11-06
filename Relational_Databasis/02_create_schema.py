"""
02 - Creating the database schema (DDL)
=======================================
Running example from the lectures: bars, cocktails and ingredients.

  bar  1 ---- n  serves  n ---- 1  cocktail  1 ---- n  contains  n ---- 1  ingredient
               (price)                                (amount_cl)

The M:N relationships become own tables ("weak entities") whose primary key
is the combination of the two foreign keys.
"""
import sqlite3
from pathlib import Path

# Database file next to this script - works no matter from which folder you start Python
DB_PATH = Path(__file__).resolve().parent / "bars.db"

SCHEMA = """
DROP TABLE IF EXISTS contains;
DROP TABLE IF EXISTS serves;
DROP TABLE IF EXISTS ingredient;
DROP TABLE IF EXISTS cocktail;
DROP TABLE IF EXISTS bar;

CREATE TABLE bar (
    b_id          INTEGER PRIMARY KEY,          -- artificial key (auto-increment)
    name          TEXT    NOT NULL,
    city          TEXT    NOT NULL,
    opening_date  TEXT                           -- ISO 8601: 'YYYY-MM-DD'
);

CREATE TABLE cocktail (
    c_id  INTEGER PRIMARY KEY,
    name  TEXT NOT NULL UNIQUE
);

CREATE TABLE ingredient (
    i_id      INTEGER PRIMARY KEY,
    name      TEXT    NOT NULL UNIQUE,
    is_sweet  INTEGER NOT NULL CHECK (is_sweet IN (0, 1))   -- boolean
);

-- M:N  bar <-> cocktail, with relationship attribute "price"
CREATE TABLE serves (
    b_id   INTEGER NOT NULL REFERENCES bar(b_id)      ON DELETE CASCADE,
    c_id   INTEGER NOT NULL REFERENCES cocktail(c_id) ON DELETE CASCADE,
    price  REAL    NOT NULL CHECK (price > 0),
    PRIMARY KEY (b_id, c_id)
);

-- M:N  cocktail <-> ingredient, with relationship attribute "amount_cl"
CREATE TABLE contains (
    c_id       INTEGER NOT NULL REFERENCES cocktail(c_id)   ON DELETE CASCADE,
    i_id       INTEGER NOT NULL REFERENCES ingredient(i_id),
    amount_cl  REAL,
    PRIMARY KEY (c_id, i_id)
);
"""

with sqlite3.connect(DB_PATH) as conn:
    conn.executescript(SCHEMA)          # runs several statements at once

    # Which tables exist now? SQLite keeps its catalog in sqlite_schema
    tables = conn.execute(
        "SELECT name FROM sqlite_schema WHERE type = 'table' ORDER BY name"
    ).fetchall()
    print("Tables:", [t[0] for t in tables])

    # Inspect the columns of one table
    for col in conn.execute("PRAGMA table_info(serves)"):
        print(col)
conn.close()
