"""A small subset of JSON Schema (type, required, properties, items, enum, minItems), enough to check what a
model returned without adding a dependency."""

from typing import Any, Dict, List

_TYPES = {"object": dict, "array": list, "string": str, "integer": int, "number": (int, float), "boolean": bool}


def validate(value: Any, schema: Dict[str, Any], path: str = "$") -> List[str]:
    """Problems found, as readable strings; an empty list means the value matches."""
    kind = schema.get("type")
    if kind:
        wanted = _TYPES[kind]
        is_bool_as_number = kind in ("integer", "number") and isinstance(value, bool)
        if not isinstance(value, wanted) or is_bool_as_number:
            return [f"{path}: expected {kind}, got {type(value).__name__}"]
    errors: List[str] = []
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} is not one of {schema['enum']}")
    if kind == "object":
        errors += [f"{path}: missing {key!r}" for key in schema.get("required", []) if key not in value]
        for key, sub in schema.get("properties", {}).items():
            if key in value:
                errors += validate(value[key], sub, f"{path}.{key}")
    if kind == "array":
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: needs at least {schema['minItems']} items")
        for i, item in enumerate(value):
            errors += validate(item, schema.get("items", {}), f"{path}[{i}]")
    return errors
