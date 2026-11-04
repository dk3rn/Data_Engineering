"""
TH Köln - Data Engineering (Prof. Dr. Peter Kern)
Module 2: Clean Code (DRY Principle), Functions, Variable Scope & Exception Handling (try/except)
"""

# Global constant (demonstrating variable scope)
PLANT_NAME = "Wastewater Treatment Plant Cologne-North"


def compute_mean(values):
    """Computes the arithmetic mean of a numeric list (DRY principle)."""
    if len(values) == 0:
        return 0.0

    # 'total' is a LOCAL variable and is invisible outside this function
    total = 0.0
    for val in values:
        total += val
    return round(total / len(values), 2)


def filter_outliers(data, threshold=50.0):
    """
    Keeps only measurements <= threshold.
    Demonstrates default parameters and returning multiple values as a tuple.
    """
    cleaned = []
    removed_count = 0
    for w in data:
        if w <= threshold:
            cleaned.append(w)
        else:
            removed_count += 1
    return cleaned, removed_count


def compute_safe_mean(raw_list):
    """
    Safely catches sensor faults ('Error', 'TIMEOUT') via try / except ValueError
    so that continuous data ingestion pipelines never crash.
    """
    clean_values = []
    for entry in raw_list:
        try:
            val = float(entry)
            clean_values.append(val)
        except ValueError:
            print(f"  [Warning] Ignoring corrupted sensor string: '{entry}'")

    if not clean_values:
        return 0.0
    return compute_mean(clean_values)


if __name__ == "__main__":
    print(f"=== MODULE 2: CLEAN CODE & EXCEPTION HANDLING ({PLANT_NAME}) ===")

    # 1. Reusable function instead of copy-paste loops
    tank_1 = [4.2, 4.5, 4.1, 4.4]
    tank_2 = [1.8, 2.1, 1.9, 2.0]
    print(f"O2 Mean Tank 1: {compute_mean(tank_1)} mg/L")
    print(f"O2 Mean Tank 2: {compute_mean(tank_2)} mg/L")

    # 2. Default parameters & keyword arguments
    raw_data = [4.1, 4.3, 999.9, 4.0, 85.2, 4.2]
    ok_std, rem_std = filter_outliers(raw_data)                   # uses default 50.0
    ok_str, rem_str = filter_outliers(raw_data, threshold=10.0)   # custom threshold 10.0
    print(f"Default Filter (<=50.0): {ok_std} ({rem_std} outliers removed)")
    print(f"Strict Filter  (<=10.0): {ok_str} ({rem_str} outliers removed)")

    # 3. Robust processing of a faulty serial sensor stream
    sensor_stream = ["4.2", "4.5", "Error", "4.1", "TIMEOUT", "4.4"]
    safe_mean = compute_safe_mean(sensor_stream)
    print(f"Safe mean despite sensor faults: {safe_mean} mg/L\n")