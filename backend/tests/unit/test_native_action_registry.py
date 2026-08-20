import pytest

from cyrvanta.modules.playbooks.application.administration_service import (
    ESSENTIAL_NATIVE_ACTIONS,
)
from cyrvanta.modules.playbooks.infrastructure.action_registry import (
    _HTTP_ACTIONS,
    REAL_ACTIONS,
    ActionRegistry,
    ActionUnavailableError,
)

# Internal, idempotent actions: replaying them cannot double-apply their effect.
_RETRY_SAFE_ACTIONS = {
    "incident.status.transition",
    "endpoint.isolate",
    "account.disable",
    "account.enable",
}


def test_registry_exposes_only_real_actions() -> None:
    descriptors = ActionRegistry().descriptors()

    assert tuple(item.code for item in descriptors) == tuple(sorted(REAL_ACTIONS))
    assert all(item.modes == ("LIVE",) for item in descriptors)
    assert all(item.retry_safe == (item.code in _RETRY_SAFE_ACTIONS) for item in descriptors)


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


def test_each_external_system_playbook_has_its_own_action_code() -> None:
    """A shared action code would collapse four destinations into one URL.

    A native action binding is unique per (tenant, action_code), so mail purge,
    perimeter blocking, EDR reactivation and evidence sealing must not share one
    code -- configuring any of them would silently repoint the other three.
    """
    external = {
        "phishing-malicious-email": "mail_security.invoke_allowlisted",
        "malicious-indicator": "firewall.invoke_allowlisted",
        "security-control-disabled": "edr.invoke_allowlisted",
        "evidence-preservation": "evidence_vault.invoke_allowlisted",
    }
    for playbook_code, action_code in external.items():
        assert ESSENTIAL_NATIVE_ACTIONS[playbook_code] == action_code
        assert action_code in _HTTP_ACTIONS
        descriptor = ActionRegistry().get(action_code, "1.0.0").describe()
        # HTTPS egress keeps them credential-gated: no binding, no dispatch.
        assert descriptor.egress == "HTTPS"
        # Handing a snapshot to a third party is not replayable on our side.
        assert descriptor.retry_safe is False
    assert len(set(external.values())) == len(external)


def test_external_system_actions_validate_the_same_bounded_path() -> None:
    """The new codes must inherit the allowlisted-path rules, not bypass them."""
    for action_code in (
        "mail_security.invoke_allowlisted",
        "firewall.invoke_allowlisted",
        "edr.invoke_allowlisted",
        "evidence_vault.invoke_allowlisted",
    ):
        connector = ActionRegistry().get(action_code, "1.0.0")
        assert connector.validate_configuration({"path": "/api/respond"}).valid is True
        rejected = (
            {"path": "https://attacker.invalid/api"},
            {"path": "/../admin"},
            {"path": "/api/respond?tenant=other"},
            {"path": "/api/respond", "method": "DELETE"},
            {},
        )
        assert all(not connector.validate_configuration(item).valid for item in rejected)


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
