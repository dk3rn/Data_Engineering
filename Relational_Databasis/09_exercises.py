"""
09 - Exercises (run 02_create_schema.py and 03_insert_data.py first)
====================================================================
Fill in the TODOs. Each task can be solved with ONE SQL statement
(task 3 needs several statements inside ONE transaction).
"""
import sqlite3
from pathlib import Path

# Database file next to this script - works no matter from which folder you start Python
DB_PATH = Path(__file__).resolve().parent / "bars.db"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA foreign_keys = ON")

# Task 1: List all ingredients of a 'Piña Colada' together with the amount (cl).
SQL_1 = """ TODO """

# Task 2: Which bar offers the most cocktails? Show bar name and number of cocktails.
SQL_2 = """ TODO """

# Task 3: Add the cocktail 'Daiquiri' (White Rum 5 cl, Lime 3 cl, Cane Sugar 2 cl)
#         and offer it at 'Rheinblick Lounge' for 9.00 EUR.
#         Use a transaction (with conn:) and parameters (?) only - no hard-coded ids!
def add_daiquiri():
    pass  # TODO


# Task 4: Write a function that returns the names of all cocktails
#         containing a given ingredient, e.g. cocktails_with("Lime").
def cocktails_with(ingredient_name):
    pass  # TODO


# Task 5 (bonus): Show the query plan of the Mojito query from 04_queries.py,
#         then create an index that helps it and show the plan again.


if __name__ == "__main__":
    for sql in (SQL_1, SQL_2):
        if "TODO" not in sql:
            print([dict(r) for r in conn.execute(sql)])
