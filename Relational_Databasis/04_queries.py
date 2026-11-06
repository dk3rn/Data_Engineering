"""
03 - Inserting data (DML) with parameters
=========================================
NEVER build SQL with f-strings or + : use placeholders (?) instead.
The driver escapes the values for you -> protection against SQL injection.
"""
import sqlite3

conn = sqlite3.connect("bars.db")
conn.execute("PRAGMA foreign_keys = ON")   # SQLite: FK checks are OFF by default!
cur = conn.cursor()

# --- Single row ---------------------------------------------------------------
cur.execute(
    "INSERT INTO bar (name, city, opening_date) VALUES (?, ?, ?)",
    ("Rheinblick Lounge", "Köln", "2015-04-01"),
)
print("New bar got b_id =", cur.lastrowid)

# --- Many rows at once: executemany -------------------------------------------
bars = [
    ("Oberberg Tiki Bar", "Gummersbach", "2019-09-13"),
    ("Dom Cocktails", "Köln", "2008-11-20"),
    ("Campus Corner", "Gummersbach", None),          # NULL = unknown
]
cur.executemany("INSERT INTO bar (name, city, opening_date) VALUES (?, ?, ?)", bars)

cocktails = [("Mojito",), ("Caipirinha",), ("Cuba Libre",), ("Piña Colada",), ("Virgin Colada",)]
cur.executemany("INSERT INTO cocktail (name) VALUES (?)", cocktails)

ingredients = [
    ("White Rum", 0), ("Lime", 0), ("Cane Sugar", 1), ("Mint", 0), ("Soda Water", 0),
    ("Cachaça", 0), ("Cola", 1), ("Coconut Cream", 1), ("Pineapple Juice", 1),
]
cur.executemany("INSERT INTO ingredient (name, is_sweet) VALUES (?, ?)", ingredients)

# Relationship tables: (b_id, c_id, price) and (c_id, i_id, amount_cl)
serves = [
    (1, 1, 9.50), (1, 2, 9.00), (1, 4, 10.50),
    (2, 1, 8.00), (2, 3, 7.50), (2, 4, 9.00), (2, 5, 6.50),
    (3, 1, 11.00), (3, 2, 10.00), (3, 3, 9.00),
    (4, 3, 6.00), (4, 5, 5.00),
]
cur.executemany("INSERT INTO serves (b_id, c_id, price) VALUES (?, ?, ?)", serves)

contains = [
    (1, 1, 5), (1, 2, 2), (1, 3, 2), (1, 4, None), (1, 5, 6),   # Mojito
    (2, 6, 5), (2, 2, 3), (2, 3, 2),                            # Caipirinha
    (3, 1, 4), (3, 7, 12), (3, 2, 1),                           # Cuba Libre
    (4, 1, 4), (4, 8, 4), (4, 9, 12),                           # Piña Colada
    (5, 8, 4), (5, 9, 16),                                      # Virgin Colada
]
cur.executemany("INSERT INTO contains (c_id, i_id, amount_cl) VALUES (?, ?, ?)", contains)

conn.commit()      # make the changes permanent (end of transaction)

for table in ("bar", "cocktail", "ingredient", "serves", "contains"):
    n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]   # table names cannot be parameters
    print(f"{table:<11} {n:>3} rows")

conn.close()

# ---------------------------------------------------------------------------
# Why placeholders matter - the classic SQL injection:
#
#   user_input = "x'; DROP TABLE bar; --"
#   sql = f"SELECT * FROM bar WHERE name = '{user_input}'"     # DANGEROUS
#   conn.execute("SELECT * FROM bar WHERE name = ?", (user_input,))  # SAFE
# ---------------------------------------------------------------------------
