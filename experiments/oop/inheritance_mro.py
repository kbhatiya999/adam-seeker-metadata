"""
Experiment: Method Resolution Order (MRO) and Multiple Inheritance
Objective: Understand how Python resolves method calls in complex inheritance hierarchies
"""

class A:
    def method(self):
        return "A.method()"
    
    def common_method(self):
        return "A.common_method()"

class B(A):
    def method(self):
        return "B.method()"
    
    def common_method(self):
        return "B.common_method()"

class C(A):
    def method(self):
        return "C.method()"
    
    def common_method(self):
        return "C.common_method()"

class D(B, C):
    def method(self):
        return "D.method()"

class E(C, B):
    def method(self):
        return "E.method()"

def analyze_mro_behavior():
    print("=== Method Resolution Order Analysis ===\n")
    
    # 1. Basic MRO inspection
    print("1. MRO Inspection:")
    print("-" * 40)
    
    print(f"D.__mro__: {D.__mro__}")
    print(f"E.__mro__: {E.__mro__}")
    
    # 2. Method resolution in different hierarchies
    print("\n2. Method Resolution:")
    print("-" * 40)
    
    d = D()
    e = E()
    
    print(f"d.method(): {d.method()}")
    print(f"e.method(): {e.method()}")
    
    # 3. Common method resolution
    print("\n3. Common Method Resolution:")
    print("-" * 40)
    
    print(f"d.common_method(): {d.common_method()}")
    print(f"e.common_method(): {e.common_method()}")
    
    # 4. Super() behavior
    print("\n4. Super() Behavior:")
    print("-" * 40)
    
    class F(B, C):
        def method(self):
            return f"F.method() -> {super().method()}"
        
        def common_method(self):
            return f"F.common_method() -> {super().common_method()}"
    
    f = F()
    print(f"f.method(): {f.method()}")
    print(f"f.common_method(): {f.common_method()}")
    
    # 5. Diamond problem demonstration
    print("\n5. Diamond Problem Demonstration:")
    print("-" * 40)
    
    class Base:
        def __init__(self):
            print("Base.__init__()")
    
    class Left(Base):
        def __init__(self):
            print("Left.__init__()")
            super().__init__()
    
    class Right(Base):
        def __init__(self):
            print("Right.__init__()")
            super().__init__()
    
    class Bottom(Left, Right):
        def __init__(self):
            print("Bottom.__init__()")
            super().__init__()
    
    print("Creating Bottom instance:")
    bottom = Bottom()
    print(f"Bottom.__mro__: {Bottom.__mro__}")
    
    # 6. Method resolution with super() chain
    print("\n6. Method Resolution with Super() Chain:")
    print("-" * 40)
    
    class GrandParent:
        def method(self):
            return "GrandParent.method()"
    
    class Parent1(GrandParent):
        def method(self):
            return f"Parent1.method() -> {super().method()}"
    
    class Parent2(GrandParent):
        def method(self):
            return f"Parent2.method() -> {super().method()}"
    
    class Child(Parent1, Parent2):
        def method(self):
            return f"Child.method() -> {super().method()}"
    
    child = Child()
    print(f"child.method(): {child.method()}")
    print(f"Child.__mro__: {Child.__mro__}")

if __name__ == "__main__":
    analyze_mro_behavior()
    
    print("\n" + "="*50)
    print("ANALYSIS:")
    print("="*50)
    print("""
Key Insights:
1. MRO follows C3 linearization algorithm (depth-first, left-to-right)
2. Method resolution stops at first matching method in MRO
3. super() follows MRO to find next method in chain
4. Diamond problem is solved by ensuring each class appears only once
5. Order of inheritance matters for method resolution

Practical Implications:
- Use super() for cooperative inheritance
- Be careful with multiple inheritance - keep hierarchies simple
- MRO can be inspected with __mro__ attribute
- Method resolution is predictable but can be complex
- Consider composition over inheritance for complex relationships
""")