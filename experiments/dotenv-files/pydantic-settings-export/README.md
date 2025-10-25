# pydantic-settings-export Behavior Testing

This directory contains experiments to understand how `pydantic-settings-export` behaves when exporting Pydantic settings to various formats.

## Experiments

- `export_format.py` - Tests what format pydantic-settings-export creates and how it structures the output
- `enum_handling.py` - Tests how enums are exported and handled in different formats

## Key Questions

1. What format does pydantic-settings-export create by default?
2. How are different data types (strings, numbers, booleans) exported?
3. How are enums handled in the export process?
4. What options are available for customizing the export format?

## Dependencies

- pydantic>=2.0.0
- pydantic-settings>=2.0.0
- pydantic-settings-export>=0.1.0