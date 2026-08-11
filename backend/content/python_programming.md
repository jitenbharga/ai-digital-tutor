# Python Programming

## Data Types
Python has several built-in data types:
- int: integers (1, -5, 0)
- float: decimal numbers (3.14, -0.5)
- str: text strings ("hello", 'world')
- bool: True or False
- list: ordered, mutable sequence [1, 2, 3]
- tuple: ordered, immutable sequence (1, 2, 3)
- dict: key-value mapping {"name": "Alice", "age": 30}
- set: unordered collection of unique elements {1, 2, 3}

## Variables and Assignment
Variables are created by assignment: x = 5. Python is dynamically typed — the type is inferred from the value. Variable names must start with a letter or underscore, and are case-sensitive.

## Control Flow
- if/elif/else: conditional execution
- for loop: iterate over a sequence (for x in range(10))
- while loop: repeat while condition is true
- break: exit the loop early
- continue: skip to next iteration

## Functions
Defined with def keyword. Can have default arguments, *args, and **kwargs.
```python
def greet(name, greeting="Hello"):
    return f"{greeting}, {name}!"
```

Functions are first-class objects — they can be passed as arguments and returned from other functions.

## Lists and List Comprehensions
Lists are mutable, ordered sequences. Key operations: append(), extend(), insert(), remove(), pop(), sort(), reverse().

List comprehensions provide concise creation: [x**2 for x in range(10) if x % 2 == 0] produces [0, 4, 16, 36, 64].

## Object-Oriented Programming
Classes define custom types with attributes and methods.
```python
class Dog:
    def __init__(self, name):
        self.name = name
    def bark(self):
        return f"{self.name} says Woof!"
```
Key OOP concepts: inheritance (class Puppy(Dog)), encapsulation, polymorphism.

## Error Handling
Use try/except blocks to handle exceptions gracefully.
```python
try:
    result = 10 / 0
except ZeroDivisionError:
    result = None
```
Common exceptions: ValueError, TypeError, KeyError, IndexError, FileNotFoundError.
