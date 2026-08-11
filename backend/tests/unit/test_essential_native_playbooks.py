from cyrvanta.modules.playbooks.application.administration_service import (
    ESSENTIAL_NATIVE_ACTIONS,
    ESSENTIAL_NATIVE_PLAYBOOKS,
)
from cyrvanta.modules.playbooks.infrastructure.action_registry import ActionRegistry


def test_every_essential_playbook_uses_a_registered_simulated_action() -> None:
    codes = {str(item["code"]) for item in ESSENTIAL_NATIVE_PLAYBOOKS}

    assert set(ESSENTIAL_NATIVE_ACTIONS) == codes
    registry = ActionRegistry()
    for action_code in ESSENTIAL_NATIVE_ACTIONS.values():
        descriptor = registry.get(action_code, "1.0.0").describe()
        assert "SIMULATED" in descriptor.modes
