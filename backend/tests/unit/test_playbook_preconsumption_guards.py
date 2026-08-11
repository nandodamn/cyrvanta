from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from cyrvanta.modules.playbooks.application.service import (
    PlaybookConflict,
    PlaybookExecutionService,
)

NOW = datetime(2026, 8, 11, 17, 0, tzinfo=UTC)


def _material() -> dict[str, object]:
    return {
        "authorization": SimpleNamespace(
            status="ACTIVE",
            consumed_at=None,
            revoked_at=None,
            expires_at=NOW + timedelta(minutes=5),
            proposal_fingerprint="a" * 64,
        ),
        "proposal": SimpleNamespace(
            status="AUTHORIZED",
            fingerprint="a" * 64,
            impact="MODERATE",
            requested_mode="HUMAN_APPROVAL",
            incident_version=3,
            is_simulated=True,
        ),
        "policy": SimpleNamespace(status="ACTIVE", kill_switch=False),
        "incident": SimpleNamespace(version=3, is_simulated=True),
        "approval_request": SimpleNamespace(
            status="APPROVED",
            expires_at=NOW + timedelta(minutes=10),
            required_approvals=1,
        ),
        "approval_count": 1,
        "global_kill_switch": False,
        "now": NOW,
    }


def test_current_authorized_material_can_pass_preconsumption_validation() -> None:
    PlaybookExecutionService._validate_authorized_state(**_material())  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (lambda values: values.update(global_kill_switch=True), "kill switch"),
        (lambda values: setattr(values["policy"], "kill_switch", True), "kill switch"),
        (lambda values: setattr(values["incident"], "version", 4), "Incident material"),
        (lambda values: setattr(values["approval_request"], "status", "REVOKED"), "Approval"),
        (lambda values: values.update(approval_count=0), "quorum"),
        (lambda values: setattr(values["authorization"], "revoked_at", NOW), "revoked"),
    ),
)
def test_changed_authorized_material_fails_closed(mutation, message: str) -> None:
    values = _material()
    mutation(values)

    with pytest.raises(PlaybookConflict, match=message):
        PlaybookExecutionService._validate_authorized_state(**values)  # type: ignore[arg-type]


def test_consumption_requires_one_unambiguous_enabled_binding_and_both_digests() -> None:
    source = (
        Path(__file__).parents[2]
        / "src"
        / "cyrvanta"
        / "modules"
        / "playbooks"
        / "application"
        / "service.py"
    ).read_text(encoding="utf-8")

    assert "ResponsePolicyVersionModel.tenant_id == tenant_id" in source
    assert "IncidentModel.tenant_id == tenant_id" in source
    assert "ApprovalRequestModel.tenant_id == tenant_id" in source
    assert "ApprovalDecisionModel.tenant_id == tenant_id" in source
    assert "if len(bindings) != 1" in source
    assert "binding.observed_digest != version.artifact_sha256" in source
    assert "binding.desired_digest != version.artifact_sha256" in source
    assert "not settings.playbook_native_engine_enabled" in source
    assert "not settings.n8n_enabled" in source
