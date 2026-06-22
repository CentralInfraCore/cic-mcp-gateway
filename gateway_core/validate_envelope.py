"""validate_envelope() — a small, programmatic structural validator for a
GatewayContextEnvelope dict against
output/gateway-context-envelope.schema.yaml.

Job: session-context-pack-v1-001, "Feladat" 3 ("Schema-validáció").
Per input.md: "egyszerű required/properties-bejáró script is elég" — this
is NOT a general-purpose JSON-Schema validator (jsonschema-draft engine);
it walks the schema's own `required`/`properties`/`enum`/`type` structure
for the specific fields this envelope schema defines, recursively, for
top-level fields and the documented nested object/array item shapes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class SchemaValidationError(Exception):
    """Raised by validate_envelope on the FIRST structural violation found.

    (Single-error-at-a-time, not an error-accumulator — sufficient for this
    job's "idézd a validáció kimenetét" requirement; a future job could
    extend this to collect all violations.)
    """


def load_schema(schema_path: Path) -> dict[str, Any]:
    with open(schema_path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _check_type(value: Any, expected_type: str, path: str) -> None:
    type_map = {
        "string": str,
        "array": list,
        "object": dict,
        "boolean": bool,
        "integer": int,
        "number": (int, float),
    }
    py_type = type_map.get(expected_type)
    if py_type is None:
        return
    if not isinstance(value, py_type) or (py_type is int and isinstance(value, bool)):
        raise SchemaValidationError(
            f"{path}: expected type {expected_type!r}, got {type(value).__name__!r} ({value!r})"
        )


def _check_const(value: Any, const: Any, path: str) -> None:
    if value != const:
        raise SchemaValidationError(f"{path}: expected const {const!r}, got {value!r}")


def _check_enum(value: Any, enum: list[Any], path: str) -> None:
    if value not in enum:
        raise SchemaValidationError(f"{path}: value {value!r} not in enum {enum!r}")


def _validate_object(value: Any, schema: dict[str, Any], path: str) -> None:
    _check_type(value, "object", path)
    for required_key in schema.get("required", []):
        if required_key not in value:
            raise SchemaValidationError(f"{path}: missing required key {required_key!r}")
    properties = schema.get("properties", {})
    for key, sub_schema in properties.items():
        if key in value:
            _validate_node(value[key], sub_schema, f"{path}.{key}")


def _validate_array(value: Any, schema: dict[str, Any], path: str) -> None:
    _check_type(value, "array", path)
    min_items = schema.get("minItems")
    if min_items is not None and len(value) < min_items:
        raise SchemaValidationError(
            f"{path}: has {len(value)} items, fewer than minItems={min_items}"
        )
    items_schema = schema.get("items")
    if items_schema:
        for index, item in enumerate(value):
            _validate_node(item, items_schema, f"{path}[{index}]")


def _validate_node(value: Any, schema: dict[str, Any], path: str) -> None:
    if "const" in schema:
        _check_const(value, schema["const"], path)
        return
    schema_type = schema.get("type")
    if schema_type == "object":
        _validate_object(value, schema, path)
    elif schema_type == "array":
        _validate_array(value, schema, path)
    else:
        if schema_type:
            _check_type(value, schema_type, path)
        if "enum" in schema:
            _check_enum(value, schema["enum"], path)
        if schema_type == "string":
            min_length = schema.get("minLength")
            if min_length is not None and len(value) < min_length:
                raise SchemaValidationError(
                    f"{path}: string length {len(value)} below minLength={min_length}"
                )


def validate_envelope(envelope: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    """Validate envelope against schema (top-level required/properties/
    enum/const/type/minItems/minLength walk, recursive into object/array
    sub-schemas).

    Returns a list of human-readable "OK" check descriptions on success.
    Raises SchemaValidationError on the first violation found.
    """
    checks_passed: list[str] = []

    for required_key in schema["required"]:
        if required_key not in envelope:
            raise SchemaValidationError(f"<root>: missing required top-level key {required_key!r}")
        checks_passed.append(f"required key present: {required_key}")

    for key, sub_schema in schema["properties"].items():
        if key in envelope:
            _validate_node(envelope[key], sub_schema, key)
            checks_passed.append(f"type/shape OK: {key}")

    return checks_passed


def validate_envelope_file(envelope: dict[str, Any], schema_path: Path) -> list[str]:
    schema = load_schema(schema_path)
    return validate_envelope(envelope, schema)
