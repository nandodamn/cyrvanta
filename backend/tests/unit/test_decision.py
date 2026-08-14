from uuid import uuid4

from cyrvanta.modules.decision.application.service import DECISION_EVENT_NAMES
from cyrvanta.modules.decision.domain.models import (
    ActionImpact,
    EvaluationOutcome,
    ResponseMode,
    canonical_fingerprint,
    evaluate_policy,
    validate_target_limit,
)
from cyrvanta.shared.domain.events import DomainEvent


def test_policy_requires_dual_control_for_high_impact() -> None:
    result = evaluate_policy(
        impact=ActionImpact.HIGH,
        requested_mode=ResponseMode.HUMAN_APPROVAL,
        global_kill_switch=False,
        tenant_kill_switch=False,
        is_simulated=False,
    )
    assert result.outcome is EvaluationOutcome.DUAL_APPROVAL_REQUIRED
    assert result.required_approvals == 2


def test_policy_denies_critical_automatic_and_kill_switch() -> None:
    critical = evaluate_policy(
        impact=ActionImpact.CRITICAL,
        requested_mode=ResponseMode.DUAL_APPROVAL,
        global_kill_switch=False,
        tenant_kill_switch=False,
        is_simulated=False,
    )
    automatic = evaluate_policy(
        impact=ActionImpact.LOW,
        requested_mode=ResponseMode.AUTOMATIC,
        global_kill_switch=False,
        tenant_kill_switch=False,
        is_simulated=False,
    )
    killed = evaluate_policy(
        impact=ActionImpact.OBSERVATIONAL,
        requested_mode=ResponseMode.HUMAN_APPROVAL,
        global_kill_switch=False,
        tenant_kill_switch=True,
        is_simulated=True,
    )
    assert critical.reason_codes == ("CRITICAL_ACTION_DENIED",)
    assert automatic.reason_codes == ("AUTOMATIC_DISABLED",)
    assert killed.reason_codes == ("KILL_SWITCH_ACTIVE",)


def test_policy_allows_automatic_only_when_explicitly_enabled() -> None:
    still_denied = evaluate_policy(
        impact=ActionImpact.LOW,
        requested_mode=ResponseMode.AUTOMATIC,
        global_kill_switch=False,
        tenant_kill_switch=False,
        is_simulated=False,
        automatic_response_enabled=False,
    )
    enabled = evaluate_policy(
        impact=ActionImpact.LOW,
        requested_mode=ResponseMode.AUTOMATIC,
        global_kill_switch=False,
        tenant_kill_switch=False,
        is_simulated=False,
        automatic_response_enabled=True,
    )
    enabled_but_killed = evaluate_policy(
        impact=ActionImpact.LOW,
        requested_mode=ResponseMode.AUTOMATIC,
        global_kill_switch=True,
        tenant_kill_switch=False,
        is_simulated=False,
        automatic_response_enabled=True,
    )
    enabled_but_critical = evaluate_policy(
        impact=ActionImpact.CRITICAL,
        requested_mode=ResponseMode.AUTOMATIC,
        global_kill_switch=False,
        tenant_kill_switch=False,
        is_simulated=False,
        automatic_response_enabled=True,
    )
    assert still_denied.outcome is EvaluationOutcome.DENIED
    assert still_denied.reason_codes == ("AUTOMATIC_DISABLED",)
    assert enabled.outcome is EvaluationOutcome.ELIGIBLE_FOR_AUTOMATIC
    assert enabled.reason_codes == ("AUTOMATIC_APPROVED",)
    assert enabled_but_killed.reason_codes == ("KILL_SWITCH_ACTIVE",)
    assert enabled_but_critical.reason_codes == ("CRITICAL_ACTION_DENIED",)


def test_fingerprint_is_deterministic_and_sensitive_to_material_change() -> None:
    left = {"targets": ["a"], "parameters": {"b": 2, "a": 1}}
    reordered = {"parameters": {"a": 1, "b": 2}, "targets": ["a"]}
    changed = {"parameters": {"a": 1, "b": 3}, "targets": ["a"]}
    assert canonical_fingerprint(left) == canonical_fingerprint(reordered)
    assert canonical_fingerprint(left) != canonical_fingerprint(changed)


def test_target_limits_fail_closed() -> None:
    validate_target_limit(ActionImpact.MODERATE, 1)
    try:
        validate_target_limit(ActionImpact.MODERATE, 2)
    except ValueError as exc:
        assert "limit" in str(exc).lower()
    else:
        raise AssertionError("moderate action accepted too many targets")


def test_decision_event_catalog_matches_approved_contract() -> None:
    assert DECISION_EVENT_NAMES == {
        "security.action_proposal.created",
        "security.policy_evaluation.completed",
        "security.approval.requested",
        "security.approval.decided",
        "security.authorization.issued",
        "security.authorization.revoked",
        "security.authorization.expired",
    }


def test_decision_event_names_are_valid_event_envelope_codes() -> None:
    for event_name in DECISION_EVENT_NAMES:
        event = DomainEvent.create(
            event_name=event_name,
            tenant_id=uuid4(),
            aggregate_type="response_decision",
            aggregate_id=uuid4(),
            correlation_id=uuid4(),
            producer="decision",
            payload={},
        )
        assert event.event_name == event_name
