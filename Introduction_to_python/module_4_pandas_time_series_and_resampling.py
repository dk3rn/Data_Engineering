"""
TH Köln - Data Engineering (Prof. Dr. Peter Kern)
Module 4: Data Cleaning (NaN), DatetimeIndex & 5-Minute Time-Series Resampling
"""

import pandas as pd
from importlib import import_module

# Ensure the sample CSV from Module 3 exists
module3 = import_module("module_3_numpy_and_pandas_data_ingestion")
module3.create_sample_csv("bb12024.csv")


def load_and_resample(filepath="bb12024.csv"):
    """
    4-Step Standard Pipeline for Industrial Telemetry and Sensor Data:
    1. Load CSV & remove physically impossible outliers
    2. Diagnose missing values (NaN) and close gaps via ffill / interpolate
    3. Convert timestamp column via pd.to_datetime() and set as index
    4. Synchronize asynchronous readings via resample('5min').mean()
    """
    print("=== MODULE 4: DATA CLEANING & TIME-SERIES RESAMPLING ===")
    df = pd.read_csv(filepath)

    # Diagnose missing values prior to cleaning
    print("Missing values (NaN) per column before cleaning:")
    print(df.isna().sum())

    # Step 1: Remove physically impossible negative concentrations (< 0 mg/L)
    df = df[df["nh4_mg_l"].isna() | (df["nh4_mg_l"] >= 0.0)].copy()

    # Step 2: Fill brief sensor dropouts (Forward Fill & Linear Interpolation)
    df["o2_ist"] = df["o2_ist"].ffill()
    df["nh4_mg_l"] = df["nh4_mg_l"].interpolate()
    df = df.dropna()

    # Step 3: Convert string timestamps into genuine datetime64[ns] objects
    print(f"\nDtype of 'zeit' before conversion: {df['zeit'].dtype}")
    df["zeit"] = pd.to_datetime(df["zeit"], errors="coerce")
    print(f"Dtype of 'zeit' after conversion : {df['zeit'].dtype}")

    # Set timestamp column as DatetimeIndex (required for resampling)
    df.set_index("zeit", inplace=True)

    # Step 4: Strict 5-minute resampling (mean aggregation) & gap interpolation
    df_5min = df.resample("5min").mean().interpolate()

    print("\n--- Synchronized Dataset on an Exact 5-Minute Grid ---")
    print(df_5min.round(2))
    return df_5min


if __name__ == "__main__":
    load_and_resample("bb12024.csv")