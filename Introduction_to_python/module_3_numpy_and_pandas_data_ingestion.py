"""
TH Köln - Data Engineering (Prof. Dr. Peter Kern)
Module 3: NumPy Arrays vs. Pandas DataFrames, CSV Ingestion & Statistical Inspection
"""

import numpy as np
import pandas as pd


def create_sample_csv(filepath="bb12024.csv"):
    """Generates a realistic process telemetry CSV with asynchronous timestamps and NaN gaps."""
    data = {
        "zeit": [
            "2024-01-01 00:01:00",
            "2024-01-01 00:04:00",
            "2024-01-01 00:07:00",
            "2024-01-01 00:09:00",
            "2024-01-01 00:11:00",
            "2024-01-01 00:14:00",
            "2024-01-01 00:18:00",
        ],
        "o2_ist": [2.14, 2.08, np.nan, 0.42, 1.95, 2.02, 0.38],
        "o2_soll": [2.00, 2.00, 2.00, 2.00, 2.00, 2.00, 2.00],
        "nh4_mg_l": [1.85, 1.88, 1.92, -0.50, 1.95, np.nan, 1.89],
        "temp_c": [11.4, 11.4, 11.3, 11.3, 11.3, 11.2, 11.2],
    }
    df_export = pd.DataFrame(data)
    df_export.to_csv(filepath, index=False)
    return filepath


def demonstrate_numpy_and_pandas():
    print("=== MODULE 3: NUMPY ARRAYS & PANDAS DATAFRAMES ===")

    # 1. Difference between a standard Python list and a NumPy array (ndarray)
    python_list = [1, 2, 3]
    numpy_array = np.array([1, 2, 3])
    print("Python List * 2 (List duplication)       :", python_list * 2)
    print("NumPy Array * 2 (Vector multiplication)  :", numpy_array * 2)

    # 2. Generate CSV file and load it via pd.read_csv()
    path = create_sample_csv("bb12024.csv")
    df = pd.read_csv(path)

    rows, cols = df.shape
    print(f"\nCSV '{path}' loaded -> Shape: {rows} rows, {cols} columns")
    print("Column names:", list(df.columns))

    # 3. Visual inspection (head), structure check (info) & summary statistics (describe)
    print("\n--- 1. Visual Inspection: df.head(4) ---")
    print(df.head(4))

    print("\n--- 2. Structure Inspection: df.info() ---")
    df.info()

    print("\n--- 3. Statistical Summary: df.describe() ---")
    print(df.describe().round(2))

    # 4. Column selection and Boolean Indexing (filtering)
    mean_temp = df["temp_c"].mean()
    critical_o2_rows = df[df["o2_ist"] < 0.5]
    print(f"\nMean Temperature: {mean_temp:.2f} °C")
    print(f"Number of critical O2 readings (< 0.5 mg/L): {len(critical_o2_rows)}\n")


if __name__ == "__main__":
    demonstrate_numpy_and_pandas()