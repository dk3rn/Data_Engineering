import sqlite3
from pathlib import Path

DB_PATH = Path("sensor_log.db")


def run_sqlite_demo():
    # Connect to the database (creates the file if it doesn't exist)
    with sqlite3.connect(DB_PATH) as conn:
        # Enable column access by name (e.g., row["location"]) in addition to index
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Enforce foreign key constraints (disabled by default in SQLite)
        cursor.execute("PRAGMA foreign_keys = ON;")

        # 1. Create a simple relational structure (2 tables)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                node_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                location TEXT NOT NULL
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS measurements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id INTEGER NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                temperature_c REAL NOT NULL,
                voltage_v REAL NOT NULL,
                FOREIGN KEY (node_id) REFERENCES nodes (node_id)
            );
        """)

        # 2. Insert initial data (using parameterized queries to prevent SQL injection)
        nodes_data = [
            ("Node-Alpha", "Basement Lab"),
            ("Node-Beta", "Outdoor Mast"),
        ]
        cursor.executemany(
            "INSERT OR IGNORE INTO nodes (name, location) VALUES (?, ?);",
            nodes_data,
        )

        measurements_data = [
            (1, 21.4, 13.8),
            (1, 21.6, 13.7),
            (2, 8.2, 12.9),
            (2, 7.9, 12.8),
        ]
        cursor.executemany(
            """
            INSERT INTO measurements (node_id, temperature_c, voltage_v)
            VALUES (?, ?, ?);
            """,
            measurements_data,
        )

        # 3. Read and join data from the database
        cursor.execute("""
            SELECT 
                n.name,
                n.location,
                m.temperature_c,
                m.voltage_v,
                m.timestamp
            FROM measurements m
            JOIN nodes n ON m.node_id = n.node_id
            ORDER BY m.id ASC;
        """)

        rows = cursor.fetchall()

        print(
            f"{'Node':<12} | {'Location':<14} | {'Temp (°C)':<9} | {'Voltage (V)':<11} | {'Timestamp'}"
        )
        print("-" * 75)
        for row in rows:
            print(
                f"{row['name']:<12} | "
                f"{row['location']:<14} | "
                f"{row['temperature_c']:<9.1f} | "
                f"{row['voltage_v']:<11.2f} | "
                f"{row['timestamp']}"
            )


if __name__ == "__main__":
    run_sqlite_demo()