# python-dotenv Behavior Testing

This directory contains experiments to understand how `python-dotenv` behaves when setting and unsetting environment variables in `.env` files.

## Experiments

- `set_unset_behavior.py` - Tests where variables are placed (original line vs end) when using set/unset operations
- `comment_preservation.py` - Tests what happens to comments during unset/set operations

## Key Questions

1. When using `dotenv.set_key()`, where does the library place new variables?
2. When unsetting variables, are comments preserved?
3. How does the library handle existing comments and formatting?
4. What happens to the file structure when variables are modified?

## Dependencies

- python-dotenv>=1.0.0