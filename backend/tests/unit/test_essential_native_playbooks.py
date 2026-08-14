from cyrvanta.modules.playbooks.application.administration_service import (
    ESSENTIAL_NATIVE_ACTIONS,
    ESSENTIAL_NATIVE_PLAYBOOKS,
    ESSENTIAL_NATIVE_STEP_ACTIONS,
    catalog_step_actions,
)
from cyrvanta.modules.playbooks.infrastructure.action_registry import ActionRegistry


def test_every_essential_playbook_uses_a_registered_real_action() -> None:
    codes = {str(item["code"]) for item in ESSENTIAL_NATIVE_PLAYBOOKS}

    assert set(ESSENTIAL_NATIVE_ACTIONS) == codes
    registry = ActionRegistry()
    for code in codes:
        # Every step, not just the first: an unregistered action buried in the
        # middle of a sequence would only surface when a real incident ran it.
        for action_code in catalog_step_actions(code):
            descriptor = registry.get(action_code, "1.0.0").describe()
            assert descriptor.modes == ("LIVE",)


def test_multi_step_playbooks_lead_with_the_action_readiness_is_anchored_to() -> None:
    """The first step must be the action ESSENTIAL_NATIVE_ACTIONS names.

    Rollback and readiness are keyed off that mapping, so a sequence that leads
    with some other action would revert an effect it never applied.
    """
    for code, actions in ESSENTIAL_NATIVE_STEP_ACTIONS.items():
        assert len(actions) > 1, f"{code} is not multi-step"
        assert actions[0] == ESSENTIAL_NATIVE_ACTIONS[code]
        assert len(set(actions)) == len(actions), f"{code} repeats an action"
