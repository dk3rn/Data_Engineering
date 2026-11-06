#!/usr/bin/env python3
"""
wspr_day_to_pandas.py
=====================
Downloads all WSPR spots of ONE day (UTC) from wspr.live, stores them as a
pandas DataFrame file (Parquet, or pickle as fallback) and creates a set of
charts (PNG) plus a one-page dashboard.

Requirements:   pip install pandas matplotlib pyarrow
                (pyarrow is optional - without it the data is saved as .pkl)

Usage
-----
    python wspr_day_to_pandas.py                          # yesterday (UTC)
    python wspr_day_to_pandas.py --date 2026-11-01
    python wspr_day_to_pandas.py --date 2026-11-01 --band 14
    python wspr_day_to_pandas.py --file wspr_2026-11-01.parquet   # only plot an existing file

Output (default folder: ./wspr_output)
------
    wspr_<date>[_band<b>].parquet     the DataFrame (one row per spot)
    plots_<date>[_band<b>]/*.png      individual charts + dashboard.png
"""
import argparse
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use("Agg")                       # render to files, no window needed
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

API_URL = "https://db1.wspr.live/"

COLUMNS = [
    "id", "toUnixTimestamp(time) AS epoch", "band",
    "rx_sign", "rx_lat", "rx_lon", "rx_loc",
    "tx_sign", "tx_lat", "tx_lon", "tx_loc",
    "distance", "azimuth", "rx_azimuth",
    "frequency", "power", "snr", "drift", "version", "code",
]

# pandas dtypes: nullable integers ("Int16" ...) keep missing values as <NA>
DTYPES = {
    "id": "int64", "epoch": "int64", "band": "int16",
    "rx_sign": "string", "rx_lat": "float32", "rx_lon": "float32", "rx_loc": "string",
    "tx_sign": "string", "tx_lat": "float32", "tx_lon": "float32", "tx_loc": "string",
    "distance": "Int32", "azimuth": "Int16", "rx_azimuth": "Int16",
    "frequency": "int64", "power": "Int8", "snr": "Int8", "drift": "Int8",
    "version": "string", "code": "Int8",
}

BAND_NAMES = {
    -1: "LF", 0: "MF", 1: "160 m", 3: "80 m", 5: "60 m", 7: "40 m", 10: "30 m",
    14: "20 m", 18: "17 m", 21: "15 m", 24: "12 m", 28: "10 m", 40: "8 m",
    50: "6 m", 70: "4 m", 144: "2 m", 432: "70 cm", 1296: "23 cm",
}

# Colors (validated reference palette): categorical slots 1-2, one-hue sequential ramp
BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, INK_2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
SEQ = LinearSegmentedColormap.from_list("seq_blue", ["#f1f6fd", "#9cc3ef", "#2a78d6", "#0d3b75"])


# --------------------------------------------------------------------------- #
# Extract
# --------------------------------------------------------------------------- #
def build_query(start, end, band):
    fmt = "%Y-%m-%d %H:%M:%S"
    where = (f"time >= toDateTime('{start:{fmt}}', 'UTC') "
             f"AND time < toDateTime('{end:{fmt}}', 'UTC')")
    if band is not None:
        where += f" AND band = {int(band)}"
    return f"SELECT {', '.join(COLUMNS)} FROM wspr.rx WHERE {where} ORDER BY id FORMAT CSVWithNames"


def fetch_chunk(start, end, band, retries=4, timeout=300) -> pd.DataFrame:
    """Downloads one time chunk and parses it directly into a DataFrame."""
    url = API_URL + "?" + urllib.parse.urlencode({"query": build_query(start, end, band)})
    req = urllib.request.Request(url, headers={"User-Agent": "wspr-pandas-loader/1.0 (teaching example)"})
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                # read as text first, convert types afterwards (robust against bad rows)
                return pd.read_csv(resp, dtype=str, keep_default_na=False, na_values=["", "\\N"])
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt == retries:
                raise
            wait = 2 ** attempt
            print(f"    request failed ({e}); retry in {wait}s", file=sys.stderr)
            time.sleep(wait)


# --------------------------------------------------------------------------- #
# Transform
# --------------------------------------------------------------------------- #
def transform(df: pd.DataFrame) -> pd.DataFrame:
    """Type conversion + validation + derived columns."""
    n0 = len(df)
    numeric = [c for c, t in DTYPES.items() if t not in ("string",)]
    for c in numeric:
        df[c] = pd.to_numeric(df[c], errors="coerce")        # bad values -> NaN
    # required fields must be present
    df = df.dropna(subset=["id", "epoch", "band", "frequency", "rx_sign", "tx_sign"])
    df = df.astype(DTYPES)
    if len(df) < n0:
        print(f"    {n0 - len(df)} malformed rows dropped", file=sys.stderr)

    df["time"] = pd.to_datetime(df["epoch"], unit="s", utc=True)
    df["band_name"] = df["band"].map(BAND_NAMES).fillna(df["band"].astype(str)).astype("category")
    df["power_w"] = (10 ** ((df["power"].astype("float") - 30) / 10)).astype("float32")
    # callsigns / locators repeat a lot -> category saves a lot of memory
    for c in ("rx_sign", "rx_loc", "tx_sign", "tx_loc", "version"):
        df[c] = df[c].astype("category")
    return df


def download_day(day, band, chunk_hours) -> pd.DataFrame:
    frames = []
    start, stop = day, day + timedelta(days=1)
    while start < stop:
        end = start + timedelta(hours=chunk_hours)
        t = time.perf_counter()
        chunk = transform(fetch_chunk(start, end, band))
        frames.append(chunk)
        print(f"  {start:%H:%M}-{end:%H:%M}  {len(chunk):>9,} spots  ({time.perf_counter() - t:5.1f} s)")
        start = end
    df = pd.concat(frames, ignore_index=True)
    # categories from different chunks -> unify
    for c in ("rx_sign", "rx_loc", "tx_sign", "tx_loc", "version", "band_name"):
        df[c] = df[c].astype("category")
    return df.drop_duplicates(subset="id").sort_values("time", ignore_index=True)


# --------------------------------------------------------------------------- #
# Load (save to file)
# --------------------------------------------------------------------------- #
def save(df: pd.DataFrame, base: Path) -> Path:
    try:
        import pyarrow  # noqa: F401
        path = base.with_suffix(".parquet")
        df.to_parquet(path, index=False, compression="zstd")
    except ImportError:
        path = base.with_suffix(".pkl")
        print("  pyarrow not installed -> saving as pickle (pip install pyarrow for Parquet)")
        df.to_pickle(path, compression="gzip")
    return path


def load(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_pickle(path)


# --------------------------------------------------------------------------- #
# Visualization
# --------------------------------------------------------------------------- #
def style(ax, title, xlabel=None, ylabel=None):
    ax.set_title(title, loc="left", fontsize=12, fontweight="bold", color=INK, pad=10)
    if xlabel: ax.set_xlabel(xlabel, color=INK_2)
    if ylabel: ax.set_ylabel(ylabel, color=INK_2)
    ax.tick_params(colors=INK_2, labelsize=9, length=0)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.set_axisbelow(True)


def band_order(df):
    """Bands present in the data, sorted by frequency (not alphabetically)."""
    return [BAND_NAMES.get(b, str(b)) for b in sorted(df["band"].unique())]


def plot_spots_per_band(ax, df):
    counts = df["band_name"].value_counts().reindex(band_order(df)).fillna(0)
    ax.barh(counts.index, counts.values, color=BLUE, height=0.6)
    ax.invert_yaxis()
    for y, v in enumerate(counts.values):                     # direct labels
        ax.text(v, y, f"  {int(v):,}", va="center", fontsize=8, color=INK_2)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_xlim(0, counts.max() * 1.18)
    style(ax, "Spots per band", "number of spots")


def plot_band_hour_heatmap(ax, fig, df):
    pivot = (df.assign(hour=df["time"].dt.hour)
               .pivot_table(index="band_name", columns="hour", values="id",
                            aggfunc="count", observed=True)
               .reindex(index=band_order(df), columns=range(24)).fillna(0))
    im = ax.imshow(pivot.values, aspect="auto", cmap=SEQ, interpolation="nearest")
    ax.set_yticks(range(len(pivot.index)), pivot.index)
    ax.set_xticks(range(0, 24, 3), [f"{h:02d}" for h in range(0, 24, 3)])
    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cb.ax.tick_params(labelsize=8, colors=INK_2, length=0)
    cb.outline.set_visible(False)
    cb.set_label("spots per hour", color=INK_2, fontsize=9)
    style(ax, "Activity by band and hour (UTC)", "hour of day (UTC)")
    ax.spines[:].set_visible(False)


def plot_distance_hist(ax, df):
    d = df["distance"].dropna().astype(float)
    ax.hist(d, bins=60, range=(0, 20_000), color=BLUE, edgecolor="white", linewidth=0.5)
    med = d.median()
    ax.axvline(med, color=INK, linewidth=1, linestyle="--")
    ax.text(med, ax.get_ylim()[1] * 0.95, f"  median {med:,.0f} km", fontsize=8, color=INK, va="top")
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    style(ax, "Distance between transmitter and receiver", "distance (km)", "spots")


def plot_snr_vs_distance(ax, fig, df):
    d = df[["distance", "snr"]].dropna().astype(float)
    hb = ax.hexbin(d["distance"], d["snr"], gridsize=45, cmap=SEQ, bins="log",
                   mincnt=1, extent=(0, 20_000, -35, 15), linewidths=0)
    cb = fig.colorbar(hb, ax=ax, fraction=0.04, pad=0.02)
    cb.ax.tick_params(labelsize=8, colors=INK_2, length=0)
    cb.outline.set_visible(False)
    cb.set_label("spots (log scale)", color=INK_2, fontsize=9)
    style(ax, "SNR vs. distance", "distance (km)", "SNR (dB)")


def plot_station_map(ax, df):
    tx = df.drop_duplicates("tx_sign")[["tx_lon", "tx_lat"]].dropna()
    rx = df.drop_duplicates("rx_sign")[["rx_lon", "rx_lat"]].dropna()
    for lon in range(-180, 181, 30):
        ax.axvline(lon, color=GRID, linewidth=0.6, zorder=0)
    for lat in range(-90, 91, 30):
        ax.axhline(lat, color=GRID, linewidth=0.6, zorder=0)
    ax.scatter(rx["rx_lon"], rx["rx_lat"], s=9, color=ORANGE, alpha=0.75,
               edgecolors="white", linewidths=0.4, label=f"receivers ({len(rx):,})")
    ax.scatter(tx["tx_lon"], tx["tx_lat"], s=9, color=BLUE, alpha=0.75,
               edgecolors="white", linewidths=0.4, label=f"transmitters ({len(tx):,})")
    ax.set_xlim(-180, 180); ax.set_ylim(-90, 90)
    ax.set_aspect("equal")
    ax.legend(loc="lower left", fontsize=8, frameon=False, markerscale=1.8)
    style(ax, "Station locations (lon / lat, from Maidenhead locator)", "longitude", "latitude")


def plot_top_transmitters(ax, df, n=15):
    top = df["tx_sign"].value_counts().head(n)[::-1]
    ax.barh(top.index.astype(str), top.values, color=BLUE, height=0.6)
    for y, v in enumerate(top.values):
        ax.text(v, y, f"  {v:,}", va="center", fontsize=8, color=INK_2)
    ax.set_xlim(0, top.max() * 1.18)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    style(ax, f"Top {n} transmitters (most often heard)", "spots")


CHARTS = [
    ("spots_per_band", plot_spots_per_band, False),
    ("band_hour_heatmap", plot_band_hour_heatmap, True),
    ("distance_histogram", plot_distance_hist, False),
    ("snr_vs_distance", plot_snr_vs_distance, True),
    ("station_map", plot_station_map, False),
    ("top_transmitters", plot_top_transmitters, False),
]


def make_plots(df: pd.DataFrame, outdir: Path, title: str):
    outdir.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "figure.facecolor": "white"})

    # individual charts
    for name, fn, needs_fig in CHARTS:
        fig, ax = plt.subplots(figsize=(9, 5.2 if name != "station_map" else 5.6))
        fn(ax, fig, df) if needs_fig else fn(ax, df)
        fig.tight_layout()
        fig.savefig(outdir / f"{name}.png", dpi=150)
        plt.close(fig)

    # dashboard: all charts on one page
    fig, axes = plt.subplots(3, 2, figsize=(16, 16))
    for ax, (name, fn, needs_fig) in zip(axes.flat, CHARTS):
        fn(ax, fig, df) if needs_fig else fn(ax, df)
    fig.suptitle(title, x=0.01, ha="left", fontsize=16, fontweight="bold", color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(outdir / "dashboard.png", dpi=130)
    plt.close(fig)
    print(f"  {len(CHARTS) + 1} charts written to {outdir}/")


def print_summary(df):
    print("\nSummary")
    print(f"  spots:          {len(df):,}")
    print(f"  transmitters:   {df['tx_sign'].nunique():,}")
    print(f"  receivers:      {df['rx_sign'].nunique():,}")
    print(f"  max distance:   {df['distance'].max():,} km")
    print(f"  median SNR:     {df['snr'].median():.0f} dB")
    print(f"  memory in RAM:  {df.memory_usage(deep=True).sum() / 1e6:,.0f} MB")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def parse_args():
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    p = argparse.ArgumentParser(description="Load one day of WSPR spots into a pandas file and plot it.")
    p.add_argument("--date", default=yesterday, help="day in UTC, YYYY-MM-DD (default: yesterday)")
    p.add_argument("--band", type=int, default=None, help="only this band code, e.g. 14 for 20 m")
    p.add_argument("--chunk-hours", type=int, default=1, choices=[1, 2, 3, 4, 6, 8, 12, 24])
    p.add_argument("--out", default="wspr_output", help="output folder (default: wspr_output)")
    p.add_argument("--file", help="skip the download and plot an existing .parquet/.pkl file")
    p.add_argument("--force", action="store_true", help="download again even if the file exists")
    return p.parse_args()


def main():
    args = parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tag = args.date + (f"_band{args.band}" if args.band is not None else "")

    if args.file:                                           # plot only
        path = Path(args.file)
        df = load(path)
        tag = path.stem.removeprefix("wspr_")
    else:
        base = out / f"wspr_{tag}"
        existing = [p for p in (base.with_suffix(".parquet"), base.with_suffix(".pkl")) if p.exists()]
        if existing and not args.force:
            path = existing[0]
            print(f"Using existing file {path} (use --force to download again)")
            df = load(path)
        else:
            day = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if day >= datetime.now(timezone.utc):
                sys.exit("The date must lie in the past.")
            band_txt = f"band {args.band}" if args.band is not None else "all bands"
            print(f"Downloading WSPR spots of {args.date} (UTC), {band_txt}")
            df = download_day(day, args.band, args.chunk_hours)
            path = save(df, base)
            print(f"  saved {len(df):,} spots to {path} ({path.stat().st_size / 1e6:,.1f} MB)")

    if df.empty:
        sys.exit("No spots found - nothing to plot.")
    print_summary(df)
    make_plots(df, out / f"plots_{tag}", f"WSPR spots on {tag.replace('_band', ' – band ')} (UTC)")


if __name__ == "__main__":
    main()
