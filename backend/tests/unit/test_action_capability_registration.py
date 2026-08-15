from cyrvanta.modules.integrations.application.connection_service import (
    IntegrationConnectionService,
)
from cyrvanta.modules.integrations.application.resolver import CAPABILITY_POLICIES
from cyrvanta.modules.playbooks.infrastructure.action_registry import (
    _HTTP_ACTIONS,
    _SMTP_ACTIONS,
    _WAZUH_ACTIONS,
    REAL_ACTIONS,
)

# integrations sits below playbooks and cannot import the registry, so the
# capability tables are maintained by hand. This test is what keeps them
# honest: adding an outbound action without registering its capability made
# the resolver answer "capability_not_registered" for a real, configured
# action, and left the connection declaring capabilities it did not cover.


def test_every_outbound_action_has_a_capability_policy() -> None:
    outbound = set(_HTTP_ACTIONS) | set(_SMTP_ACTIONS)
    missing = sorted(action for action in outbound if action not in CAPABILITY_POLICIES)

    assert not missing, f"outbound actions without a capability policy: {missing}"


def test_http_policies_point_at_the_allowlisted_connector() -> None:
    for action in sorted(_HTTP_ACTIONS):
        policy = CAPABILITY_POLICIES[action]
        assert policy["connector_type"] == "HTTP_ALLOWLISTED", action
        # Handing an incident to a third party is never silent.
        assert policy["requires_approval"] is True, action


def test_connection_capabilities_cover_every_action_of_their_connector() -> None:
    """A connection must declare the capabilities its connector can serve.

    The resolver matches on the snapshot stored with the connection, so an
    action missing here cannot resolve even when the connection is active,
    verified and pointing at the right system.
    """
    declared_http = set(IntegrationConnectionService._capabilities("HTTP_ALLOWLISTED"))
    assert set(_HTTP_ACTIONS) <= declared_http
    declared_smtp = set(IntegrationConnectionService._capabilities("SMTP"))
    assert set(_SMTP_ACTIONS) <= declared_smtp

    # Wazuh-backed actions are bound from the Wazuh connection, not through an
    # allowlisted HTTP one, so they must not be advertised as such.
    assert declared_http.isdisjoint(_WAZUH_ACTIONS)


def test_capability_policies_name_only_registered_actions() -> None:
    """A policy for an action the engine cannot run would offer a dead choice."""
    action_policies = {
        capability
        for capability, policy in CAPABILITY_POLICIES.items()
        if policy["connector_type"] in {"HTTP_ALLOWLISTED", "SMTP"}
    }
    unknown = sorted(
        capability
        for capability in action_policies
        # incident.report.deliver is the SMTP delivery capability of
        # incident.report.generate, not an action code of its own.
        if capability not in REAL_ACTIONS and capability != "incident.report.deliver"
    )
    assert not unknown, f"capability policies for unregistered actions: {unknown}"
