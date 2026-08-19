from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cyrvanta.modules.correlation.domain.models import (
    CorrelationCandidate,
    CorrelationLimitExceeded,
    CorrelationRule,
    EntityReference,
    SignalSelector,
    evaluate_rule,
)
from cyrvanta.modules.integrations.infrastructure.wazuh.normalizer import (
    WazuhNormalizer,
)
from cyrvanta.modules.integrations.infrastructure.wazuh.schemas import WazuhHit

BASE_TIME = datetime(2026, 7, 28, 12, 1, tzinfo=UTC)


def rule() -> CorrelationRule:
    return CorrelationRule(
        code="credential-attack",
        version="2",
        definition_sha256="a" * 64,
        selectors=(
            SignalSelector(
                "auth_failure",
                "source-a",
                "rule_reference",
                "failed",
            ),
            SignalSelector(
                "auth_success",
                "source-a",
                "rule_reference",
                "success",
            ),
            SignalSelector(
                "auth_success",
                "source-b",
                "rule_reference",
                "success",
            ),
            SignalSelector(
                "auth_failure",
                "wazuh",
                "rule_reference",
                "60122",
            ),
            SignalSelector(
                "auth_success",
                "wazuh",
                "rule_reference",
                "60106",
            ),
        ),
        partial_issue_allowlist=frozenset({"description_missing"}),
    )


def candidate(
    selector: str,
    *,
    source_system: str = "source-a",
    minute: int = 1,
    namespace: str = "source",
    value: str = "192.0.2.44",
    simulated: bool = False,
    basis: str = "SOURCE",
    status: str = "VALID",
    issues: tuple[str, ...] = (),
    severity: int = 70,
) -> CorrelationCandidate:
    return CorrelationCandidate(
        finding_id=uuid4(),
        revision_id=uuid4(),
        integration_id=uuid4(),
        source_system=source_system,
        effective_at=BASE_TIME.replace(minute=minute),
        effective_time_basis=basis,
        severity_score=severity,
        category="credential-access",
        rule_reference=selector,
        normalization_status=status,
        issue_codes=issues,
        entities=(EntityReference("IP_ADDRESS", value, namespace),),
        is_simulated=simulated,
    )


def test_same_inputs_are_order_independent_and_score_is_not_probability() -> None:
    trigger = candidate("success", minute=4)
    failed = candidate("failed", minute=2)
    first = evaluate_rule(rule(), trigger, (trigger, failed))
    second = evaluate_rule(rule(), trigger, (failed, trigger))
    assert first is not None and second is not None
    assert first.input_fingerprint == second.input_fingerprint
    assert first.grouping_key_hash == second.grouping_key_hash
    assert [item.revision_id for item in first.members] == [
        item.revision_id for item in second.members
    ]
    assert first.score == 85
    assert first.threshold == 85


def test_source_diversity_is_optional_and_explainable() -> None:
    trigger = candidate("success", source_system="source-b", minute=4)
    failed = candidate("failed", minute=2)
    match = evaluate_rule(rule(), trigger, (failed, trigger))
    assert match is not None
    assert match.score == 100
    diversity = next(factor for factor in match.factors if factor.code == "source_diversity")
    assert diversity.matched is True
    assert diversity.contribution == 15


def test_exact_ip_role_and_simulation_boundary_fail_closed() -> None:
    trigger = candidate("success", minute=4, simulated=True)
    wrong_role = candidate("failed", minute=2, namespace="destination", simulated=True)
    real = candidate("failed", minute=2, simulated=False)
    assert evaluate_rule(rule(), trigger, (wrong_role, real, trigger)) is None


def test_partial_allowlist_and_ingested_time_are_explicit() -> None:
    trigger = candidate(
        "success",
        minute=4,
        status="PARTIAL",
        issues=("description_missing",),
    )
    allowed = candidate("failed", minute=2)
    assert evaluate_rule(rule(), trigger, (allowed, trigger)) is not None
    rejected = candidate(
        "success",
        minute=4,
        status="PARTIAL",
        issues=("source_timestamp_missing_or_invalid",),
    )
    assert evaluate_rule(rule(), rejected, (allowed, rejected)) is None
    ingested = candidate("success", minute=4, basis="INGESTED")
    assert evaluate_rule(rule(), ingested, (allowed, ingested)) is None


def test_bucket_boundary_is_fixed_utc_and_non_overlapping() -> None:
    trigger = candidate("success", minute=10)
    previous = candidate("failed", minute=9)
    same_bucket = candidate("failed", minute=11)
    assert evaluate_rule(rule(), trigger, (previous, trigger)) is None
    match = evaluate_rule(rule(), trigger, (trigger, same_bucket))
    assert match is not None
    assert match.window_start == datetime(2026, 7, 28, 12, 10, tzinfo=UTC)
    assert match.window_end == datetime(2026, 7, 28, 12, 20, tzinfo=UTC)


def test_candidate_and_member_limits_never_correlate_partial_sets() -> None:
    constrained = replace(rule(), max_candidates=1)
    trigger = candidate("success", minute=4)
    failed = candidate("failed", minute=2)
    with pytest.raises(CorrelationLimitExceeded, match="candidate"):
        evaluate_rule(constrained, trigger, (trigger, failed))


def asset_candidate(
    selector: str,
    *,
    asset: str = "lab-server-01",
    minute: int = 1,
    source_system: str = "source-a",
    simulated: bool = False,
) -> CorrelationCandidate:
    return CorrelationCandidate(
        finding_id=uuid4(),
        revision_id=uuid4(),
        integration_id=uuid4(),
        source_system=source_system,
        effective_at=BASE_TIME.replace(minute=minute),
        effective_time_basis="SOURCE",
        severity_score=70,
        category="host-integrity",
        rule_reference=selector,
        normalization_status="VALID",
        issue_codes=(),
        entities=(EntityReference("ASSET", asset, "wazuh-agent"),),
        is_simulated=simulated,
    )


def test_grouping_defaults_to_source_ip_for_rules_seeded_before_it_existed() -> None:
    """Regression anchor: a rule that never declares `grouping` in its stored
    definition must keep grouping by IP, with the same factor name and the
    same score it produced before this field existed.
    """
    assert rule().grouping == "source_ip"
    trigger = candidate("success", minute=4)
    failed = candidate("failed", minute=2)
    match = evaluate_rule(rule(), trigger, (trigger, failed))
    assert match is not None
    assert match.score == 85
    exact = next(factor for factor in match.factors if factor.code == "exact_source_ip")
    assert exact.matched is True


def test_asset_grouping_correlates_findings_with_no_source_ip() -> None:
    """File integrity and rootcheck findings carry no source IP: grouping by
    asset is the only way they can ever correlate at all.
    """
    asset_grouped = replace(rule(), grouping="asset")
    trigger = asset_candidate("success", minute=4)
    failed = asset_candidate("failed", minute=2)
    match = evaluate_rule(asset_grouped, trigger, (failed, trigger))
    assert match is not None
    assert match.score == 85
    exact = next(factor for factor in match.factors if factor.code == "exact_asset")
    assert exact.matched is True
    assert exact.explanation_code == "correlation.factor.exact_asset"


def test_asset_grouping_does_not_cross_different_hosts() -> None:
    asset_grouped = replace(rule(), grouping="asset")
    trigger = asset_candidate("success", minute=4, asset="lab-server-01")
    other_host = asset_candidate("failed", minute=2, asset="lab-workstation-01")
    assert evaluate_rule(asset_grouped, trigger, (other_host, trigger)) is None


def test_unknown_grouping_is_rejected() -> None:
    with pytest.raises(ValueError, match="grouping"):
        replace(rule(), grouping="asset_owner")


def test_single_signal_rule_opens_on_one_finding_grave_enough() -> None:
    """Wazuh level 12 normalises to severity 84 (level * 7). One ransomware
    or malware hit of that weight is an incident on its own -- no second
    signal exists to pair it with, and waiting for one loses the case.
    """
    single = replace(rule(), min_severity=80)
    trigger = candidate("success", minute=4, severity=84)
    match = evaluate_rule(single, trigger, (trigger,))
    assert match is not None
    assert match.score == 85
    assert len(match.members) == 1
    severity_factor = next(f for f in match.factors if f.code == "critical_severity")
    assert severity_factor.matched is True
    assert severity_factor.contribution == 45


def test_single_signal_rule_stays_shut_below_its_minimum() -> None:
    single = replace(rule(), min_severity=80)
    trigger = candidate("success", minute=4, severity=79)
    assert evaluate_rule(single, trigger, (trigger,)) is None


def test_single_signal_mode_does_not_emit_the_factors_it_waives() -> None:
    """The pattern factors are not scored as zero in this mode, they are not
    evaluated at all: reporting a failed `distinct_signal_pattern` on a rule
    that never asked for one would misexplain the decision to the analyst.
    """
    single = replace(rule(), min_severity=80)
    trigger = candidate("success", minute=4, severity=84)
    match = evaluate_rule(single, trigger, (trigger,))
    assert match is not None
    codes = {factor.code for factor in match.factors}
    assert codes == {"exact_source_ip", "critical_severity", "source_diversity"}


def test_multi_signal_rule_still_refuses_a_lone_severe_finding() -> None:
    """Regression: `credential-attack` declares no min_severity, so a single
    failed login must not open an incident no matter how severe it is.
    """
    assert rule().min_severity is None
    lone = candidate("failed", minute=4, severity=100)
    assert evaluate_rule(rule(), lone, (lone,)) is None


def test_min_severity_outside_the_severity_range_is_rejected() -> None:
    with pytest.raises(ValueError, match="min_severity"):
        replace(rule(), min_severity=101)


def test_correlation_domain_does_not_import_wazuh() -> None:
    module_names = (
        CorrelationCandidate.__module__,
        CorrelationRule.__module__,
        SignalSelector.__module__,
    )
    assert all("wazuh" not in name for name in module_names)


def test_wazuh_and_synthetic_inputs_use_the_same_rule_engine_contract() -> None:
    tenant_id = uuid4()
    integration_id = uuid4()
    normalizer = WazuhNormalizer(clock=lambda: BASE_TIME)

    def normalized(rule_id: str, minute: int) -> CorrelationCandidate:
        finding = normalizer.normalize(
            WazuhHit.model_validate(
                {
                    "_index": "wazuh-alerts-test",
                    "_id": f"{rule_id}-{minute}",
                    "_source": {
                        "timestamp": BASE_TIME.replace(minute=minute).isoformat(),
                        "rule": {
                            "id": rule_id,
                            "level": 9,
                            "description": "Synthetic Wazuh fixture",
                            "groups": ["authentication"],
                        },
                        "data": {"srcip": "192.0.2.44"},
                    },
                }
            ),
            tenant_id,
            integration_id,
        )
        assert finding.source_ip is not None
        return CorrelationCandidate(
            finding_id=finding.finding_id,
            revision_id=uuid4(),
            integration_id=integration_id,
            source_system=finding.source_system,
            effective_at=finding.effective_at,
            effective_time_basis=finding.effective_time_basis.value,
            severity_score=finding.severity_score,
            category=finding.category,
            rule_reference=finding.rule_reference,
            normalization_status=finding.normalization.status.value,
            issue_codes=finding.normalization.issue_codes,
            entities=(EntityReference("IP_ADDRESS", str(finding.source_ip), "source"),),
            is_simulated=False,
        )

    failed = normalized("60122", 2)
    success = normalized("60106", 4)
    match = evaluate_rule(rule(), success, (success, failed))
    assert match is not None
    assert match.score == 85
    assert {match.selector_codes[item.revision_id] for item in match.members} == {
        "auth_failure",
        "auth_success",
    }
