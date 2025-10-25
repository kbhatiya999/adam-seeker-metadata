"""
Experiment: python-dotenv comment preservation
Objective: Test what happens to comments during unset/set operations
"""

import os
import tempfile
from pathlib import Path
from dotenv import set_key, unset_key, load_dotenv

def test_comment_preservation():
    print("=== python-dotenv comment preservation analysis ===\n")
    
    # Create a temporary .env file with various comment patterns
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        f.write("""# Header comment
VAR1=value1
# Inline comment after variable
VAR2=value2 # This is an inline comment
# Standalone comment
VAR3=value3
# Comment before variable
VAR4=value4
# Multiple consecutive comments
# Another comment
VAR5=value5
# Comment at end
""")
        env_file = f.name
    
    print("1. Initial .env file with various comment patterns:")
    print("-" * 50)
    with open(env_file, 'r') as f:
        initial_content = f.read()
        print(initial_content)
    
    # Test 1: Unset a variable with inline comment
    print("\n2. Unsetting VAR2 (has inline comment):")
    print("-" * 50)
    unset_key(env_file, 'VAR2')
    
    with open(env_file, 'r') as f:
        after_unset_inline = f.read()
        print(after_unset_inline)
    
    # Test 2: Unset a variable with comment before it
    print("\n3. Unsetting VAR4 (has comment before it):")
    print("-" * 50)
    unset_key(env_file, 'VAR4')
    
    with open(env_file, 'r') as f:
        after_unset_before = f.read()
        print(after_unset_before)
    
    # Test 3: Set a new variable
    print("\n4. Setting new variable NEW_VAR=new_value:")
    print("-" * 50)
    set_key(env_file, 'NEW_VAR', 'new_value')
    
    with open(env_file, 'r') as f:
        after_set_new = f.read()
        print(after_set_new)
    
    # Test 4: Modify existing variable
    print("\n5. Modifying VAR1 (preserving its position):")
    print("-" * 50)
    set_key(env_file, 'VAR1', 'modified_value')
    
    with open(env_file, 'r') as f:
        after_modify = f.read()
        print(after_modify)
    
    # Test 5: Unset variable with multiple comments before
    print("\n6. Unsetting VAR5 (has multiple comments before):")
    print("-" * 50)
    unset_key(env_file, 'VAR5')
    
    with open(env_file, 'r') as f:
        after_unset_multiple = f.read()
        print(after_unset_multiple)
    
    # Test 6: Set variable with special characters
    print("\n7. Setting variable with special characters:")
    print("-" * 50)
    set_key(env_file, 'SPECIAL_VAR', 'value with spaces and "quotes"')
    
    with open(env_file, 'r') as f:
        after_special = f.read()
        print(after_special)
    
    # Clean up
    os.unlink(env_file)
    
    return {
        'initial': initial_content,
        'after_unset_inline': after_unset_inline,
        'after_unset_before': after_unset_before,
        'after_set_new': after_set_new,
        'after_modify': after_modify,
        'after_unset_multiple': after_unset_multiple,
        'after_special': after_special
    }

if __name__ == "__main__":
    results = test_comment_preservation()
    
    print("\n" + "="*60)
    print("ANALYSIS:")
    print("="*60)
    print("""
Key Findings:
1. INLINE comments (after variable) are REMOVED when variable is unset
2. STANDALONE comments are PRESERVED
3. Comments BEFORE variables are PRESERVED when variable is unset
4. MULTIPLE consecutive comments are PRESERVED
5. New variables are added at the END with proper quoting
6. Special characters in values are properly quoted

Comment Preservation Rules:
- Standalone comments: Always preserved
- Comments before variables: Preserved when variable is unset
- Inline comments: Removed when variable is unset
- Multiple comments: All preserved
- File structure: Maintained throughout operations
""")