"""
05 - UPDATE, DELETE and integrity constraints
=============================================
The DBMS - not your program - guarantees that the data stays consistent.
"""
import sqlite3
from pathlib import Path

# Database file next to this script - works no matter from which folder you start Python
DB_PATH = Path(__file__).resolve().parent / "bars.db"

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA foreign_keys = ON")

# --- UPDATE: change data in ONE place (no redundancy!) -----------------------
cur = conn.execute(
    "UPDATE serves SET price = ROUND(price * 1.10, 2) WHERE b_id = ?", (2,)
)
print("Price increase at bar 2 ->", cur.rowcount, "rows updated")
conn.commit()

# --- Constraint violations raise sqlite3.IntegrityError ----------------------
tests = {
    "NOT NULL":    ("INSERT INTO bar (name, city) VALUES (?, ?)", (None, "Köln")),
    "UNIQUE":      ("INSERT INTO cocktail (name) VALUES (?)", ("Mojito",)),
    "CHECK":       ("INSERT INTO serves VALUES (?, ?, ?)", (1, 3, -5.0)),
    "PRIMARY KEY": ("INSERT INTO serves VALUES (?, ?, ?)", (1, 1, 9.0)),
    "FOREIGN KEY": ("INSERT INTO serves VALUES (?, ?, ?)", (99, 1, 9.0)),
}
for constraint, (sql, params) in tests.items():
    try:
        conn.execute(sql, params)
    except sqlite3.IntegrityError as e:
        print(f"{constraint:<12} rejected: {e}")

# --- DELETE with ON DELETE CASCADE -------------------------------------------
before = conn.execute("SELECT COUNT(*) FROM serves").fetchone()[0]
conn.execute("DELETE FROM bar WHERE name = ?", ("Campus Corner",))
after = conn.execute("SELECT COUNT(*) FROM serves").fetchone()[0]
print(f"\nDeleted 'Campus Corner': serves rows {before} -> {after} (cascade)")

conn.rollback()        # undo the delete - we still need the bar for later scripts
print("Rolled back, bars:", conn.execute("SELECT COUNT(*) FROM bar").fetchone()[0])
conn.close()
