from __future__ import annotations

import math
import re
from copy import deepcopy
from uuid import UUID

STRICT_OBJECT = {
    "type": "object",
    "additionalProperties": False,
    "properties": {},
}

SCHEMAS: dict[str, dict[str, object]] = {
    "security/input-v1": STRICT_OBJECT,
    "security/result-v1": STRICT_OBJECT,
    "security/incident-notification-input-v1": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "incident_id": {"type": "string", "format": "uuid"},
            "incident_version": {"type": "integer", "minimum": 0},
            "targets": {
                "type": "array",
                "items": {
                    "type": "string",
                    "format": "uuid",
                    "minLength": 36,
                    "maxLength": 36,
                },
                "minItems": 1,
                "maxItems": 100,
                "uniqueItems": True,
            },
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {},
            },
            "evidence_refs": {
                "type": "array",
                "items": {"type": "string", "format": "uuid"},
                "maxItems": 32,
                "uniqueItems": True,
            },
        },
        "required": [
            "incident_id",
            "incident_version",
            "targets",
            "parameters",
            "evidence_refs",
        ],
    },
    "security/incident-notification-result-v1": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "effect": {"type": "string", "const": "applied"},
            "workflow_code": {
                "type": "string",
                "minLength": 3,
                "maxLength": 64,
                "pattern": r"^[a-z][a-z0-9-]{2,63}$",
            },
            "step_receipts": {
                "type": "object",
                "additionalProperties": {
                    "type": ["string", "null"],
                    "minLength": 1,
                    "maxLength": 512,
                },
                "properties": {},
                "maxProperties": 64,
            },
        },
        "required": ["effect", "workflow_code", "step_receipts"],
    },
}

_SUPPORTED_TYPES = frozenset({"object", "array", "string", "integer", "number", "boolean", "null"})
_MAX_SCHEMA_DEPTH = 16


class SchemaReferenceUnknown(ValueError):
    pass


def resolve_schema(reference: str) -> dict[str, object]:
    try:
        schema = deepcopy(SCHEMAS[reference])
    except KeyError as exc:
        raise SchemaReferenceUnknown("PLAYBOOK_INVALID") from exc
    if not _is_strict_supported_schema(schema, depth=0):
        raise SchemaReferenceUnknown("PLAYBOOK_INVALID")
    return schema


def is_strict_schema(schema: dict[str, object]) -> bool:
    return _is_strict_supported_schema(schema, depth=0)


def validate_strict_object(schema: dict[str, object], value: dict[str, object]) -> bool:
    return _is_strict_supported_schema(schema, depth=0) and _validate_value(schema, value, depth=0)


def _is_strict_supported_schema(schema: object, *, depth: int) -> bool:
    if not isinstance(schema, dict) or depth > _MAX_SCHEMA_DEPTH:
        return False
    declared = schema.get("type")
    types = [declared] if isinstance(declared, str) else declared
    if (
        not isinstance(types, list)
        or not types
        or any(not isinstance(item, str) or item not in _SUPPORTED_TYPES for item in types)
        or len(set(types)) != len(types)
    ):
        return False
    if "object" in types:
        properties = schema.get("properties")
        additional = schema.get("additionalProperties")
        required = schema.get("required", [])
        if (
            not isinstance(properties, dict)
            or not isinstance(required, list)
            or any(not isinstance(key, str) or key not in properties for key in required)
            or (additional is not False and not isinstance(additional, dict))
        ):
            return False
        if not all(
            isinstance(key, str) and _is_strict_supported_schema(nested, depth=depth + 1)
            for key, nested in properties.items()
        ):
            return False
        if isinstance(additional, dict) and not _is_strict_supported_schema(
            additional, depth=depth + 1
        ):
            return False
    if "array" in types and not _is_strict_supported_schema(schema.get("items"), depth=depth + 1):
        return False
    return True


def _validate_value(schema: dict[str, object], value: object, *, depth: int) -> bool:
    if depth > _MAX_SCHEMA_DEPTH or not _matches_declared_type(schema.get("type"), value):
        return False
    if "const" in schema and value != schema["const"]:
        return False
    enum = schema.get("enum")
    if isinstance(enum, list) and value not in enum:
        return False
    if isinstance(value, dict):
        return _validate_object(schema, value, depth=depth)
    if isinstance(value, list):
        return _validate_array(schema, value, depth=depth)
    if isinstance(value, str):
        return _validate_string(schema, value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _validate_number(schema, value)
    return True


def _validate_object(schema: dict[str, object], value: dict[object, object], *, depth: int) -> bool:
    properties = schema.get("properties")
    required = schema.get("required", [])
    additional = schema.get("additionalProperties")
    if not isinstance(properties, dict) or not isinstance(required, list):
        return False
    if any(not isinstance(key, str) for key in value) or any(key not in value for key in required):
        return False
    if not _within_length(value, schema.get("minProperties"), schema.get("maxProperties")):
        return False
    for key, nested_value in value.items():
        nested_schema = properties.get(key)
        if nested_schema is None:
            if additional is False or not isinstance(additional, dict):
                return False
            nested_schema = additional
        if not isinstance(nested_schema, dict) or not _validate_value(
            nested_schema, nested_value, depth=depth + 1
        ):
            return False
    return True


def _validate_array(schema: dict[str, object], value: list[object], *, depth: int) -> bool:
    items = schema.get("items")
    if not isinstance(items, dict) or not _within_length(
        value, schema.get("minItems"), schema.get("maxItems")
    ):
        return False
    if schema.get("uniqueItems") is True:
        serialized = [repr(item) for item in value]
        if len(set(serialized)) != len(serialized):
            return False
    return all(_validate_value(items, item, depth=depth + 1) for item in value)


def _validate_string(schema: dict[str, object], value: str) -> bool:
    if not _within_length(value, schema.get("minLength"), schema.get("maxLength")):
        return False
    pattern = schema.get("pattern")
    if isinstance(pattern, str) and re.search(pattern, value) is None:
        return False
    if schema.get("format") == "uuid":
        try:
            return str(UUID(value)) == value.casefold()
        except ValueError:
            return False
    return schema.get("format") in {None, "uuid"}


def _validate_number(schema: dict[str, object], value: int | float) -> bool:
    if isinstance(value, float) and not math.isfinite(value):
        return False
    minimum = schema.get("minimum")
    maximum = schema.get("maximum")
    return not (
        isinstance(minimum, (int, float))
        and value < minimum
        or isinstance(maximum, (int, float))
        and value > maximum
    )


def _matches_declared_type(declared: object, value: object) -> bool:
    types = [declared] if isinstance(declared, str) else declared
    if not isinstance(types, list):
        return False
    return any(
        {
            "object": isinstance(value, dict),
            "array": isinstance(value, list),
            "string": isinstance(value, str),
            "integer": isinstance(value, int) and not isinstance(value, bool),
            "number": isinstance(value, (int, float)) and not isinstance(value, bool),
            "boolean": isinstance(value, bool),
            "null": value is None,
        }.get(item, False)
        for item in types
    )


def _within_length(value: object, minimum: object, maximum: object) -> bool:
    size = len(value)  # type: ignore[arg-type]
    return not (
        isinstance(minimum, int) and size < minimum or isinstance(maximum, int) and size > maximum
    )
