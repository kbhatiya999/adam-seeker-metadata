"""
Experiment: pydantic-settings-export format observation
Objective: Observe what format pydantic-settings-export creates and how it structures the output
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

def observe_export_format():
    print("=== pydantic-settings-export format observation ===\n")
    
    # Create settings with sample data
    settings = TestSettings(
        app_name="MyApplication",
        debug_mode=True,
        port=8080,
        timeout=60.0,
        optional_string="test_value",
        optional_int=42,
        allowed_hosts=["example.com", "api.example.com", "admin.example.com"]
    )
    
    print("1. Sample settings object:")
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
    
    # Export to different formats using generators
    print("\n2. Export to .env format using DotEnvGenerator:")
    print("-" * 40)
    from pydantic_settings_export import PSESettings
    from pydantic_settings_export.models import SettingsInfoModel
    
    pse_settings = PSESettings()
    settings_info = SettingsInfoModel.from_settings_model(settings)
    
    dotenv_gen = DotEnvGenerator(pse_settings)
    env_export = dotenv_gen.generate(settings_info)
    print(env_export)
    
    print("\n3. Export to Markdown format using MarkdownGenerator:")
    print("-" * 40)
    markdown_gen = MarkdownGenerator(pse_settings)
    markdown_export = markdown_gen.generate(settings_info)
    print(markdown_export)
    
    print("\n4. Export to Simple format using SimpleGenerator:")
    print("-" * 40)
    simple_gen = SimpleGenerator(pse_settings)
    simple_export = simple_gen.generate(settings_info)
    print(simple_export)
    
    return {
        'env_export': env_export,
        'markdown_export': markdown_export,
        'simple_export': simple_export
    }

if __name__ == "__main__":
    results = observe_export_format()
    
    print("\n" + "="*60)
    print("OBSERVATION RESULTS:")
    print("="*60)
    print("""
What pydantic-settings-export actually produces:

1. DOTENV FORMAT:
   - Shows all fields as commented out KEY=VALUE pairs
   - Uses proper quoting for string values
   - Groups nested fields with delimiter (__)
   - Shows default values, not current values

2. MARKDOWN FORMAT:
   - Creates comprehensive documentation tables
   - Shows field types, defaults, and examples
   - Groups nested models separately
   - Includes environment variable prefixes

3. SIMPLE FORMAT:
   - Basic text representation
   - Shows field types and default values
   - Simple section headers
   - Good for quick reference

Key Observations:
- All formats show DEFAULT values, not current instance values
- Nested models are handled with delimiter pattern
- String values are properly quoted
- Optional fields show as null when not set
- Arrays are shown in JSON format
""")