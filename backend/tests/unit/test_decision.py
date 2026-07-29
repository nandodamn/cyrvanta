from cyrvanta.modules.decision.domain.models import (
    ActionImpact,
    EvaluationOutcome,
    ResponseMode,
    canonical_fingerprint,
    evaluate_policy,
    validate_target_limit,
)


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
