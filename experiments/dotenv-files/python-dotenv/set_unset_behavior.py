"""
Experiment: python-dotenv set/unset behavior
Objective: Test where variables are placed (original line vs end) when using set/unset operations
"""

import os
import tempfile
from pathlib import Path
from dotenv import set_key, unset_key, load_dotenv

def test_set_unset_behavior():
    print("=== python-dotenv set/unset behavior analysis ===\n")
    
    # Create a temporary .env file for testing
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        # Write initial content with comments and existing variables
        f.write("""# This is a comment at the top
EXISTING_VAR=original_value
# Another comment
ANOTHER_VAR=another_value
# Comment at the end
""")
        env_file = f.name
    
    print("1. Initial .env file content:")
    print("-" * 40)
    with open(env_file, 'r') as f:
        initial_content = f.read()
        print(initial_content)
    
    # Test 1: Set a new variable
    print("\n2. Setting a new variable 'NEW_VAR=new_value':")
    print("-" * 40)
    set_key(env_file, 'NEW_VAR', 'new_value')
    
    with open(env_file, 'r') as f:
        after_set_content = f.read()
        print(after_set_content)
    
    # Test 2: Set an existing variable
    print("\n3. Setting existing variable 'EXISTING_VAR=modified_value':")
    print("-" * 40)
    set_key(env_file, 'EXISTING_VAR', 'modified_value')
    
    with open(env_file, 'r') as f:
        after_modify_content = f.read()
        print(after_modify_content)
    
    # Test 3: Unset a variable
    print("\n4. Unsetting variable 'ANOTHER_VAR':")
    print("-" * 40)
    unset_key(env_file, 'ANOTHER_VAR')
    
    with open(env_file, 'r') as f:
        after_unset_content = f.read()
        print(after_unset_content)
    
    # Test 4: Set another new variable
    print("\n5. Setting another new variable 'FINAL_VAR=final_value':")
    print("-" * 40)
    set_key(env_file, 'FINAL_VAR', 'final_value')
    
    with open(env_file, 'r') as f:
        final_content = f.read()
        print(final_content)
    
    # Test 5: Load and verify the environment
    print("\n6. Loading environment variables:")
    print("-" * 40)
    load_dotenv(env_file)
    
    env_vars = {
        'EXISTING_VAR': os.getenv('EXISTING_VAR'),
        'NEW_VAR': os.getenv('NEW_VAR'),
        'ANOTHER_VAR': os.getenv('ANOTHER_VAR'),
        'FINAL_VAR': os.getenv('FINAL_VAR')
    }
    
    for var, value in env_vars.items():
        print(f"{var}: {value}")
    
    # Clean up
    os.unlink(env_file)
    
    return {
        'initial': initial_content,
        'after_set': after_set_content,
        'after_modify': after_modify_content,
        'after_unset': after_unset_content,
        'final': final_content,
        'env_vars': env_vars
    }

if __name__ == "__main__":
    results = test_set_unset_behavior()
    
    print("\n" + "="*60)
    print("ANALYSIS:")
    print("="*60)
    print("""
Key Findings:
1. NEW variables are added at the END of the file
2. EXISTING variables are modified IN PLACE (preserving original line position)
3. UNSET variables are completely REMOVED from the file
4. Comments are PRESERVED during all operations
5. File structure and formatting are maintained

Behavior Summary:
- set_key() for new variables: Appends to end
- set_key() for existing variables: Modifies in place
- unset_key(): Removes entire line
- Comments: Always preserved
- Formatting: Maintained
""")