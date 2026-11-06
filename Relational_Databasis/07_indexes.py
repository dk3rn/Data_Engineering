"""
06 - Transactions (ACID)
========================
A transaction is "all or nothing": either every statement succeeds,
or the database is left exactly as it was before.
"""
import sqlite3

conn = sqlite3.connect("bars.db")
conn.execute("PRAGMA foreign_keys = ON")


def total_offers():
    return conn.execute("SELECT COUNT(*) FROM serves").fetchone()[0]


print("Offers before:", total_offers())

# 'with conn:' = commit on success, ROLLBACK on any exception
try:
    with conn:
        # A new bar opens and takes over the menu of 'Dom Cocktails' ...
        cur = conn.execute(
            "INSERT INTO bar (name, city, opening_date) VALUES (?, ?, date('now'))",
            ("Hochschul-Bar", "Gummersbach"),
        )
        new_id = cur.lastrowid
        conn.execute(
            "INSERT INTO serves (b_id, c_id, price) "
            "SELECT ?, c_id, price FROM serves WHERE b_id = 3",
            (new_id,),
        )
        print("  inside transaction:", total_offers(), "offers")
        # ... but then something goes wrong (price must be > 0):
        conn.execute("INSERT INTO serves VALUES (?, ?, ?)", (new_id, 5, 0))
except sqlite3.IntegrityError as e:
    print("  error:", e, "-> ROLLBACK")

print("Offers after: ", total_offers())   # unchanged - atomicity!
print("Hochschul-Bar exists?",
      conn.execute("SELECT COUNT(*) FROM bar WHERE name='Hochschul-Bar'").fetchone()[0] == 1)
conn.close()
