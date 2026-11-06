"""
08 - Mini ETL pipeline: CSV  ->  validate  ->  SQLite  ->  analyse
==================================================================
Typical data-engineering task: raw sensor readings arrive as CSV files.
  Extract   : read the CSV
  Transform : validate / clean the rows
  Load      : store them in a table with constraints
"""
import csv
import io
import sqlite3

import pandas as pd

# In practice this would be open("readings.csv"); here inline for a self-contained demo
RAW_CSV = """machine,timestamp,temperature_c
M1,2026-11-06 08:00,71.5
M1,2026-11-06 08:05,72.1
M2,2026-11-06 08:00,65.0
M2,2026-11-06 08:05,not_available
M3,2026-11-06 08:00,-999
M2,2026-11-06 08:10,66.4
M1,2026-11-06 08:10,79.8
"""

conn = sqlite3.connect("sensors.db")
conn.executescript("""
DROP TABLE IF EXISTS reading;
CREATE TABLE reading (
    machine        TEXT NOT NULL,
    ts             TEXT NOT NULL,
    temperature_c  REAL NOT NULL CHECK (temperature_c BETWEEN -50 AND 200),
    PRIMARY KEY (machine, ts)
);
""")

# --- Extract + Transform ------------------------------------------------------
good, bad = [], []
for rec in csv.DictReader(io.StringIO(RAW_CSV)):
    try:
        good.append((rec["machine"], rec["timestamp"], float(rec["temperature_c"])))
    except ValueError:
        bad.append(rec)                       # not a number -> reject

# --- Load: the CHECK constraint is our second line of defence ----------------
loaded = 0
for row in good:
    try:
        conn.execute("INSERT INTO reading VALUES (?, ?, ?)", row)
        loaded += 1
    except sqlite3.IntegrityError as e:
        bad.append({"row": row, "error": str(e)})
conn.commit()
print(f"loaded {loaded} rows, rejected {len(bad)}:")
for b in bad:
    print("  ", b)

# --- Analyse: SQL result straight into a pandas DataFrame --------------------
df = pd.read_sql_query(
    """SELECT machine, COUNT(*) AS n, ROUND(AVG(temperature_c),1) AS avg_temp,
              MAX(temperature_c) AS max_temp
       FROM reading GROUP BY machine ORDER BY machine""",
    conn,
)
print(df.to_string(index=False))
conn.close()
