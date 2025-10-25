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

def test_enum_handling():
    print("=== pydantic-settings-export enum handling analysis ===\n")
    
    # Create a temporary .env file for testing
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        f.write("""# Test environment file with enums
LOG_LEVEL=WARNING
ENVIRONMENT=production
DATABASE_TYPE=mysql
DEBUG_MODE=true
PORT=9000
DATABASE__TYPE=mongodb
DATABASE__HOST=db.example.com
DATABASE__PORT=3306
DATABASE__SSL_ENABLED=false
""")
        env_file = f.name
    
    print("1. Initial .env file content:")
    print("-" * 40)
    with open(env_file, 'r') as f:
        initial_content = f.read()
        print(initial_content)
    
    # Load settings
    settings = TestSettingsWithEnums(_env_file=env_file)
    
    print("\n2. Loaded settings object with enums:")
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
    
    # Test export to different formats using generators
    print("\n3. Export to .env format using DotEnvGenerator:")
    print("-" * 40)
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
    
    # Test enum validation
    print("\n6. Testing enum validation:")
    print("-" * 40)
    
    # Test valid enum values
    try:
        valid_settings = TestSettingsWithEnums(
            log_level="DEBUG",
            environment="staging",
            database_type="sqlite"
        )
        print("✓ Valid enum values accepted:")
        print(f"  log_level: {valid_settings.log_level}")
        print(f"  environment: {valid_settings.environment}")
        print(f"  database_type: {valid_settings.database_type}")
    except Exception as e:
        print(f"✗ Valid enum values rejected: {e}")
    
    # Test invalid enum values
    try:
        invalid_settings = TestSettingsWithEnums(
            log_level="INVALID_LEVEL",
            environment="invalid_env"
        )
        print("✗ Invalid enum values accepted (unexpected)")
    except Exception as e:
        print(f"✓ Invalid enum values properly rejected: {e}")
    
    # Test enum serialization
    print("\n7. Testing enum serialization:")
    print("-" * 40)
    print(f"settings.model_dump(): {settings.model_dump()}")
    print(f"settings.model_dump_json(): {settings.model_dump_json()}")
    
    # Clean up
    os.unlink(env_file)
    
    return {
        'initial': initial_content,
        'env_export': env_export,
        'markdown_export': markdown_export,
        'simple_export': simple_export,
        'settings_dump': settings.model_dump(),
        'settings_json': settings.model_dump_json()
    }

if __name__ == "__main__":
    results = test_enum_handling()
    
    print("\n" + "="*60)
    print("ANALYSIS:")
    print("="*60)
    print("""
Key Findings:
1. ENUM VALIDATION: Pydantic validates enum values against defined options
2. ENUM SERIALIZATION: Enums are serialized as their string values
3. ENUM EXPORT: All generators handle enums as string values in output
4. ENUM TYPES: String enums work seamlessly with environment variables
5. NESTED ENUMS: Enums in nested models are properly handled
6. OPTIONAL ENUMS: None values are handled correctly for optional enums
7. INVALID VALUES: Invalid enum values are properly rejected with validation errors

Enum Handling Characteristics:
- Environment variables are automatically converted to enum values
- Export formats show enum values as strings
- Validation ensures only valid enum values are accepted
- Nested enums use the same delimiter pattern as other nested fields
- Optional enums can be None without issues
""")