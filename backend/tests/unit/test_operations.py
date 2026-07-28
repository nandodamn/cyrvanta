import pytest
from pytest import MonkeyPatch

from cyrvanta.modules.operations.application.ports import (
    WorkflowCatalogSnapshot,
    WorkflowNodeSnapshot,
    WorkflowSnapshot,
)
from cyrvanta.modules.operations.application.schemas import AutomationRequest
from cyrvanta.modules.operations.application.service import OperationsService


async def test_demo_automation_is_idempotent(monkeypatch: MonkeyPatch) -> None:
    service = OperationsService()
    monkeypatch.setattr(service.settings, "n8n_mode", "simulated")
    payload = AutomationRequest(
        incident_id="00000000-0000-0000-0000-000000000001",
        workflow_id="cyrvanta-demo-response",
        approved=True,
        idempotency_key="same-demo-key",
    )
    first = await service.execute(payload)
    second = await service.execute(payload)
    assert first.execution_id == second.execution_id
    assert first.status == "simulated_completed"


async def test_unapproved_automation_fails_closed() -> None:
    service = OperationsService()
    payload = AutomationRequest(
        incident_id="00000000-0000-0000-0000-000000000001",
        workflow_id="cyrvanta-demo-response",
        approved=False,
        idempotency_key="blocked-demo-key",
    )
    try:
        await service.execute(payload)
    except ValueError as exc:
        assert "approval" in str(exc).lower()
    else:
        raise AssertionError("unapproved execution should fail")


def test_mitre_catalog_uses_stable_ids() -> None:
    assert {item.external_id for item in OperationsService.techniques()} == {
        "T1110", "T1078", "T1098"
    }


async def test_live_automation_calls_adapter(monkeypatch: MonkeyPatch) -> None:
    service = OperationsService()
    monkeypatch.setattr(service.settings, "n8n_mode", "live")
    calls: list[AutomationRequest] = []

    async def adapter(payload: AutomationRequest) -> None:
        calls.append(payload)

    monkeypatch.setattr(service, "_n8n_execute", adapter)
    payload = AutomationRequest(
        incident_id="00000000-0000-0000-0000-000000000001",
        workflow_id="cyrvanta-demo-response",
        approved=True,
        idempotency_key="approved-live-key",
    )
    result = await service.execute(payload)
    assert calls == [payload]
    assert result.mode == "live"
    assert result.status == "completed"


async def test_disabled_automation_fails_closed(monkeypatch: MonkeyPatch) -> None:
    service = OperationsService()
    monkeypatch.setattr(service.settings, "n8n_mode", "disabled")
    payload = AutomationRequest(
        incident_id="00000000-0000-0000-0000-000000000001",
        workflow_id="cyrvanta-demo-response",
        approved=True,
        idempotency_key="blocked-disabled-key",
    )
    with pytest.raises(ValueError, match="disabled"):
        await service.execute(payload)


class FakeWorkflowCatalog:
    async def list_workflows(self) -> WorkflowCatalogSnapshot:
        return WorkflowCatalogSnapshot(
            workflows=(
                WorkflowSnapshot(
                    workflow_id="cyrvanta-demo-response",
                    name="Cyrvanta Demo Response",
                    active=True,
                    version_id="synthetic-version",
                    nodes=(
                        WorkflowNodeSnapshot(
                            node_type="n8n-nodes-base.webhook",
                            name="Approved request",
                            credential_names=("Synthetic credential label",),
                        ),
                    ),
                ),
                WorkflowSnapshot(
                    workflow_id="not-allowlisted",
                    name="Must remain hidden",
                    active=True,
                    version_id=None,
                    nodes=(),
                ),
            ),
            synchronized=True,
            detail="synchronized",
        )


async def test_playbook_catalog_only_exposes_allowlisted_metadata(
    monkeypatch: MonkeyPatch,
) -> None:
    service = OperationsService(workflow_catalog=FakeWorkflowCatalog())
    monkeypatch.setattr(
        service.settings, "n8n_allowed_workflow_ids", "cyrvanta-demo-response"
    )

    result = await service.playbooks(limit=10, offset=0, query=None)

    assert result.synchronized is True
    assert result.total == 1
    assert result.items[0].workflow_id == "cyrvanta-demo-response"
    assert result.items[0].connectors[0].credential_names == [
        "Synthetic credential label"
    ]


async def test_playbook_catalog_is_bounded_and_searchable(
    monkeypatch: MonkeyPatch,
) -> None:
    service = OperationsService()
    monkeypatch.setattr(
        service.settings,
        "n8n_allowed_workflow_ids",
        "cyrvanta-demo-response,another-safe-workflow",
    )

    result = await service.playbooks(limit=1, offset=0, query="demo")

    assert result.total == 1
    assert len(result.items) == 1
    assert result.items[0].workflow_id == "cyrvanta-demo-response"
