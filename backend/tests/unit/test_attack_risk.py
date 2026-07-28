import json

import pytest

from cyrvanta.modules.risk.domain.models import (
    RiskInput,
    assess_risk,
    deterministic_explanation,
)
from cyrvanta.modules.threat_knowledge.application.stix import parse_bundle
from cyrvanta.modules.threat_knowledge.domain.models import map_credential_attack


def test_credential_attack_v2_mapping_is_exact_and_deterministic() -> None:
    mappings = map_credential_attack(
        "credential-attack",
        "2",
        ("resource_access", "privilege_change", "auth_failure", "auth_success"),
    )
    assert [item.technique_external_id for item in mappings] == [
        "T1110",
        "T1078",
        "T1098",
    ]
    assert map_credential_attack("credential-attack", "1", ("auth_failure",)) == ()


def test_risk_v1_uses_exactly_five_factors_and_not_correlation_score() -> None:
    result = assess_risk(
        RiskInput(
            severity="high",
            evidence_count=4,
            source_count=2,
            supported_mapping_count=3,
            normalization_statuses=("VALID", "VALID", "VALID", "VALID"),
        )
    )
    assert result.score == 85
    assert result.band == "critical"
    assert len(result.factors) == 5
    assert [item.contribution for item in result.factors] == [45, 15, 10, 10, 5]
    assert assess_risk(RiskInput("high", 4, 2, 3, ("VALID",) * 4)).fingerprint == result.fingerprint


def test_partial_normalization_removes_quality_points() -> None:
    result = assess_risk(RiskInput("medium", 2, 1, 1, ("VALID", "PARTIAL")))
    assert result.score == 40
    assert result.band == "medium"
    assert result.factors[-1].contribution == 0


def test_explanation_is_bilingual_grounded_in_factors() -> None:
    result = assess_risk(RiskInput("low", 1, 1, 1, ("VALID",)))
    es, en = deterministic_explanation(result, ("T1110",))
    assert "T1110" in es and "T1110" in en
    assert f"{result.score}/100" in es and f"{result.score}/100" in en


def test_offline_stix_parser_allowlists_objects(tmp_path) -> None:
    bundle = tmp_path / "enterprise.json"
    bundle.write_text(
        json.dumps(
            {
                "type": "bundle",
                "objects": [
                    {
                        "type": "attack-pattern",
                        "id": "attack-pattern--11111111-1111-4111-8111-111111111111",
                        "name": "Brute Force",
                        "external_references": [
                            {"source_name": "mitre-attack", "external_id": "T1110"}
                        ],
                        "kill_chain_phases": [
                            {
                                "kill_chain_name": "mitre-attack",
                                "phase_name": "credential-access",
                            }
                        ],
                    },
                    {
                        "type": "malware",
                        "id": "malware--11111111-1111-4111-8111-111111111111",
                        "name": "Excluded",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    parsed = parse_bundle(bundle)
    assert len(parsed.objects) == 1
    assert parsed.objects[0].external_id == "T1110"
    assert parsed.objects[0].tactic_codes == ("credential-access",)


def test_risk_rejects_unknown_severity() -> None:
    with pytest.raises(ValueError, match="unknown"):
        assess_risk(RiskInput("invented", 1, 1, 0, ("VALID",)))
