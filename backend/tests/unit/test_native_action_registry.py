from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from cyrvanta.modules.playbooks.application.engine_ports import EngineContext
from cyrvanta.modules.playbooks.infrastructure.action_registry import (
    SIMULATED_ACTIONS,
    ActionRegistry,
    ActionUnavailableError,
)


def context() -> EngineContext:
    return EngineContext(
        tenant_id=uuid4(),
        correlation_id=uuid4(),
        causation_id=None,
        deadline=datetime.now(UTC) + timedelta(seconds=30),
    )


def test_registry_exposes_only_approved_simulated_actions() -> None:
    descriptors = ActionRegistry().descriptors()

    assert tuple(item.code for item in descriptors) == tuple(sorted(SIMULATED_ACTIONS))
    assert all(item.modes == ("SIMULATED",) for item in descriptors)
    assert all(item.egress == "NONE" for item in descriptors)


@pytest.mark.asyncio
async def test_simulated_connector_is_deterministic_and_has_no_effect() -> None:
    connector = ActionRegistry().get("notification.send", "1.0.0")

    first = await connector.execute(context(), {"template": "critical"}, "stable", None)
    second = await connector.execute(context(), {"template": "critical"}, "stable", None)

    assert first == second
    assert first.succeeded is True
    assert first.output["effect"] == "none"
    assert first.output["status"] == "DELIVERED"


def test_registry_fails_closed_for_unknown_action_or_version() -> None:
    registry = ActionRegistry()

    with pytest.raises(ActionUnavailableError, match="PLAYBOOK_ACTION_UNAVAILABLE"):
        registry.get("shell.execute", "1.0.0")
    with pytest.raises(ActionUnavailableError, match="PLAYBOOK_ACTION_UNAVAILABLE"):
        registry.get("notification.send", "2.0.0")


def test_simulated_configuration_rejects_unregistered_fields() -> None:
    connector = ActionRegistry().get("ticket.create", "1.0.0")

    result = connector.validate_configuration({"url": "https://example.invalid"})

    assert result.valid is False
    assert result.error_codes == ("PLAYBOOK_ACTION_CONFIG_INVALID",)
