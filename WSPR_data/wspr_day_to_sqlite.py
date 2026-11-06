#!/usr/bin/env python3
"""
wspr_day_to_sqlite.py
=====================
Downloads all WSPR spots of ONE day (UTC) from the public wspr.live database
(a ClickHouse mirror of wsprnet.org) and stores them in a SQLite database.

Only the Python standard library is used (urllib, csv, sqlite3).

Usage
-----
    python wspr_day_to_sqlite.py                       # yesterday (UTC) -> wspr.db
    python wspr_day_to_sqlite.py --date 2026-11-01
    python wspr_day_to_sqlite.py --date 2026-11-01 --band 14 --db wspr_20m.db

Notes
-----
* One day contains several million spots. The download is therefore split
  into chunks (default: 1 hour) that are streamed directly into SQLite,
  so memory usage stays small.
* The script can be re-run safely: spots are identified by their id
  (PRIMARY KEY) and duplicates are ignored (INSERT OR IGNORE).
* Band codes: -1 = LF, 0 = MF, 1 = 160 m, 3 = 80 m, 7 = 40 m, 10 = 30 m,
  14 = 20 m, 21 = 15 m, 28 = 10 m, 50 = 6 m, 144 = 2 m, ...
"""
import argparse
import csv
import io
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

API_URL = "https://db1.wspr.live/"

# Columns we request from wspr.live (table wspr.rx).
# The time is requested as Unix epoch to avoid any time-zone ambiguity.
COLUMNS = [
    "id", "toUnixTimestamp(time) AS epoch", "band",
    "rx_sign", "rx_lat", "rx_lon", "rx_loc",
    "tx_sign", "tx_lat", "tx_lon", "tx_loc",
    "distance", "azimuth", "rx_azimuth",
    "frequency", "power", "snr", "drift", "version", "code",
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS spot (
    id          INTEGER PRIMARY KEY,           -- spot id (same as wsprnet.org)
    time_utc    TEXT    NOT NULL,              -- 'YYYY-MM-DD HH:MM:SS' (UTC)
    epoch       INTEGER NOT NULL,              -- Unix timestamp (UTC)
    band        INTEGER NOT NULL,              -- band code (14 = 20 m, ...)
    rx_sign     TEXT    NOT NULL,              -- receiver callsign
    rx_lat      REAL,
    rx_lon      REAL,
    rx_loc      TEXT,                          -- receiver Maidenhead locator
    tx_sign     TEXT    NOT NULL,              -- transmitter callsign
    tx_lat      REAL,
    tx_lon      REAL,
    tx_loc      TEXT,                          -- transmitter Maidenhead locator
    distance    INTEGER,                       -- km
    azimuth     INTEGER,                       -- degrees, seen from transmitter
    rx_azimuth  INTEGER,                       -- degrees, seen from receiver
    frequency   INTEGER NOT NULL,              -- Hz
    power       INTEGER,                       -- dBm
    snr         INTEGER,                       -- dB
    drift       INTEGER,                       -- Hz/min (-3 .. +3)
    version     TEXT,                          -- receiver software version
    code        INTEGER                        -- mode flag
);

-- bookkeeping: which time ranges have already been loaded completely
CREATE TABLE IF NOT EXISTS load_log (
    chunk_start TEXT NOT NULL,
    chunk_end   TEXT NOT NULL,
    band        INTEGER,                       -- NULL = all bands
    rows        INTEGER NOT NULL,
    loaded_at   TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (chunk_start, chunk_end, band)
);
"""

INDEXES = """
CREATE INDEX IF NOT EXISTS idx_spot_band_epoch ON spot(band, epoch);
CREATE INDEX IF NOT EXISTS idx_spot_tx_sign    ON spot(tx_sign);
CREATE INDEX IF NOT EXISTS idx_spot_rx_sign    ON spot(rx_sign);
"""

INSERT_SQL = f"""
INSERT OR IGNORE INTO spot (
    id, time_utc, epoch, band, rx_sign, rx_lat, rx_lon, rx_loc,
    tx_sign, tx_lat, tx_lon, tx_loc, distance, azimuth, rx_azimuth,
    frequency, power, snr, drift, version, code
) VALUES ({", ".join("?" * 21)})
"""


# --------------------------------------------------------------------------- #
# Extract: download one time chunk from wspr.live as CSV (streamed)
# --------------------------------------------------------------------------- #
def build_query(start: datetime, end: datetime, band: int | None) -> str:
    fmt = "%Y-%m-%d %H:%M:%S"
    where = (
        f"time >= toDateTime('{start.strftime(fmt)}', 'UTC') "
        f"AND time < toDateTime('{end.strftime(fmt)}', 'UTC')"
    )
    if band is not None:
        where += f" AND band = {int(band)}"          # int() -> no injection
    return (
        f"SELECT {', '.join(COLUMNS)} FROM wspr.rx "
        f"WHERE {where} ORDER BY id FORMAT CSVWithNames"
    )


def fetch_chunk(start, end, band, retries=4, timeout=300):
    """Yields one dict per spot. Retries with exponential backoff."""
    url = API_URL + "?" + urllib.parse.urlencode({"query": build_query(start, end, band)})
    req = urllib.request.Request(url, headers={"User-Agent": "wspr-sqlite-loader/1.0 (teaching example)"})
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                text = io.TextIOWrapper(resp, encoding="utf-8", newline="")
                yield from csv.DictReader(text)
            return
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt == retries:
                raise
            wait = 2 ** attempt
            print(f"    request failed ({e}); retry {attempt}/{retries - 1} in {wait}s", file=sys.stderr)
            time.sleep(wait)


# --------------------------------------------------------------------------- #
# Transform: convert one CSV record into a tuple for SQLite
# --------------------------------------------------------------------------- #
def to_int(v):
    return int(v) if v not in ("", None, "\\N") else None


def to_float(v):
    return float(v) if v not in ("", None, "\\N") else None


def transform(rec: dict) -> tuple:
    epoch = int(rec["epoch"])
    time_utc = datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    return (
        int(rec["id"]), time_utc, epoch, int(rec["band"]),
        rec["rx_sign"], to_float(rec["rx_lat"]), to_float(rec["rx_lon"]), rec["rx_loc"],
        rec["tx_sign"], to_float(rec["tx_lat"]), to_float(rec["tx_lon"]), rec["tx_loc"],
        to_int(rec["distance"]), to_int(rec["azimuth"]), to_int(rec["rx_azimuth"]),
        int(rec["frequency"]), to_int(rec["power"]), to_int(rec["snr"]),
        to_int(rec["drift"]), rec["version"], to_int(rec["code"]),
    )


# --------------------------------------------------------------------------- #
# Load: write one chunk inside one transaction
# --------------------------------------------------------------------------- #
def load_chunk(conn, start, end, band, batch_size=10_000) -> tuple[int, int]:
    """Returns (rows received, rows rejected)."""
    received = rejected = 0
    batch = []
    with conn:                                  # COMMIT at the end, ROLLBACK on error
        for rec in fetch_chunk(start, end, band):
            received += 1
            try:
                batch.append(transform(rec))
            except (KeyError, ValueError) as e:  # malformed row -> skip it
                rejected += 1
                if rejected <= 5:
                    print(f"    skipped malformed row ({e}): {rec}", file=sys.stderr)
                continue
            if len(batch) >= batch_size:
                conn.executemany(INSERT_SQL, batch)
                batch.clear()
        if batch:
            conn.executemany(INSERT_SQL, batch)
        conn.execute(
            "INSERT OR REPLACE INTO load_log (chunk_start, chunk_end, band, rows) VALUES (?, ?, ?, ?)",
            (start.isoformat(), end.isoformat(), band, received - rejected),
        )
    return received, rejected


def already_loaded(conn, start, end, band) -> bool:
    return conn.execute(
        "SELECT 1 FROM load_log WHERE chunk_start = ? AND chunk_end = ? AND band IS ?",
        (start.isoformat(), end.isoformat(), band),
    ).fetchone() is not None


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def parse_args():
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    p = argparse.ArgumentParser(description="Load one day of WSPR spots from wspr.live into SQLite.")
    p.add_argument("--date", default=yesterday, help="day in UTC, YYYY-MM-DD (default: yesterday)")
    p.add_argument("--db", default="wspr.db", help="SQLite database file (default: wspr.db)")
    p.add_argument("--band", type=int, default=None, help="only this band code, e.g. 14 for 20 m")
    p.add_argument("--chunk-hours", type=int, default=1, choices=[1, 2, 3, 4, 6, 8, 12, 24],
                   help="hours per download request (default: 1)")
    p.add_argument("--force", action="store_true", help="reload chunks even if already loaded")
    return p.parse_args()


def main():
    args = parse_args()
    day = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if day >= datetime.now(timezone.utc):
        sys.exit("The date must lie in the past.")

    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA journal_mode = WAL")      # faster bulk writes
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.executescript(SCHEMA)

    band_txt = f"band {args.band}" if args.band is not None else "all bands"
    print(f"Loading WSPR spots of {args.date} (UTC), {band_txt} -> {args.db}")
    t0 = time.perf_counter()
    total = 0
    step = timedelta(hours=args.chunk_hours)
    start = day
    while start < day + timedelta(days=1):
        end = start + step
        label = f"{start:%H:%M}-{end:%H:%M}"
        if not args.force and already_loaded(conn, start, end, args.band):
            print(f"  {label}  already loaded, skipped")
        else:
            t = time.perf_counter()
            received, rejected = load_chunk(conn, start, end, args.band)
            total += received - rejected
            print(f"  {label}  {received:>9,} spots  ({time.perf_counter() - t:5.1f} s)"
                  + (f"  {rejected} rejected" if rejected else ""))
        start = end

    print("Creating indexes ...")
    conn.executescript(INDEXES)

    # short summary
    lo, hi = int(day.timestamp()), int((day + timedelta(days=1)).timestamp())
    print(f"\nDone in {time.perf_counter() - t0:.0f} s, {total:,} new spots written.")
    print("Spots per band for this day:")
    for band, n in conn.execute(
        "SELECT band, COUNT(*) FROM spot WHERE epoch >= ? AND epoch < ? GROUP BY band ORDER BY band",
        (lo, hi),
    ):
        print(f"  band {band:>5}: {n:>10,}")
    conn.close()


if __name__ == "__main__":
    main()
