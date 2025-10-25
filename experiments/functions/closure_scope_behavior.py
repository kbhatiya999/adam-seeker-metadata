"""
Experiment: Closure Scope Behavior and Variable Capture
Objective: Understand how closures capture variables and the implications of late binding
"""

def analyze_closure_behavior():
    print("=== Closure Scope Behavior Analysis ===\n")
    
    # 1. Basic closure behavior
    print("1. Basic Closure Behavior:")
    print("-" * 40)
    
    def outer_function(x):
        def inner_function(y):
            return x + y
        return inner_function
    
    closure1 = outer_function(10)
    closure2 = outer_function(20)
    
    print(f"closure1(5): {closure1(5)}")  # Should be 15
    print(f"closure2(5): {closure2(5)}")  # Should be 25
    print(f"closure1.__closure__: {closure1.__closure__}")
    print(f"closure1.__code__.co_freevars: {closure1.__code__.co_freevars}")
    
    # 2. Late binding problem
    print("\n2. Late Binding Problem:")
    print("-" * 40)
    
    def create_multipliers():
        multipliers = []
        for i in range(3):
            multipliers.append(lambda x: x * i)
        return multipliers
    
    mults = create_multipliers()
    print("Late binding (problematic):")
    for i, mult in enumerate(mults):
        print(f"multiplier[{i}](2): {mult(2)}")  # All will be 4!
    
    # 3. Solution with default parameters
    print("\n3. Solution with Default Parameters:")
    print("-" * 40)
    
    def create_multipliers_fixed():
        multipliers = []
        for i in range(3):
            multipliers.append(lambda x, i=i: x * i)
        return multipliers
    
    mults_fixed = create_multipliers_fixed()
    print("Fixed with default parameters:")
    for i, mult in enumerate(mults_fixed):
        print(f"multiplier[{i}](2): {mult(2)}")  # Now correct!
    
    # 4. Closure with mutable objects
    print("\n4. Closure with Mutable Objects:")
    print("-" * 40)
    
    def create_counter():
        count = [0]  # Using list to make it mutable
        def counter():
            count[0] += 1
            return count[0]
        return counter
    
    counter1 = create_counter()
    counter2 = create_counter()
    
    print(f"counter1(): {counter1()}")
    print(f"counter1(): {counter1()}")
    print(f"counter2(): {counter2()}")
    print(f"counter1(): {counter1()}")
    
    # 5. Nonlocal keyword
    print("\n5. Nonlocal Keyword:")
    print("-" * 40)
    
    def create_counter_nonlocal():
        count = 0
        def counter():
            nonlocal count
            count += 1
            return count
        return counter
    
    counter3 = create_counter_nonlocal()
    print(f"counter3(): {counter3()}")
    print(f"counter3(): {counter3()}")
    print(f"counter3(): {counter3()}")

if __name__ == "__main__":
    analyze_closure_behavior()
    
    print("\n" + "="*50)
    print("ANALYSIS:")
    print("="*50)
    print("""
Key Insights:
1. Closures capture variables by reference, not by value
2. Late binding can cause unexpected behavior in loops
3. Default parameters capture values at function definition time
4. Mutable objects in closures can be modified
5. 'nonlocal' allows modification of enclosing scope variables

Practical Implications:
- Be careful with closures in loops - use default parameters
- Use 'nonlocal' for cleaner mutable state in closures
- Understand that closures capture references, not values
- Closures are powerful for creating function factories
""")