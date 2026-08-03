from __future__ import annotations

from copy import deepcopy

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
            "severity": {"type": "string"},
        },
    },
    "security/incident-notification-result-v1": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "simulated": {"type": "boolean"},
            "effect": {"type": "string", "const": "none"},
        },
        "required": ["simulated", "effect"],
    },
}


class SchemaReferenceUnknown(ValueError):
    pass


def resolve_schema(reference: str) -> dict[str, object]:
    try:
        schema = deepcopy(SCHEMAS[reference])
    except KeyError as exc:
        raise SchemaReferenceUnknown("PLAYBOOK_INVALID") from exc
    if schema.get("type") != "object" or schema.get("additionalProperties") is not False:
        raise SchemaReferenceUnknown("PLAYBOOK_INVALID")
    return schema


def validate_strict_object(schema: dict[str, object], value: dict[str, object]) -> bool:
    properties = schema.get("properties")
    required = schema.get("required", [])
    if not isinstance(properties, dict) or not isinstance(required, list):
        return False
    if any(key not in properties for key in value):
        return False
    if any(not isinstance(key, str) or key not in value for key in required):
        return False
    return True
