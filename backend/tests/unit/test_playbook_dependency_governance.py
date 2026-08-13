from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cyrvanta.modules.playbooks.application import administration_service as administration_module
from cyrvanta.modules.playbooks.application.administration_service import (
    PlaybookAdministrationService,
)


def _artifact() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "code": "contain-and-document-incident",
        "version": "1.0.0",
        "title_i18n": {"es": "Contener", "en": "Contain"},
        "description_i18n": {"es": "Contención real", "en": "Real containment"},
        "execution_mode": "LIVE",
        "impact_level": "MEDIUM",
        "input_schema_ref": "security/incident-notification-input-v1",
        "result_schema_ref": "security/incident-notification-result-v1",
        "steps": [
            {
                "id": "step-1",
                "type": "ACTION",
                "action": "incident.status.transition",
                "action_version": "1.0.0",
                "parameters": {},
                "credential_aliases": [],
            }
        ],
        "edges": [],
        "timeouts": {"overall_seconds": 60, "action_seconds": 30, "max_attempts": 1},
        "credential_aliases": [],
        "labels": {},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("approval_mode", "requires_approval"),
    (("AUTOMATIC", False), ("SINGLE", True), ("FOUR_EYES", True)),
)
async def test_dependency_projection_uses_definition_governance(
    monkeypatch,
    approval_mode: str,
    requires_approval: bool,
) -> None:
    tenant_id, definition_id, version_id = uuid4(), uuid4(), uuid4()
    version = SimpleNamespace(
        id=version_id,
        tenant_id=tenant_id,
        definition_id=definition_id,
        portable_schema_version="1.0",
        portable_artifact=_artifact(),
    )
    configuration = {"target_status": "contained"}
    service = PlaybookAdministrationService()
    binding = SimpleNamespace(
        configuration=configuration,
        configuration_sha256=service._digest(configuration),
        connector_type="INTERNAL",
        credential_key_id=None,
    )
    session = SimpleNamespace(scalar=AsyncMock(side_effect=[version, approval_mode, binding]))

    @asynccontextmanager
    async def session_scope(scoped_tenant_id):
        assert scoped_tenant_id == tenant_id
        yield session

    monkeypatch.setattr(administration_module, "tenant_session", session_scope)

    dependencies = await service.validate_connection_dependencies(
        tenant_id=tenant_id,
        version_id=version_id,
    )

    assert dependencies[0]["requires_approval"] is requires_approval
    assert dependencies[0]["resolution_status"] == "resolved"
