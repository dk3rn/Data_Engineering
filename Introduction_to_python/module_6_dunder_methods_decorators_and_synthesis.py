"""
TH Köln - Data Engineering (Prof. Dr. Peter Kern)
Module 6: Magic Dunder Methods, Decorators (@) & Full Pipeline Synthesis (Pandas + OOP)
"""

from functools import lru_cache
from importlib import import_module
import pandas as pd

# Ensure the sample CSV file exists
module3 = import_module("03_numpy_und_pandas_import")
module3.create_sample_csv("bb12024.csv")


# 1. Custom Decorator using the wrapper pattern
def log_execution(func):
    """Automatically logs the start and completion of a function or method call."""
    def wrapper(*args, **kwargs):
        print(f"  [Decorator Log] Starting '{func.__name__}'...")
        result = func(*args, **kwargs)
        print(f"  [Decorator Log] '{func.__name__}' completed successfully.")
        return result
    return wrapper


# 2. Using @lru_cache for memoization / performance optimization
@lru_cache(maxsize=32)
def compute_saturation_concentration(temperature_c):
    """Approximation formula for dissolved O2 saturation in water (mg/L) with caching."""
    return round(14.62 - 0.3898 * temperature_c + 0.006969 * (temperature_c ** 2), 2)


# 3. Full Synthesis Class: Combines OOP, Dunder Methods, Decorators & Pandas Resampling
class TankAnalysis:
    """Object-oriented analyzer for aeration tank telemetry datasets."""

    def __init__(self, tank_name, csv_path):
        self.name = tank_name
        self.path = csv_path
        self.df = pd.DataFrame()

    @log_execution
    def process_5min(self):
        """Loads the CSV, filters invalid outliers, and performs 5-minute resampling."""
        raw_df = pd.read_csv(self.path)
        raw_df = raw_df[raw_df["nh4_mg_l"].isna() | (raw_df["nh4_mg_l"] >= 0.0)].copy()
        raw_df["zeit"] = pd.to_datetime(raw_df["zeit"])
        raw_df.set_index("zeit", inplace=True)
        self.df = raw_df.resample("5min").mean().interpolate().bfill()

    @property
    def o2_mean(self):
        """Allows attribute-style access (bb1.o2_mean) without parentheses."""
        if self.df.empty:
            return 0.0
        return round(float(self.df["o2_ist"].mean()), 2)

    @property
    def temp_mean(self):
        if self.df.empty:
            return 0.0
        return round(float(self.df["temp_c"].mean()), 1)

    @staticmethod
    def is_temperature_plausible(temp_value):
        """Static utility method without self or cls binding."""
        return 0.0 <= temp_value <= 45.0

    @classmethod
    def default_north_tank(cls):
        """Alternative factory constructor using @classmethod."""
        return cls(tank_name="Aeration Tank 1 (North)", csv_path="bb12024.csv")

    # --- Magic Dunder Methods ---
    def __len__(self):
        """Enables len(bb1) -> returns number of 5-minute intervals."""
        return len(self.df)

    def __getitem__(self, index):
        """Enables bracket indexing bb1[0] just like a Python list."""
        return self.df.iloc[index]

    def __eq__(self, other):
        """Compares two TankAnalysis instances for content equality via ==."""
        if not isinstance(other, TankAnalysis):
            return False
        return self.name == other.name and len(self) == len(other)

    def __call__(self):
        """Makes the instance itself callable like a function: bb1()."""
        print(f"=== Report {self.name} (5min Grid) ===")
        print(
            f"Intervals: {len(self)} | O2 Mean: {self.o2_mean:.2f} mg/L "
            f"| Temp Mean: {self.temp_mean:.1f} °C"
        )

    def __str__(self):
        """Human-readable representation for print(bb1)."""
        return f"TankAnalysis('{self.name}', Rows={len(self)}, O2={self.o2_mean} mg/L)"

    def __repr__(self):
        """Official unambiguous representation for developer debugging."""
        return f"TankAnalysis(tank_name='{self.name}', csv_path='{self.path}')"


if __name__ == "__main__":
    print("=== MODULE 6: DUNDER METHODS, DECORATORS & FULL SYNTHESIS ===")

    # Instantiate via @classmethod and run pipeline (logged via @log_execution)
    bb1 = TankAnalysis.default_north_tank()
    bb1.process_5min()

    # Demonstrate Dunder Methods (__str__, __repr__, __len__, __getitem__, __call__)
    print("\nOutput via print(bb1) [__str__] :", bb1)
    print("Output via repr(bb1)  [__repr__]:", repr(bb1))
    print("5-minute intervals    [__len__] :", len(bb1))
    print("First interval bb1[0] [__getitem__]:", dict(bb1[0].round(2)))

    # Call the object directly as a function (__call__)
    print()
    bb1()

    # Test @staticmethod and @lru_cache
    t_avg = bb1.temp_mean
    print(
        f"\nTemperature {t_avg} °C plausible? {TankAnalysis.is_temperature_plausible(t_avg)} "
        f"| O2 Saturation: {compute_saturation_concentration(t_avg)} mg/L"
    )