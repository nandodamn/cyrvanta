from pathlib import Path

import pytest

from cyrvanta.modules.playbooks.application.administration_service import (
    PlaybookAdministrationService,
)


@pytest.mark.parametrize(
    ("requested", "minimum", "allowed"),
    [
        ("AUTOMATIC", "AUTOMATIC", True),
        ("SINGLE", "AUTOMATIC", True),
        ("FOUR_EYES", "AUTOMATIC", True),
        ("SINGLE", "SINGLE", True),
        ("FOUR_EYES", "SINGLE", True),
        ("AUTOMATIC", "SINGLE", False),
        ("FOUR_EYES", "FOUR_EYES", True),
        ("SINGLE", "FOUR_EYES", False),
        ("AUTOMATIC", "FOUR_EYES", False),
        ("UNKNOWN", "AUTOMATIC", False),
    ],
)
def test_approval_governance_can_only_stay_equal_or_become_stricter(
    requested: str,
    minimum: str,
    allowed: bool,
) -> None:
    assert PlaybookAdministrationService._approval_satisfies_minimum(requested, minimum) is allowed


def test_definition_projection_has_no_fabricated_readiness_defaults() -> None:
    """
    Live/derived readiness signals (binding + credential health, execution history)
    must never be fabricated. Static catalog metadata (MITRE coverage, rollback
    companions) is allowed to be non-empty *only* when sourced from the reviewed,
    tested ESSENTIAL_NATIVE_PLAYBOOKS catalog via a named lookup table -- never
    invented ad hoc in the projection itself (e.g. via string formatting a code).
    """
    source = (
        Path(__file__).parents[2]
        / "src"
        / "cyrvanta"
        / "modules"
        / "playbooks"
        / "application"
        / "administration_service.py"
    ).read_text(encoding="utf-8")

    projection = source.split("async def _enriched_definition_response", maxsplit=1)[1].split(
        "async def update_approval_governance", maxsplit=1
    )[0]

    assert "PLAYBOOK_MITRE_CODES" not in projection
    assert '"target_incident_types": []' in projection
    assert '"mitre_codes": PLAYBOOK_MITRE_COVERAGE.get(item.code, [])' in projection
    assert '"automation_policy_i18n": None' in projection
    assert 'else "PENDING"' in projection
    assert "else False" in projection
    assert '"rollback_supported": item.code in PLAYBOOK_ROLLBACK_TARGETS' in projection
    assert '"rollback_target_code": PLAYBOOK_ROLLBACK_TARGETS.get(item.code)' in projection
    assert 'f"rollback-{item.code}"' not in projection

    # Both lookup tables must be sourced from the reviewed catalog, not fabricated.
    assert (
        'PLAYBOOK_MITRE_COVERAGE: dict[str, list[str]] = {\n'
        '    pb["code"]: list(pb.get("mitre_codes", []))'
    ) in source
    assert "for pb in ESSENTIAL_NATIVE_PLAYBOOKS" in source
    rollback_targets = source.split("PLAYBOOK_ROLLBACK_TARGETS: dict[str, str] = {", maxsplit=1)[
        1
    ].split("}", maxsplit=1)[0]
    for code in ("compromised-account", "compromised-endpoint", "lateral-movement",
                 "privilege-escalation", "ransomware-destructive"):
        assert f'"{code}"' in rollback_targets
        assert f'"{code}-rollback"' in rollback_targets
