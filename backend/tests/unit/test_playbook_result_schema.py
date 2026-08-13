from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cyrvanta.modules.playbooks.application.service import (
    PlaybookExecutionService,
    PlaybookSecurityError,
)
from cyrvanta.modules.playbooks.infrastructure.schema_registry import resolve_schema


def _artifact() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "code": "notify-critical-incident",
        "version": "1.0.0",
        "title_i18n": {"es": "Notificar", "en": "Notify"},
        "description_i18n": {"es": "Notificación real", "en": "Real notification"},
        "execution_mode": "LIVE",
        "impact_level": "MEDIUM",
        "input_schema_ref": "security/incident-notification-input-v1",
        "result_schema_ref": "security/incident-notification-result-v1",
        "steps": [
            {
                "id": "step-1",
                "type": "ACTION",
                "action": "notification.send",
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
async def test_live_result_requires_receipts_for_exact_released_steps() -> None:
    tenant_id, version_id = uuid4(), uuid4()
    version = SimpleNamespace(
        id=version_id,
        tenant_id=tenant_id,
        workflow_code="notify-critical-incident",
        result_schema=resolve_schema("security/incident-notification-result-v1"),
        portable_artifact=_artifact(),
    )
    session = SimpleNamespace(scalar=AsyncMock(return_value=version))
    execution = SimpleNamespace(
        tenant_id=tenant_id,
        playbook_version_id=version_id,
        execution_mode="LIVE",
    )
    valid = {
        "effect": "applied",
        "workflow_code": "notify-critical-incident",
        "step_receipts": {"step-1": "receipt-1"},
    }

    await PlaybookExecutionService._validate_success_result(session, execution, valid)

    for receipts in ({}, {"step-1": "receipt-1", "unexpected": "receipt-2"}):
        with pytest.raises(PlaybookSecurityError, match="receipts"):
            await PlaybookExecutionService._validate_success_result(
                session,
                execution,
                {**valid, "step_receipts": receipts},
            )
