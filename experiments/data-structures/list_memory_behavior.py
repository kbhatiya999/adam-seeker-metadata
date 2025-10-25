"""
Experiment: List Memory Behavior and Reference Sharing
Objective: Understand how Python handles list memory allocation and reference sharing
"""

import sys
from copy import deepcopy

def analyze_list_behavior():
    print("=== List Memory Behavior Analysis ===\n")
    
    # 1. List creation and memory allocation
    print("1. List Creation and Memory Allocation:")
    print("-" * 40)
    
    # Empty list
    empty_list = []
    print(f"Empty list size: {sys.getsizeof(empty_list)} bytes")
    
    # Small list
    small_list = [1, 2, 3]
    print(f"Small list [1,2,3] size: {sys.getsizeof(small_list)} bytes")
    
    # Larger list
    large_list = list(range(100))
    print(f"List with 100 elements size: {sys.getsizeof(large_list)} bytes")
    
    # 2. Reference sharing behavior
    print("\n2. Reference Sharing Behavior:")
    print("-" * 40)
    
    original = [1, 2, 3, [4, 5]]
    print(f"Original list: {original}")
    print(f"Original list id: {id(original)}")
    
    # Shallow copy
    shallow_copy = original.copy()
    print(f"Shallow copy: {shallow_copy}")
    print(f"Shallow copy id: {id(shallow_copy)}")
    print(f"Same object? {original is shallow_copy}")
    print(f"Same nested list? {original[3] is shallow_copy[3]}")
    
    # Deep copy
    deep_copy = deepcopy(original)
    print(f"Deep copy: {deep_copy}")
    print(f"Deep copy id: {id(deep_copy)}")
    print(f"Same object? {original is deep_copy}")
    print(f"Same nested list? {original[3] is deep_copy[3]}")
    
    # 3. List modification and memory growth
    print("\n3. List Modification and Memory Growth:")
    print("-" * 40)
    
    test_list = []
    print(f"Initial size: {sys.getsizeof(test_list)} bytes")
    
    for i in range(10):
        test_list.append(i)
        print(f"After adding {i+1} elements: {sys.getsizeof(test_list)} bytes")
    
    # 4. List slicing behavior
    print("\n4. List Slicing Behavior:")
    print("-" * 40)
    
    original_list = [1, 2, 3, 4, 5]
    slice_result = original_list[1:4]
    print(f"Original: {original_list}")
    print(f"Slice [1:4]: {slice_result}")
    print(f"Slice is new object: {original_list is not slice_result}")
    
    # Modifying slice doesn't affect original
    slice_result[0] = 99
    print(f"After modifying slice: {slice_result}")
    print(f"Original unchanged: {original_list}")

if __name__ == "__main__":
    analyze_list_behavior()
    
    print("\n" + "="*50)
    print("ANALYSIS:")
    print("="*50)
    print("""
Key Insights:
1. Lists have overhead beyond just their elements (empty list ~56 bytes)
2. Memory grows dynamically but not linearly with each addition
3. Shallow copy shares references to nested objects
4. Deep copy creates completely independent objects
5. Slicing creates new list objects (defensive copying)

Practical Implications:
- Use shallow copy when you want to share nested data
- Use deep copy when you need complete independence
- Be aware of memory overhead for small lists
- Slicing is safe but creates new objects
""")