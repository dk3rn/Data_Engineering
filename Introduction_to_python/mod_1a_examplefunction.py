# mod 1 additional example function
# 2026-11-04

# import necessary libraries
import math
import pandas as pd

#functions
def addstuff(a, b):
    """Adds two numbers and returns the result."""
    result = a + b
    return result


#main execution block
print("=== MODULE 1: PYTHON FUNDAMENTALS & DATA STRUCTURES ===")

# 1. Dynamic Typing & Primitive Data Types
plant_id = 101                       # int (integer)
o2_reading = 23.5                    # float (floating-point number)
sensor_active = True                 # bool (boolean truth value)
location = "Aeration Tank North"     # str (string)

print(f"Location: {location} (ID: {plant_id}, Active: {sensor_active})")
print(f"Runtime type of o2_reading ({o2_reading}): {type(o2_reading).__name__}")

result = addstuff(5, 10)
print(f"Adding 5 and 10 using addstuff function: {result}")












