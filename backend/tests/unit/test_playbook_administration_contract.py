import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from cyrvanta.modules.playbooks.application.administration_schemas import (
    BindingCreate,
    DefinitionCreate,
)
from cyrvanta.modules.playbooks.application.administration_service import (
    PlaybookAdministrationConflict,
    PlaybookAdministrationService,
)
from cyrvanta.modules.playbooks.application.portable import PortablePlaybookV1
from cyrvanta.modules.playbooks.infrastructure.schema_registry import (
    is_strict_schema,
    resolve_schema,
    validate_strict_object,
)

FIXTURE = (
    Path(__file__).parents[3]
    / "infrastructure"
    / "playbook_engine"
    / "fixtures"
    / "simulated-notification.json"
)


def test_definition_contract_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        DefinitionCreate.model_validate(
            {
                "code": "notify",
                "title_i18n": {"es": "Avisar", "en": "Notify"},
                "description_i18n": {"es": "Prueba", "en": "Test"},
                "tenant_id": "00000000-0000-0000-0000-000000000000",
            }
        )


def test_binding_contract_is_discriminated_and_native_has_no_secret_fields() -> None:
    native = TypeAdapter(BindingCreate).validate_python(
        {
            "playbook_version_id": "00000000-0000-0000-0000-000000000001",
            "engine_type": "NATIVE",
            "instance_code": "cyrvanta-native",
        }
    )
    assert native.engine_type == "NATIVE"

    with pytest.raises(ValidationError):
        TypeAdapter(BindingCreate).validate_python(
            {
                "playbook_version_id": "00000000-0000-0000-0000-000000000001",
                "engine_type": "NATIVE",
                "instance_code": "cyrvanta-native",
                "key_id": "forbidden",
            }
        )


def test_internal_schema_registry_is_typed_strict_and_non_remote() -> None:
    schema = resolve_schema("security/incident-notification-input-v1")
    incident_id = "00000000-0000-0000-0000-000000000001"
    valid = {
        "incident_id": incident_id,
        "incident_version": 7,
        "targets": [incident_id],
        "parameters": {},
        "evidence_refs": [],
    }

    assert validate_strict_object(schema, valid) is True
    invalid = (
        {**valid, "incident_id": "not-a-uuid"},
        {**valid, "incident_version": True},
        {**valid, "targets": []},
        {**valid, "targets": ["not-a-uuid"]},
        {**valid, "targets": [incident_id, incident_id]},
        {**valid, "parameters": {"free_command": "forbidden"}},
        {**valid, "evidence_refs": ["not-a-uuid"]},
        {**valid, "unexpected": "value"},
        {key: value for key, value in valid.items() if key != "incident_id"},
    )
    assert all(not validate_strict_object(schema, item) for item in invalid)
    assert (
        is_strict_schema(
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {"open": {"type": "object"}},
            }
        )
        is False
    )
    with pytest.raises(ValueError, match="PLAYBOOK_INVALID"):
        resolve_schema("https://example.invalid/schema.json")


def test_result_schema_types_and_bounds_dynamic_receipts() -> None:
    schema = resolve_schema("security/incident-notification-result-v1")
    valid = {
        "effect": "applied",
        "workflow_code": "notify-critical-incident",
        "step_receipts": {"step-1": "receipt-1"},
    }

    assert validate_strict_object(schema, valid) is True
    assert validate_strict_object(schema, {**valid, "step_receipts": {"step-1": None}}) is True
    assert validate_strict_object(schema, {**valid, "effect": "simulated"}) is False
    assert (
        validate_strict_object(schema, {**valid, "step_receipts": {"step-1": {"raw": "forbidden"}}})
        is False
    )
    assert validate_strict_object(schema, {**valid, "step_receipts": {"step-1": ""}}) is False


def test_configuration_rejects_secret_like_keys_recursively() -> None:
    with pytest.raises(PlaybookAdministrationConflict, match="PLAYBOOK_ACTION_CONFIG_INVALID"):
        PlaybookAdministrationService._reject_sensitive_configuration(
            {"nested": {"api_key": "must-not-be-accepted"}}
        )


def test_approved_fixture_uses_only_registered_actions() -> None:
    artifact = PortablePlaybookV1.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))

    PlaybookAdministrationService()._validate_registered_actions(artifact)


def test_toggle_binding_payload_and_definition_metadata() -> None:
    from cyrvanta.modules.playbooks.application.administration_schemas import (
        DefinitionResponse,
        ToggleBindingPayload,
    )

    payload = ToggleBindingPayload.model_validate({"active": True, "engine_type": "N8N"})
    assert payload.active is True
    assert payload.engine_type == "N8N"

    definition = DefinitionResponse.model_validate(
        {
            "id": "00000000-0000-0000-0000-000000000001",
            "code": "simulate-user-block",
            "title_i18n": {"es": "Simular bloqueo", "en": "Simulate block"},
            "description_i18n": {"es": "Desc", "en": "Desc"},
            "created_at": "2026-08-01T00:00:00Z",
            "target_incident_types": ["credential-access"],
            "mitre_codes": ["T1110", "T1078"],
            "rollback_supported": True,
            "rollback_target_code": "simulate-user-unblock",
            "rollback_guidance_i18n": {"es": "Desbloquea al usuario.", "en": "Unblocks user."},
            "automation_policy_i18n": {
                "es": "Aprobación obligatoria.",
                "en": "Mandatory approval.",
            },
        }
    )
    assert definition.target_incident_types == ["credential-access"]
    assert definition.mitre_codes == ["T1110", "T1078"]
    assert definition.rollback_supported is True
    assert definition.rollback_target_code == "simulate-user-unblock"
    assert definition.rollback_guidance_i18n.es == "Desbloquea al usuario."
    assert definition.automation_policy_i18n.en == "Mandatory approval."
