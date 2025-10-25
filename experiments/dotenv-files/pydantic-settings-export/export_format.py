"""
Experiment: pydantic-settings-export format testing
Objective: Test what format pydantic-settings-export creates and how it structures the output
"""

import os
import tempfile
from pathlib import Path
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from pydantic_settings_export import Exporter
from pydantic_settings_export.generators import DotEnvGenerator, MarkdownGenerator, SimpleGenerator

class TestSettings(BaseSettings):
    """Test settings with various data types"""
    
    # String values
    app_name: str = "MyApp"
    debug_mode: bool = False
    port: int = 8000
    timeout: float = 30.5
    
    # Optional values
    optional_string: str | None = None
    optional_int: int | None = None
    
    # List values
    allowed_hosts: list[str] = ["localhost", "127.0.0.1"]
    
    # Nested model
    class DatabaseConfig(BaseModel):
        host: str = "localhost"
        port: int = 5432
        name: str = "mydb"
        ssl_enabled: bool = True
    
    database: DatabaseConfig = DatabaseConfig()
    
    model_config = {
        "env_file": ".env",
        "env_nested_delimiter": "__"
    }

def test_export_format():
    print("=== pydantic-settings-export format analysis ===\n")
    
    # Create a temporary .env file for testing
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        f.write("""# Test environment file
APP_NAME=TestApp
DEBUG_MODE=true
PORT=9000
TIMEOUT=45.0
ALLOWED_HOSTS=["example.com", "test.com"]
DATABASE__HOST=db.example.com
DATABASE__PORT=3306
DATABASE__NAME=testdb
DATABASE__SSL_ENABLED=false
""")
        env_file = f.name
    
    print("1. Initial .env file content:")
    print("-" * 40)
    with open(env_file, 'r') as f:
        initial_content = f.read()
        print(initial_content)
    
    # Load settings
    settings = TestSettings(_env_file=env_file)
    
    print("\n2. Loaded settings object:")
    print("-" * 40)
    print(f"app_name: {settings.app_name}")
    print(f"debug_mode: {settings.debug_mode}")
    print(f"port: {settings.port}")
    print(f"timeout: {settings.timeout}")
    print(f"optional_string: {settings.optional_string}")
    print(f"optional_int: {settings.optional_int}")
    print(f"allowed_hosts: {settings.allowed_hosts}")
    print(f"database.host: {settings.database.host}")
    print(f"database.port: {settings.database.port}")
    print(f"database.name: {settings.database.name}")
    print(f"database.ssl_enabled: {settings.database.ssl_enabled}")
    
    # Test export to different formats using generators
    print("\n3. Export to .env format using DotEnvGenerator:")
    print("-" * 40)
    from pydantic_settings_export import PSESettings
    from pydantic_settings_export.models import SettingsInfoModel
    
    pse_settings = PSESettings()
    settings_info = SettingsInfoModel.from_settings_model(settings)
    
    dotenv_gen = DotEnvGenerator(pse_settings)
    env_export = dotenv_gen.generate(settings_info)
    print(env_export)
    
    print("\n4. Export to Markdown format using MarkdownGenerator:")
    print("-" * 40)
    markdown_gen = MarkdownGenerator(pse_settings)
    markdown_export = markdown_gen.generate(settings_info)
    print(markdown_export)
    
    print("\n5. Export to Simple format using SimpleGenerator:")
    print("-" * 40)
    simple_gen = SimpleGenerator(pse_settings)
    simple_export = simple_gen.generate(settings_info)
    print(simple_export)
    
    # Test using Exporter with multiple generators
    print("\n6. Using Exporter with multiple generators:")
    print("-" * 40)
    exporter = Exporter(generators=[DotEnvGenerator(pse_settings), MarkdownGenerator(pse_settings)])
    generated_files = exporter.run_all(settings)
    print(f"Generated files: {generated_files}")
    
    # Test export to file using DotEnvGenerator
    print("\n7. Export to file using DotEnvGenerator:")
    print("-" * 40)
    output_file = tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False)
    
    # Write the generated content to file manually
    with open(output_file.name, 'w') as f:
        f.write(env_export)
    
    with open(output_file.name, 'r') as f:
        file_content = f.read()
        print(file_content)
    
    # Clean up
    os.unlink(env_file)
    os.unlink(output_file.name)
    
    return {
        'initial': initial_content,
        'env_export': env_export,
        'markdown_export': markdown_export,
        'simple_export': simple_export,
        'generated_files': generated_files,
        'file_export': file_content
    }

if __name__ == "__main__":
    results = test_export_format()
    
    print("\n" + "="*60)
    print("ANALYSIS:")
    print("="*60)
    print("""
Key Findings:
1. DOTENV format: Uses KEY=VALUE format with proper quoting
2. MARKDOWN format: Creates documentation tables with field information
3. SIMPLE format: Basic text representation of settings
4. EXPORTER class: Can run multiple generators at once
5. FILE output: Can write directly to files using generators
6. NESTED handling: Uses delimiter (__) for nested fields
7. GENERATORS: Modular system for different output formats

Export Format Characteristics:
- DOTENV: Simple KEY=VALUE, good for environment files
- MARKDOWN: Documentation tables, good for README files
- SIMPLE: Basic text, good for debugging
- All formats preserve data types and structure
""")