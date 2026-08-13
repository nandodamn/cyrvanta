import pytest

from cyrvanta.modules.playbooks.infrastructure.action_registry import (
    REAL_ACTIONS,
    ActionRegistry,
    ActionUnavailableError,
)


def test_registry_exposes_only_real_actions() -> None:
    descriptors = ActionRegistry().descriptors()

    assert tuple(item.code for item in descriptors) == tuple(sorted(REAL_ACTIONS))
    assert all(item.modes == ("LIVE",) for item in descriptors)
    assert next(item for item in descriptors if item.code == "incident.status.transition").retry_safe
    assert all(
        not item.retry_safe
        for item in descriptors
        if item.code != "incident.status.transition"
    )


def test_registry_fails_closed_for_unknown_action_or_version() -> None:
    registry = ActionRegistry()

    with pytest.raises(ActionUnavailableError, match="PLAYBOOK_ACTION_UNAVAILABLE"):
        registry.get("shell.execute", "1.0.0")
    with pytest.raises(ActionUnavailableError, match="PLAYBOOK_ACTION_UNAVAILABLE"):
        registry.get("notification.send", "2.0.0")


def test_http_configuration_accepts_only_bounded_relative_post_path() -> None:
    connector = ActionRegistry().get("ticket.create", "1.0.0")

    assert connector.validate_configuration({"path": "/api/tickets"}).valid is True
    assert connector.validate_configuration({"path": "https://example.invalid"}).valid is False
    assert connector.validate_configuration({"path": "/../admin"}).valid is False
    assert connector.validate_configuration({"path": "/api/tickets", "method": "DELETE"}).valid is False