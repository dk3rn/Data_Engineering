"""
Solutions for 09_exercises.py  (run from the parent folder:  python solutions/09_solutions.py)
"""
import sqlite3

conn = sqlite3.connect("bars.db")
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA foreign_keys = ON")

# Task 1
SQL_1 = """
SELECT i.name AS ingredient, co.amount_cl
FROM   cocktail c
JOIN   contains   co ON co.c_id = c.c_id
JOIN   ingredient i  ON i.i_id  = co.i_id
WHERE  c.name = ?
"""
print("Task 1:", [dict(r) for r in conn.execute(SQL_1, ("Piña Colada",))])

# Task 2
SQL_2 = """
SELECT b.name, COUNT(*) AS cocktails
FROM   bar b JOIN serves s ON s.b_id = b.b_id
GROUP  BY b.b_id
ORDER  BY cocktails DESC
LIMIT  1
"""
print("Task 2:", dict(conn.execute(SQL_2).fetchone()))


# Task 3
def add_daiquiri():
    recipe = {"White Rum": 5, "Lime": 3, "Cane Sugar": 2}
    with conn:                                   # all or nothing
        c_id = conn.execute(
            "INSERT INTO cocktail (name) VALUES (?)", ("Daiquiri",)
        ).lastrowid
        for ingredient, amount in recipe.items():
            conn.execute(
                "INSERT INTO contains (c_id, i_id, amount_cl) "
                "SELECT ?, i_id, ? FROM ingredient WHERE name = ?",
                (c_id, amount, ingredient),
            )
        conn.execute(
            "INSERT INTO serves (b_id, c_id, price) "
            "SELECT b_id, ?, ? FROM bar WHERE name = ?",
            (c_id, 9.00, "Rheinblick Lounge"),
        )


try:
    add_daiquiri()
    print("Task 3: Daiquiri added")
except sqlite3.IntegrityError as e:
    print("Task 3: already added?", e)


# Task 4
def cocktails_with(ingredient_name):
    sql = """
    SELECT c.name
    FROM   cocktail c
    JOIN   contains   co ON co.c_id = c.c_id
    JOIN   ingredient i  ON i.i_id  = co.i_id
    WHERE  i.name = ?
    ORDER  BY c.name
    """
    return [row["name"] for row in conn.execute(sql, (ingredient_name,))]


print("Task 4:", cocktails_with("Lime"))

# Task 5
MOJITO = """
SELECT b.name, s.price FROM serves s
JOIN bar b ON b.b_id = s.b_id JOIN cocktail c ON c.c_id = s.c_id
WHERE c.name = 'Mojito'
"""
show = lambda: [r[-1] for r in conn.execute("EXPLAIN QUERY PLAN " + MOJITO)]
print("Task 5 before:", show())
conn.execute("CREATE INDEX IF NOT EXISTS idx_serves_cocktail ON serves(c_id)")
print("Task 5 after: ", show())
conn.close()
