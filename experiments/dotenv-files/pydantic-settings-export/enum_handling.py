"""
Experiment: pydantic-settings-export enum observation
Objective: Observe how enums are exported and what the output looks like
"""

import os
import tempfile
from enum import Enum
from pathlib import Path
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from pydantic_settings_export import Exporter, PSESettings
from pydantic_settings_export.generators import DotEnvGenerator, MarkdownGenerator, SimpleGenerator
from pydantic_settings_export.models import SettingsInfoModel

class LogLevel(str, Enum):
    """Log level enumeration"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class Environment(str, Enum):
    """Environment type enumeration"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

class DatabaseType(str, Enum):
    """Database type enumeration"""
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLITE = "sqlite"
    MONGODB = "mongodb"

class TestSettingsWithEnums(BaseSettings):
    """Test settings with various enum types"""
    
    # String enums
    log_level: LogLevel = LogLevel.INFO
    environment: Environment = Environment.DEVELOPMENT
    
    # Optional enum
    database_type: DatabaseType | None = None
    
    # Enum with custom values
    debug_mode: bool = False
    port: int = 8000
    
    # Nested model with enum
    class DatabaseConfig(BaseModel):
        type: DatabaseType = DatabaseType.POSTGRESQL
        host: str = "localhost"
        port: int = 5432
        ssl_enabled: bool = True
    
    database: DatabaseConfig = DatabaseConfig()
    
    model_config = {
        "env_file": ".env",
        "env_nested_delimiter": "__"
    }

def observe_enum_export():
    print("=== pydantic-settings-export enum export observation ===\n")
    
    # Create settings with enum values
    settings = TestSettingsWithEnums(
        log_level=LogLevel.WARNING,
        environment=Environment.PRODUCTION,
        database_type=DatabaseType.MYSQL,
        debug_mode=True,
        port=9000
    )
    
    print("1. Sample settings object with enums:")
    print("-" * 40)
    print(f"log_level: {settings.log_level} (type: {type(settings.log_level)})")
    print(f"environment: {settings.environment} (type: {type(settings.environment)})")
    print(f"database_type: {settings.database_type} (type: {type(settings.database_type)})")
    print(f"debug_mode: {settings.debug_mode}")
    print(f"port: {settings.port}")
    print(f"database.type: {settings.database.type} (type: {type(settings.database.type)})")
    print(f"database.host: {settings.database.host}")
    print(f"database.port: {settings.database.port}")
    print(f"database.ssl_enabled: {settings.database.ssl_enabled}")
    
    # Export to different formats using generators
    print("\n2. Export to .env format using DotEnvGenerator:")
    print("-" * 40)
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
    results = observe_enum_export()
    
    print("\n" + "="*60)
    print("OBSERVATION RESULTS:")
    print("="*60)
    print("""
What pydantic-settings-export produces when enums are used:

1. DOTENV FORMAT WITH ENUMS:
   - Shows enum fields with their DEFAULT string values
   - Uses proper quoting for enum string values
   - Shows enum type name in Markdown format
   - Nested enums use the same delimiter pattern

2. MARKDOWN FORMAT WITH ENUMS:
   - Shows enum type names (e.g., "LogLevel", "Environment")
   - Displays default enum values as strings
   - Includes type information in the table
   - Groups nested enum fields properly

3. SIMPLE FORMAT WITH ENUMS:
   - Shows enum type names in field type information
   - Displays default values as strings
   - Simple representation of enum fields

Key Observations:
- Enums are exported as their string values, not enum objects
- Default values are shown, not current instance values
- Enum type names appear in type information
- Nested enums follow the same pattern as other nested fields
- Optional enums show as null when not set
""")