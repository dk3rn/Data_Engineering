"""
TH Köln - Data Engineering (Prof. Dr. Peter Kern)
Module 1: Python Fundamentals, Dynamic Typing, Control Flow & Built-in Data Structures
"""

import math
from datetime import datetime


def demonstrate_fundamentals():
    print("=== MODULE 1: PYTHON FUNDAMENTALS & DATA STRUCTURES ===")

    # 1. Dynamic Typing & Primitive Data Types
    plant_id = 101                       # int (integer)
    o2_reading = 23.5                    # float (floating-point number)
    sensor_active = True                 # bool (boolean truth value)
    location = "Aeration Tank North"     # str (string)

    print(f"Location: {location} (ID: {plant_id}, Active: {sensor_active})")
    print(f"Runtime type of o2_reading ({o2_reading}): {type(o2_reading).__name__}")

    # 2. Arithmetic & Special Operators
    duration_minutes = 135
    full_hours = duration_minutes // 60       # Floor division -> 2
    remaining_minutes = duration_minutes % 60 # Modulo         -> 15
    power_test = 2 ** 4                       # Exponentiation -> 16

    print(f"Duration: {full_hours}h {remaining_minutes}min | 2^4 = {power_test} | sqrt(16) = {math.sqrt(power_test)}")

    # 3. Control Structures - Conditional Branching (if / elif / else)
    temperature = 25.0
    if temperature > 30.0:
        climate_status = "Activate cooling"
    elif temperature < 10.0:
        climate_status = "Activate heating"
    else:
        climate_status = "Temperature within normal range"
    print(f"Temperature ({temperature} °C): {climate_status}")

    # 4. Control Structures - Loops (for, while, break, continue)
    raw_readings = [4.2, -0.5, 4.5, 4.1, 999.9, 4.3]
    valid_readings = []

    for value in raw_readings:
        if value < 0.0:
            print(f"  [continue] Skipping negative calibration error: {value}")
            continue
        if value > 500.0:
            print(f"  [break] Critical hardware fault ({value}) -> Aborting loop!")
            break
        valid_readings.append(value)

    # 5. Built-in Data Structures: List (mutable), Tuple (immutable), Dictionary (Key-Value)
    valid_readings.sort()
    threshold_tuple = (0.5, 8.0)  # Immutable tuple (min, max)
    sensor_dict = {
        "id": plant_id,
        "type": "O2 Probe",
        "values": valid_readings,
        "thresholds": threshold_tuple,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    print(f"Sorted reading list (Index 0 = {valid_readings[0]}): {valid_readings}")
    print(f"Dictionary lookup: Type={sensor_dict['type']}, Time={sensor_dict['timestamp']}\n")


if __name__ == "__main__":
    demonstrate_fundamentals()