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
    assert next(
        item for item in descriptors if item.code == "incident.status.transition"
    ).retry_safe
    assert all(
        not item.retry_safe for item in descriptors if item.code != "incident.status.transition"
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
    invalid = (
        {"path": "https://example.invalid"},
        {"path": "/../admin"},
        {"path": "/api/%252e%252e/admin"},
        {"path": "/api/%25252e%25252e/admin"},
        {"path": "/api/tickets%0d%0aheader"},
        {"path": "/api/tickets?tenant=other"},
        {"path": "/api/tickets#fragment"},
        {"path": "/api/tickets", "method": "DELETE"},
        {"path": 42},
    )
    assert all(not connector.validate_configuration(item).valid for item in invalid)


def test_smtp_configuration_requires_one_safe_mailbox_and_typed_prefix() -> None:
    connector = ActionRegistry().get("notification.send", "1.0.0")

    assert connector.validate_configuration({"to": "soc@example.test"}).valid is True
    invalid = (
        {"to": "soc@example.test,other@example.test"},
        {"to": "soc@example.test\r\nBcc: other@example.test"},
        {"to": "not-a-mailbox"},
        {"to": "soc@example.test", "subject_prefix": "safe\r\nBcc: other"},
        {"to": "soc@example.test", "subject_prefix": 42},
    )
    assert all(not connector.validate_configuration(item).valid for item in invalid)
