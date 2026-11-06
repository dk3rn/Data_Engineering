"""
04 - Querying data (SELECT, WHERE, ORDER BY, JOIN, GROUP BY)
============================================================
"""
import sqlite3

conn = sqlite3.connect("bars.db")
conn.row_factory = sqlite3.Row      # rows behave like dicts: row["name"]

# --- 1. Simple filter + sorting ----------------------------------------------
print("Bars in Köln:")
for row in conn.execute(
    "SELECT name, opening_date FROM bar WHERE city = ? ORDER BY opening_date",
    ("Köln",),
):
    print(f"  {row['name']:<20} since {row['opening_date']}")

# --- 2. fetchone / fetchall ---------------------------------------------------
cheapest = conn.execute("SELECT MIN(price) AS p FROM serves").fetchone()
print("\nCheapest drink costs", cheapest["p"], "EUR")

# --- 3. JOIN: combine the tables via their keys ------------------------------
sql = """
SELECT b.name AS bar, c.name AS cocktail, s.price
FROM   serves   s
JOIN   bar      b ON b.b_id = s.b_id
JOIN   cocktail c ON c.c_id = s.c_id
WHERE  c.name = ?
ORDER  BY s.price
"""
print("\nWhere can I get a Mojito?")
for row in conn.execute(sql, ("Mojito",)):
    print(f"  {row['bar']:<20} {row['price']:>6.2f} EUR")

# --- 4. Aggregation: GROUP BY ------------------------------------------------
sql = """
SELECT b.city,
       COUNT(*)             AS offers,
       ROUND(AVG(s.price),2) AS avg_price
FROM   serves s JOIN bar b ON b.b_id = s.b_id
GROUP  BY b.city
ORDER  BY avg_price DESC
"""
print("\nAverage price per city:")
for row in conn.execute(sql):
    print(f"  {row['city']:<12} {row['offers']} offers, avg {row['avg_price']} EUR")

# --- 5. Which cocktails are alcohol-free?  (subquery) ------------------------
sql = """
SELECT name FROM cocktail
WHERE  c_id NOT IN (
    SELECT c.c_id FROM contains c JOIN ingredient i ON i.i_id = c.i_id
    WHERE  i.name IN ('White Rum', 'Cachaça')
)
"""
print("\nAlcohol-free:", [r["name"] for r in conn.execute(sql)])

conn.close()
