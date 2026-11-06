"""
07 - Indexes: why databases can search fast
===========================================
Without an index the DBMS must read every row (full table scan).
An index (a B-tree) lets it jump directly to the matching rows.
"""
import random
import sqlite3
import time

random.seed(42)
conn = sqlite3.connect(":memory:")
conn.execute("CREATE TABLE orders (o_id INTEGER PRIMARY KEY, customer TEXT, amount REAL)")

N = 1_000_000
rows = ((f"customer_{random.randint(1, 100_000)}", round(random.uniform(5, 50), 2))
        for _ in range(N))
conn.executemany("INSERT INTO orders (customer, amount) VALUES (?, ?)", rows)
conn.commit()
print(f"{N:,} orders inserted")

QUERY = "SELECT COUNT(*), SUM(amount) FROM orders WHERE customer = ?"


def measure(label, repetitions=200):
    start = time.perf_counter()
    for i in range(repetitions):
        conn.execute(QUERY, (f"customer_{i + 1}",)).fetchone()
    ms = (time.perf_counter() - start) / repetitions * 1000
    plan = conn.execute("EXPLAIN QUERY PLAN " + QUERY, ("x",)).fetchall()[0][-1]
    print(f"{label:<15} {ms:8.3f} ms/query   plan: {plan}")
    return ms


t1 = measure("without index", repetitions=20)
conn.execute("CREATE INDEX idx_orders_customer ON orders(customer)")
t2 = measure("with index")
print(f"-> about {t1 / t2:,.0f}x faster")
conn.close()
