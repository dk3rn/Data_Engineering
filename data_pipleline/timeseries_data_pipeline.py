#!/usr/bin/env python3
"""
timeseries_data_pipeline.py
===========================
A complete, step-by-step data pipeline for time-series (sensor) data:

    STEP 0  Configuration
    STEP 1  Generate synthetic raw data (with realistic data-quality problems)
    STEP 2  Extract      - read the raw CSV file
    STEP 3  Profile      - look at the data BEFORE changing anything
    STEP 4  Clean        - types, duplicates, labels, units, sorting
    STEP 5  Outliers     - rule-based + statistical (Z-score, IQR, Hampel)
    STEP 6  Gaps         - regular time grid + interpolation of short gaps
    STEP 7  Normalize    - min-max, z-score, robust scaling
    STEP 8  Aggregate    - hourly / daily features
    STEP 9  Load         - store the results in CSV files and a SQLite database
    STEP 10 Visualize    - charts that show what each step did
    STEP 11 Report       - a short data-quality report

Scenario
--------
Three production machines (M1, M2, M3) report every 10 minutes:
    * temperature in °C
    * vibration   in mm/s
The raw export is "dirty", exactly like real-world data usually is.

Requirements:   pip install numpy pandas matplotlib
Run:            python timeseries_data_pipeline.py
Output:         folder ./pipeline_output  (CSV, SQLite DB, PNG charts, report)
"""

# =============================================================================
# STEP 0 - Imports and configuration
# =============================================================================
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")                    # draw into files, no window needed
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# All settings in one place - change them here, not inside the code.
CONFIG = {
    "seed": 42,                          # same seed -> same "random" data every run
    "start": "2026-10-01 00:00",         # first timestamp
    "days": 30,                          # length of the time series
    "freq": "10min",                     # sampling interval of the sensors
    "machines": ["M1", "M2", "M3"],
    "output_dir": Path("pipeline_output"),

    # physical limits: values outside are impossible -> sensor error
    "limits": {"temperature_c": (-20.0, 150.0), "vibration_mm_s": (0.0, 50.0)},
    # Hampel filter: window for the local median (samples) and threshold (in robust sigmas)
    "hampel_window": 13,                 # 13 x 10 min = ~2 hours
    "hampel_threshold": 4.0,          # 4 sigma -> very few false alarms
    # gaps up to this many missing samples are interpolated (3 x 10 min = 30 min)
    "max_interpolation_gap": 3,
}

OUT = CONFIG["output_dir"]
OUT.mkdir(exist_ok=True)
RAW_CSV = OUT / "01_raw_sensor_data.csv"

# Colors for the charts (one per machine + a highlight color for outliers)
COLORS = {"M1": "#2a78d6", "M2": "#eb6834", "M3": "#1baf7a"}
OUTLIER_COLOR = "#e34948"
INK, INK_2, GRID = "#0b0b0b", "#52514e", "#e4e3df"

# The report collects numbers from every step (data lineage!)
report = {}


def log(title):
    """Prints a visible step header to the console."""
    print("\n" + "=" * 70 + f"\n{title}\n" + "=" * 70)


# =============================================================================
# STEP 1 - Generate synthetic raw data
# =============================================================================
# In a real project this data would come from a machine, an API or a database.
# Here we create it ourselves, so we KNOW which problems are hidden inside and
# can check whether the pipeline finds them.
def generate_raw_data(cfg) -> pd.DataFrame:
    log("STEP 1 - Generate synthetic raw data")
    rng = np.random.default_rng(cfg["seed"])
    timestamps = pd.date_range(cfg["start"], periods=cfg["days"] * 144, freq=cfg["freq"])
    t_hours = np.arange(len(timestamps)) / 6                  # time in hours

    frames = []
    for i, machine in enumerate(cfg["machines"]):
        # --- 1a) the "true" physical signal --------------------------------
        base = 60 + 8 * i                                        # each machine runs at its own level
        daily_cycle = 6 * np.sin(2 * np.pi * (t_hours - 8) / 24)  # warmer during the day shift
        trend = 0.08 * t_hours / 24                              # slow wear: +0.08 °C per day
        temperature = base + daily_cycle + trend + rng.normal(0, 0.8, len(t_hours))

        # vibration correlates with temperature + noise, always positive
        vibration = np.abs(2.5 + 0.15 * (temperature - base) + rng.normal(0, 0.4, len(t_hours)))

        df = pd.DataFrame({
            "timestamp": timestamps.strftime("%Y-%m-%d %H:%M:%S"),
            "machine_id": machine,
            "temperature": temperature.round(2),
            "unit": "C",
            "vibration_mm_s": vibration.round(3),
        })
        frames.append(df)

    raw = pd.concat(frames, ignore_index=True)
    n = len(raw)

    # --- 1b) now we inject typical data-quality problems --------------------
    # (i) single spikes (sensor glitches) - statistical outliers
    idx = rng.choice(n, size=60, replace=False)
    raw.loc[idx, "temperature"] += rng.choice([-1, 1], 60) * rng.uniform(12, 30, 60)
    idx = rng.choice(n, size=40, replace=False)
    raw.loc[idx, "vibration_mm_s"] *= rng.uniform(3, 6, 40)

    # (ii) error codes: the sensor writes -999 when it fails - physically impossible
    idx = rng.choice(n, size=25, replace=False)
    raw.loc[idx, "temperature"] = -999.0

    # (iii) one machine sometimes reports in Fahrenheit (firmware bug)
    m3 = raw.index[raw["machine_id"] == "M3"]
    idx = rng.choice(m3, size=150, replace=False)
    raw.loc[idx, "temperature"] = (raw.loc[idx, "temperature"] * 9 / 5 + 32).round(2)
    raw.loc[idx, "unit"] = "F"

    # (iv) values become text: missing values written in different ways,
    #      and German decimal commas ("71,5" instead of 71.5)
    raw["temperature"] = raw["temperature"].astype(object)
    idx = rng.choice(n, size=120, replace=False)
    raw.loc[idx, "temperature"] = rng.choice(["", "n/a", "NULL", "-"], 120)
    idx = rng.choice(np.setdiff1d(np.arange(n), idx), size=80, replace=False)
    raw.loc[idx, "temperature"] = [str(v).replace(".", ",") for v in raw.loc[idx, "temperature"]]

    # (v) inconsistent labels: " m1", "M2 ", "m3"
    idx = rng.choice(n, size=200, replace=False)
    raw.loc[idx, "machine_id"] = [f" {m.lower()} " for m in raw.loc[idx, "machine_id"]]

    # (vi) a sensor outage: M2 sends nothing for 6 hours
    outage = (raw["machine_id"].str.strip().str.upper() == "M2") & \
             raw["timestamp"].between("2026-10-12 08:00:00", "2026-10-12 13:59:59")
    raw = raw[~outage]

    # (vii) duplicated rows (the export ran twice for some records)
    raw = pd.concat([raw, raw.sample(150, random_state=cfg["seed"])])

    # (viii) wrong order: the file is not sorted by time
    raw = raw.sample(frac=1, random_state=cfg["seed"]).reset_index(drop=True)

    raw.to_csv(RAW_CSV, index=False)
    print(f"Raw data written to {RAW_CSV}  ({len(raw):,} rows)")
    return raw


# =============================================================================
# STEP 2 - Extract
# =============================================================================
# We read EVERYTHING as text (dtype=str). Reason: if pandas guesses the types
# itself, one bad value like "n/a" turns a whole column into "object" or
# silently becomes NaN. We want to control every conversion ourselves.
def extract(path: Path) -> pd.DataFrame:
    log("STEP 2 - Extract: read the raw CSV")
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    print(f"{len(df):,} rows, columns: {list(df.columns)}")
    report["rows_raw"] = len(df)
    return df


# =============================================================================
# STEP 3 - Profile (look before you clean!)
# =============================================================================
def profile(df: pd.DataFrame):
    log("STEP 3 - Profile the raw data")
    print(df.head(8).to_string(index=False))
    print("\nDistinct machine labels :", sorted(df["machine_id"].unique()))
    print("Distinct units          :", sorted(df["unit"].unique()))
    non_numeric = ~df["temperature"].str.replace(",", ".", regex=False) \
                                    .str.fullmatch(r"-?\d+(\.\d+)?")
    print("Non-numeric temperatures:", df.loc[non_numeric, "temperature"].value_counts().to_dict())
    print("Exact duplicate rows    :", df.duplicated().sum())
    print("Sorted by time?         :", df["timestamp"].is_monotonic_increasing)


# =============================================================================
# STEP 4 - Clean: types, labels, duplicates, units, order
# =============================================================================
def clean(df: pd.DataFrame) -> pd.DataFrame:
    log("STEP 4 - Clean")
    df = df.copy()

    # 4a) Standardize labels: remove spaces, upper case -> " m1 " becomes "M1"
    df["machine_id"] = df["machine_id"].str.strip().str.upper()
    unknown = ~df["machine_id"].isin(CONFIG["machines"])
    df = df[~unknown]
    print(f"4a) labels standardized, {unknown.sum()} rows with unknown machine removed")

    # 4b) Convert the timestamp text into real datetime objects.
    #     errors="coerce" turns unreadable timestamps into NaT (not a time).
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    bad_ts = df["timestamp"].isna().sum()
    df = df.dropna(subset=["timestamp"])
    print(f"4b) timestamps parsed, {bad_ts} unreadable timestamps removed")

    # 4c) Convert the measurements into numbers.
    #     Decimal comma -> decimal point, then to_numeric. "n/a", "", "NULL"
    #     cannot be converted and become NaN (= missing value).
    temp_text = df["temperature"].str.replace(",", ".", regex=False)
    df["temperature"] = pd.to_numeric(temp_text, errors="coerce")
    df["vibration_mm_s"] = pd.to_numeric(df["vibration_mm_s"], errors="coerce")
    report["missing_values"] = int(df["temperature"].isna().sum())
    print(f"4c) numbers converted, {report['missing_values']} missing temperature values")

    # 4d) Remove duplicates. A measurement is identified by machine + time.
    #     keep="first": if the same key appears twice, keep one row.
    before = len(df)
    df = df.drop_duplicates(subset=["machine_id", "timestamp"], keep="first")
    report["duplicates"] = before - len(df)
    print(f"4d) {report['duplicates']} duplicates removed")

    # 4e) Harmonize units: everything in °C.  °C = (°F - 32) * 5/9
    #     (-999 error codes are left untouched; they are handled in STEP 5)
    is_f = (df["unit"].str.upper() == "F") & (df["temperature"] != -999)
    df.loc[is_f, "temperature"] = (df.loc[is_f, "temperature"] - 32) * 5 / 9
    df["unit"] = "C"
    df = df.rename(columns={"temperature": "temperature_c"}).drop(columns="unit")
    report["unit_conversions"] = int(is_f.sum())
    print(f"4e) {report['unit_conversions']} values converted from °F to °C")

    # 4f) Sort by machine and time - required for all time-series operations
    df = df.sort_values(["machine_id", "timestamp"]).reset_index(drop=True)
    print("4f) sorted by machine and timestamp")
    return df


# =============================================================================
# STEP 5 - Outlier detection
# =============================================================================
# We combine two kinds of checks:
#   (1) RULE-BASED   : domain knowledge - a value outside the physical limits
#                      or an error code can never be a real measurement.
#   (2) STATISTICAL  : values that are "unusual" compared to their neighbours.
#
# For time series a GLOBAL test (z-score / IQR over the whole month) is often
# wrong: the daily cycle and the trend make normal values look extreme.
# A LOCAL test (Hampel filter = rolling median + MAD) compares each value
# with its neighbours in time - that is the method we use for cleaning.
# Z-score and IQR are computed as well, only for comparison in the report.
def zscore_outliers(s: pd.Series, threshold=3.0) -> pd.Series:
    z = (s - s.mean()) / s.std()
    return z.abs() > threshold


def iqr_outliers(s: pd.Series, k=1.5) -> pd.Series:
    q1, q3 = s.quantile([0.25, 0.75])
    iqr = q3 - q1
    return (s < q1 - k * iqr) | (s > q3 + k * iqr)


def hampel_outliers(s: pd.Series, window: int, threshold: float) -> pd.Series:
    """
    Hampel-type filter (robust, local):
        1. local level   : median of a short centered window (~2 h)
                           -> follows the daily cycle and the trend
        2. residual      : r_t = x_t - local median
        3. robust spread : sigma = 1.4826 * median(|r|) over one day
                           (1.4826 scales the MAD so that it equals the
                            standard deviation for normally distributed noise)
        4. outlier       : |r_t| > threshold * sigma
    Median and MAD are robust: a spike hardly changes them, whereas mean
    and standard deviation would be pulled towards the outlier.
    """
    median = s.rolling(window, center=True, min_periods=3).median()
    resid = s - median
    sigma = 1.4826 * resid.abs().rolling(144, center=True, min_periods=12).median()
    return resid.abs() > threshold * sigma


def detect_outliers(df: pd.DataFrame) -> pd.DataFrame:
    log("STEP 5 - Outlier detection")
    df = df.copy()
    comparison = []

    for col, (low, high) in CONFIG["limits"].items():
        # (1) rule-based: physically impossible values
        rule = (df[col] < low) | (df[col] > high)

        # (2) statistical, per machine (each machine has its own normal level!)
        hampel = pd.Series(False, index=df.index)
        z = pd.Series(False, index=df.index)
        iqr = pd.Series(False, index=df.index)
        for _, g in df[~rule].groupby("machine_id"):
            s = g[col]
            hampel.loc[g.index] = hampel_outliers(s, CONFIG["hampel_window"], CONFIG["hampel_threshold"])
            z.loc[g.index] = zscore_outliers(s)
            iqr.loc[g.index] = iqr_outliers(s)

        flag = rule | hampel
        df[f"{col}_outlier"] = flag              # keep the flag -> traceability
        df[f"{col}_raw"] = df[col]               # keep the original value
        df.loc[flag, col] = np.nan               # outliers become missing values

        comparison.append({"column": col, "rule_based": int(rule.sum()),
                           "z_score(global)": int(z.sum()), "IQR(global)": int(iqr.sum()),
                           "hampel(local)": int(hampel.sum()), "removed": int(flag.sum())})

    table = pd.DataFrame(comparison).set_index("column")
    print(table.to_string())
    print("\nNote: global z-score / IQR find far fewer spikes, because the daily"
          "\ncycle widens the 'normal' range. The local Hampel filter is used.")
    report["outliers"] = table
    return df


# =============================================================================
# STEP 6 - Regular time grid and gap filling
# =============================================================================
# Many analyses (rolling windows, FFT, machine learning) need a REGULAR grid:
# exactly one row every 10 minutes. Missing timestamps are inserted as NaN.
# Short gaps are interpolated in time; long gaps (sensor outage) stay missing,
# because inventing 6 hours of data would be misleading.
def fill_gaps(df: pd.DataFrame) -> pd.DataFrame:
    log("STEP 6 - Regular time grid and gap filling")
    limit = CONFIG["max_interpolation_gap"]
    parts = []
    for machine, g in df.groupby("machine_id"):
        g = g.set_index("timestamp")
        full_index = pd.date_range(g.index.min(), g.index.max(), freq=CONFIG["freq"])
        g = g.reindex(full_index)                  # inserts missing timestamps
        g.index.name = "timestamp"
        g["machine_id"] = machine
        g["was_missing"] = g["temperature_c"].isna()

        for col in CONFIG["limits"]:
            # limit_area="inside": only fill BETWEEN two known values
            filled = g[col].interpolate(method="time", limit_area="inside")
            # but only for gaps of at most `limit` samples:
            gap_id = g[col].notna().cumsum()
            gap_len = g[col].isna().groupby(gap_id).transform("sum")
            g[col] = filled.where(gap_len <= limit, g[col])
        g["interpolated"] = g["was_missing"] & g["temperature_c"].notna()
        parts.append(g.reset_index())

    out = pd.concat(parts, ignore_index=True)
    report["interpolated"] = int(out["interpolated"].sum())
    report["still_missing"] = int(out["temperature_c"].isna().sum())
    print(f"{report['interpolated']} values interpolated (gaps <= {limit} samples)")
    print(f"{report['still_missing']} values left missing (long gaps, e.g. the M2 outage)")
    return out


# =============================================================================
# STEP 7 - Normalization
# =============================================================================
# Why normalize? M1 runs at ~60 °C, M3 at ~76 °C, vibration is in mm/s.
# To compare shapes, or to feed values into machine learning, all signals
# should be on a common scale. We compute three common variants PER MACHINE:
#   min-max : (x - min) / (max - min)          -> range 0 .. 1
#   z-score : (x - mean) / std                 -> mean 0, std 1
#   robust  : (x - median) / IQR               -> insensitive to outliers
# IMPORTANT: in machine learning, compute min/max/mean/std on the TRAINING
# data only and reuse them for test data - otherwise information leaks.
def normalize(df: pd.DataFrame) -> pd.DataFrame:
    log("STEP 7 - Normalization (per machine)")
    df = df.copy()
    g = df.groupby("machine_id")
    for col in CONFIG["limits"]:
        x = df[col]
        mn, mx = g[col].transform("min"), g[col].transform("max")
        mean, std = g[col].transform("mean"), g[col].transform("std")
        med = g[col].transform("median")
        iqr = g[col].transform(lambda s: s.quantile(0.75) - s.quantile(0.25))
        df[f"{col}_minmax"] = (x - mn) / (mx - mn)
        df[f"{col}_zscore"] = (x - mean) / std
        df[f"{col}_robust"] = (x - med) / iqr
    check = df.groupby("machine_id")[["temperature_c_minmax", "temperature_c_zscore"]] \
              .agg(["min", "max", "mean"]).round(2)
    print(check.to_string())
    return df


# =============================================================================
# STEP 8 - Aggregation / feature engineering
# =============================================================================
def aggregate(df: pd.DataFrame):
    log("STEP 8 - Aggregation")
    df = df.copy()
    # rolling 1-hour mean (6 samples) - smooths the noise
    df["temperature_c_rolling_1h"] = df.groupby("machine_id")["temperature_c"] \
                                       .transform(lambda s: s.rolling(6, min_periods=3).mean())
    # group by machine AND calendar day (pd.Grouper splits the time axis)
    daily = (df.groupby(["machine_id", pd.Grouper(key="timestamp", freq="1D")])
               [["temperature_c", "vibration_mm_s"]]
               .agg(["mean", "min", "max", "count"]))
    daily.columns = ["_".join(c) for c in daily.columns]           # flatten column names
    daily = daily.reset_index()
    # data completeness per day: 144 samples are expected
    daily["completeness_pct"] = (daily["temperature_c_count"] / 144 * 100).round(1)
    print(daily.head(6).to_string(index=False, float_format="%.2f"))
    return df, daily


# =============================================================================
# STEP 9 - Load: store the results
# =============================================================================
def load(clean_df: pd.DataFrame, daily: pd.DataFrame):
    log("STEP 9 - Load: CSV files and SQLite database")
    clean_df.to_csv(OUT / "02_clean_sensor_data.csv", index=False)
    daily.to_csv(OUT / "03_daily_aggregates.csv", index=False)

    db_path = OUT / "sensor_data.db"
    with sqlite3.connect(db_path) as conn:
        # timestamps as ISO text - SQLite has no DATETIME type
        c = clean_df.assign(timestamp=clean_df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S"))
        d = daily.assign(timestamp=daily["timestamp"].dt.strftime("%Y-%m-%d"))
        c.to_sql("measurement", conn, if_exists="replace", index=False)
        d.to_sql("daily_aggregate", conn, if_exists="replace", index=False)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_meas ON measurement(machine_id, timestamp)")
        n = conn.execute("SELECT COUNT(*) FROM measurement").fetchone()[0]
    print(f"Saved CSV files and {db_path} ({n:,} rows in table 'measurement')")


# =============================================================================
# STEP 10 - Visualization
# =============================================================================
def style(ax, title, ylabel=None):
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold", color=INK)
    if ylabel:
        ax.set_ylabel(ylabel, color=INK_2)
    ax.tick_params(colors=INK_2, labelsize=8, length=0)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def plot_raw_vs_clean(ax, df, machine="M1", days=("2026-10-08", "2026-10-15")):
    """Chart 1: what did cleaning + outlier removal do to one week of M1?"""
    g = df[(df["machine_id"] == machine) & df["timestamp"].between(*days)]
    low, high = CONFIG["limits"]["temperature_c"]
    # error codes like -999 would squash the y-axis -> hide them in the raw line
    raw_plot = g["temperature_c_raw"].where(g["temperature_c_raw"].between(low, high))
    n_codes = int((g["temperature_c_raw"] < low).sum())
    ax.plot(g["timestamp"], raw_plot, color="#b8b7b0", linewidth=1,
            label=f"raw (after type/unit fix, {n_codes} error codes hidden)")
    ax.plot(g["timestamp"], g["temperature_c"], color=COLORS[machine], linewidth=1.5, label="clean")
    out = g[g["temperature_c_outlier"] & g["temperature_c_raw"].between(-20, 150)]
    ax.scatter(out["timestamp"], out["temperature_c_raw"], color=OUTLIER_COLOR, marker="x", s=40,
               linewidths=1.5, zorder=3, label=f"outliers removed ({len(out)})")
    ax.legend(fontsize=8, frameon=False, loc="lower right", ncol=3)
    ax.set_ylim(g["temperature_c"].min() - 30, g["temperature_c"].max() + 30)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m."))
    style(ax, f"{machine}: temperature, raw vs. clean (one week)", "°C")


def plot_outlier_methods(ax):
    """Chart 2: how many outliers does each method find?"""
    t = report["outliers"].loc["temperature_c", ["rule_based", "z_score(global)", "IQR(global)", "hampel(local)"]]
    bars = ax.bar(t.index, t.values, color=["#b8b7b0", "#b8b7b0", "#b8b7b0", COLORS["M1"]], width=0.6)
    for b, v in zip(bars, t.values):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v}", ha="center", va="bottom", fontsize=9, color=INK_2)
    style(ax, "Temperature outliers found per method", "flagged values")


def plot_quality_steps(ax):
    """Chart 3: what happened in each cleaning step?"""
    steps = {
        "duplicates\nremoved": report["duplicates"],
        "°F → °C\nconverted": report["unit_conversions"],
        "missing /\nunreadable": report["missing_values"],
        "outliers\nremoved": int(report["outliers"]["removed"].sum()),
        "values\ninterpolated": report["interpolated"],
        "still\nmissing": report["still_missing"],
    }
    ax.barh(list(steps)[::-1], list(steps.values())[::-1], color=COLORS["M1"], height=0.6)
    for y, v in enumerate(list(steps.values())[::-1]):
        ax.text(v, y, f"  {v}", va="center", fontsize=9, color=INK_2)
    ax.set_xlim(0, max(steps.values()) * 1.2)
    style(ax, "Data-quality actions per step")
    ax.yaxis.grid(False)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)


def plot_distributions(ax, df):
    """Chart 4: distribution per machine after cleaning (box plot)."""
    data = [df.loc[df["machine_id"] == m, "temperature_c"].dropna() for m in CONFIG["machines"]]
    bp = ax.boxplot(data, patch_artist=True, widths=0.5, showfliers=False)
    ax.set_xticks(range(1, len(CONFIG["machines"]) + 1), CONFIG["machines"])
    for patch, m in zip(bp["boxes"], CONFIG["machines"]):
        patch.set_facecolor(COLORS[m]); patch.set_edgecolor("white")
    for part in ("medians", "whiskers", "caps"):
        for line in bp[part]:
            line.set_color(INK_2)
    style(ax, "Clean temperature per machine", "°C")


def plot_normalized(ax, df, day="2026-10-20"):
    """Chart 5: after z-score normalization the machines become comparable."""
    for m in CONFIG["machines"]:
        g = df[(df["machine_id"] == m) & (df["timestamp"].dt.strftime("%Y-%m-%d") == day)]
        ax.plot(g["timestamp"], g["temperature_c_zscore"], color=COLORS[m], linewidth=1.5, label=m)
    ax.axhline(0, color=INK_2, linewidth=0.8)
    ax.legend(fontsize=8, frameon=False, ncol=3, loc="upper left")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    style(ax, f"Z-score normalized temperature on {day}", "z-score (σ)")


def plot_daily(ax, daily):
    """Chart 6: daily mean temperature - the slow upward trend becomes visible.
    Watch M2 on 12.10.: the 6-hour outage removed the warm midday hours, so the
    daily mean is biased low -> always check completeness_pct before trusting
    an aggregate!"""
    for m in CONFIG["machines"]:
        g = daily[daily["machine_id"] == m]
        ax.plot(g["timestamp"], g["temperature_c_mean"], color=COLORS[m], linewidth=2, marker="o",
                markersize=3, label=m)
        ax.text(g["timestamp"].iloc[-1], g["temperature_c_mean"].iloc[-1], f"  {m}",
                color=INK, fontsize=8, va="center")
    ax.legend(fontsize=8, frameon=False, ncol=3, loc="upper left")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m."))
    style(ax, "Daily mean temperature", "°C")


def visualize(df, daily):
    log("STEP 10 - Visualization")
    plt.rcParams.update({"font.family": "DejaVu Sans", "figure.facecolor": "white"})
    charts = [
        ("1_raw_vs_clean", lambda ax: plot_raw_vs_clean(ax, df)),
        ("2_outlier_methods", plot_outlier_methods),
        ("3_quality_steps", plot_quality_steps),
        ("4_distributions", lambda ax: plot_distributions(ax, df)),
        ("5_normalized", lambda ax: plot_normalized(ax, df)),
        ("6_daily_mean", lambda ax: plot_daily(ax, daily)),
    ]
    # one PNG per chart ...
    for name, fn in charts:
        fig, ax = plt.subplots(figsize=(10, 4.5))
        fn(ax)
        fig.tight_layout()
        fig.savefig(OUT / f"chart_{name}.png", dpi=150)
        plt.close(fig)

    # ... and a dashboard with all charts on one page
    fig = plt.figure(figsize=(16, 15))
    grid = fig.add_gridspec(3, 2, hspace=0.35, wspace=0.18, top=0.94)
    axes = [fig.add_subplot(grid[0, :]), fig.add_subplot(grid[1, 0]), fig.add_subplot(grid[1, 1]),
            fig.add_subplot(grid[2, 0]), fig.add_subplot(grid[2, 1])]
    for ax, (_, fn) in zip(axes, [charts[0], charts[2], charts[1], charts[4], charts[5]]):
        fn(ax)
    fig.suptitle("Sensor data pipeline - from raw export to clean, normalized data",
                 x=0.06, y=0.98, ha="left", fontsize=16, fontweight="bold", color=INK)
    fig.savefig(OUT / "dashboard.png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"{len(charts)} charts + dashboard.png written to {OUT}/")


# =============================================================================
# STEP 11 - Report
# =============================================================================
def write_report():
    log("STEP 11 - Data-quality report")
    lines = [
        "DATA-QUALITY REPORT",
        "===================",
        f"rows in raw file              : {report['rows_raw']:,}",
        f"duplicates removed            : {report['duplicates']:,}",
        f"°F values converted to °C     : {report['unit_conversions']:,}",
        f"missing / unreadable values   : {report['missing_values']:,}",
        f"values interpolated           : {report['interpolated']:,}",
        f"values still missing          : {report['still_missing']:,}",
        f"rows in clean data            : {report['rows_clean']:,}",
        "",
        "Outliers per method:",
        report["outliers"].to_string(),
    ]
    text = "\n".join(lines)
    (OUT / "report.txt").write_text(text, encoding="utf-8")
    print(text)


# =============================================================================
# Run the pipeline
# =============================================================================
# Each function takes a DataFrame and returns a new one -> every step can be
# tested on its own, and the order of the steps is visible in one place.
def main():
    generate_raw_data(CONFIG)          # 1  (in real life: data arrives from outside)
    raw = extract(RAW_CSV)             # 2
    profile(raw)                       # 3
    df = clean(raw)                    # 4
    df = detect_outliers(df)           # 5
    df = fill_gaps(df)                 # 6
    df = normalize(df)                 # 7
    df, daily = aggregate(df)          # 8
    report["rows_clean"] = len(df)
    load(df, daily)                    # 9
    visualize(df, daily)               # 10
    write_report()                     # 11
    print(f"\nPipeline finished. All results are in the folder '{OUT}'.")


if __name__ == "__main__":
    main()
