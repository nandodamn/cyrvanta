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
    capability) is allowed to be non-empty *only* when sourced from the reviewed,
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
    assert '"rollback_supported": item.code in PLAYBOOK_ROLLBACK_ACTIONS' in projection
    assert '"rollback_action_code": PLAYBOOK_ROLLBACK_ACTIONS.get(item.code)' in projection
    assert 'f"rollback-{item.code}"' not in projection

    # Both lookup tables must be sourced from the reviewed catalog, not
    # fabricated. Asserted over the table's own body with whitespace collapsed,
    # so the guard survives reformatting and type narrowing while still
    # refusing a coverage map built from anything but the catalog entries.
    coverage = source.split("PLAYBOOK_MITRE_COVERAGE: dict[str, list[str]] = {", maxsplit=1)[
        1
    ].split("\n}", maxsplit=1)[0]
    collapsed = " ".join(coverage.split())
    assert 'pb["code"]' in collapsed
    assert 'pb.get("mitre_codes", [])' in collapsed
    assert "for pb in ESSENTIAL_NATIVE_PLAYBOOKS" in collapsed
    # No technique may be conjured out of the playbook code itself.
    assert 'f"' not in collapsed
    rollback_actions = source.split("PLAYBOOK_ROLLBACK_ACTIONS: dict[str, str] = {", maxsplit=1)[
        1
    ].split("}", maxsplit=1)[0]
    # Every rollback target must be a registered reverse ACTION, never another
    # catalog playbook -- reverting is an operation on an execution.
    for code in (
        "compromised-account",
        "compromised-endpoint",
        "lateral-movement",
        "privilege-escalation",
        "ransomware-destructive",
    ):
        assert f'"{code}"' in rollback_actions
        assert f'"{code}-rollback"' not in rollback_actions
    for reverse_action in ("account.enable", "host.restore"):
        assert f'"{reverse_action}"' in rollback_actions


def test_rollback_companions_are_not_catalog_playbooks() -> None:
    """A rollback must never be listable/dispatchable as a standalone procedure."""
    from cyrvanta.modules.playbooks.application.administration_service import (
        ESSENTIAL_NATIVE_ACTIONS,
        ESSENTIAL_NATIVE_PLAYBOOKS,
        IMPLEMENTED_REAL_PLAYBOOKS,
        PLAYBOOK_ROLLBACK_ACTIONS,
        RETIRED_PLAYBOOK_CODES,
    )

    catalog_codes = {str(item["code"]) for item in ESSENTIAL_NATIVE_PLAYBOOKS}
    assert not any(code.endswith("-rollback") for code in catalog_codes)
    assert not any(code.endswith("-rollback") for code in ESSENTIAL_NATIVE_ACTIONS)
    assert not any(code.endswith("-rollback") for code in IMPLEMENTED_REAL_PLAYBOOKS)
    assert RETIRED_PLAYBOOK_CODES.isdisjoint(catalog_codes)
    # Every playbook advertising rollback is itself a real catalog playbook.
    assert set(PLAYBOOK_ROLLBACK_ACTIONS).issubset(catalog_codes)
