

class Car:
    'hello, this is a simple car class'  # Class docstring
    def __init__(self, make, model):
        self.make = make      # Attribute 1
        self.model = model    # Attribute 2

    def display_info(self):   # Method 1
        return f"This car is a {self.make} {self.model}."

# Example usage:
my_car = Car("Toyota", "Corolla")
print(my_car.model)  # Accessing attribute directly
print(my_car.make)  # Accessing attribute directly

print(my_car.display_info())

my_second_car = Car("Honda", "Civic")
print(my_second_car.display_info())

print(my_second_car.__doc__)  # Accessing the class docstring

