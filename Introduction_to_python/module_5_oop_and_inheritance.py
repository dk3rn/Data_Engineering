"""
TH Köln - Data Engineering (Prof. Dr. Peter Kern)
Module 5: Object-Oriented Programming (OOP), Inheritance, super(), MRO & Duck Typing
"""


# 1. Parent Class (Base Class)
class Sensor:
    """General blueprint for an industrial measurement sensor."""

    def __init__(self, sensor_id, sensor_type, unit):
        self.id = sensor_id
        self.type = sensor_type
        self.unit = unit
        self._current_value = 0.0                  # Convention: protected attribute (_internal)
        self.__serial_number = f"THK-{sensor_id}"  # Name Mangling (_Sensor__serial_number)
        self.history = []

    def update_value(self, raw_input):
        """Validates incoming readings via try/except and appends them to the history."""
        try:
            self._current_value = float(raw_input)
            self.history.append(self._current_value)
        except ValueError:
            print(f"  [Sensor {self.id}] Ignored corrupted raw value: '{raw_input}'")

    def mean_value(self):
        if not self.history:
            return 0.0
        return round(sum(self.history) / len(self.history), 2)

    def report(self):
        return (
            f"Sensor {self.id} ({self.type}): Current = {self._current_value} {self.unit} "
            f"| Mean = {self.mean_value()} {self.unit}"
        )


# 2. Mixin Class for Multiple Inheritance
class CalibrationMixin:
    """Reusable mixin providing offset calibration for sensors."""

    def apply_offset(self, offset):
        self._current_value = round(self._current_value + offset, 2)
        return self._current_value


# 3. Child Class demonstrating Inheritance, super(), Method Overriding & Multiple Inheritance
class O2Sensor(Sensor, CalibrationMixin):
    """Specialized dissolved oxygen sensor with lower-threshold monitoring."""

    def __init__(self, sensor_id, min_threshold=0.5):
        # Delegate base initialization to the parent class via super()
        super().__init__(sensor_id=sensor_id, sensor_type="O2 Probe", unit="mg/L")
        self.min_threshold = min_threshold

    def report(self):
        # Overrides parent method and extends its output
        base_text = super().report()
        status = "ALARM (Low O2!)" if self._current_value < self.min_threshold else "OK"
        return f"{base_text} -> Status: [{status}]"


# 4. Independent Class demonstrating Duck Typing
class PumpController:
    """Does NOT inherit from Sensor, but implements a matching .report() method."""

    def report(self):
        return "PumpController: Blower 1 operating at 75% speed."


def print_plant_status(component_list):
    """Duck Typing: Only requires each object to provide a .report() method."""
    for component in component_list:
        print(" ->", component.report())


if __name__ == "__main__":
    print("=== MODULE 5: OBJECT-ORIENTED PROGRAMMING & INHERITANCE ===")

    o2_tank1 = O2Sensor(sensor_id=101, min_threshold=1.0)
    temp_inlet = Sensor(sensor_id=102, sensor_type="Temperature", unit="°C")
    pump = PumpController()

    for raw in ["2.1", "2.4", "Error", "0.4"]:
        o2_tank1.update_value(raw)

    temp_inlet.update_value("15.4")
    o2_tank1.apply_offset(0.05)  # Method inherited from CalibrationMixin

    # Polymorphism & Duck Typing in action
    print_plant_status([o2_tank1, temp_inlet, pump])

    # Inspect Method Resolution Order (MRO) and Name Mangling
    print("\nMRO of O2Sensor  :", [cls.__name__ for cls in O2Sensor.mro()])
    print("Name Mangling SN :", o2_tank1._Sensor__serial_number, "\n")