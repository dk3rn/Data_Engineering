"""
01 - Connecting to SQLite
=========================
SQLite ships with Python (module ``sqlite3``) - no server, no installation.
A database is just ONE file on disk (or lives purely in memory).
"""
import sqlite3

# --- 1. A database file: created automatically if it does not exist ----------
conn = sqlite3.connect("bars.db")
print("SQLite library version:", sqlite3.sqlite_version)

# A cursor executes SQL statements and holds the result set
cur = conn.cursor()
cur.execute("SELECT 'Hello from SQLite!', date('now')")
print(cur.fetchone())          # -> ('Hello from SQLite!', '2026-11-06')

conn.close()                   # always close (or use a context manager)

# --- 2. An in-memory database: perfect for tests, gone after close() ----------
mem = sqlite3.connect(":memory:")
print(mem.execute("SELECT 6 * 7").fetchone()[0])   # -> 42
mem.close()
