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
    assert '"mitre_codes": []' in projection
    assert '"automation_policy_i18n": None' in projection
    assert 'else "PENDING"' in projection
    assert "else False" in projection
    assert '"rollback_supported": False' in projection
    assert '"rollback_target_code": None' in projection
    assert 'f"rollback-{item.code}"' not in projection
