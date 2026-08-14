from pytest import MonkeyPatch

from cyrvanta.modules.operations.application.ports import (
    WorkflowCatalogSnapshot,
    WorkflowNodeSnapshot,
    WorkflowSnapshot,
)
from cyrvanta.modules.operations.application.service import OperationsService


def test_mitre_catalog_uses_stable_ids() -> None:
    assert {item.external_id for item in OperationsService.techniques()} == {
        "T1110",
        "T1078",
        "T1098",
    }


class FakeWorkflowCatalog:
    async def list_workflows(self) -> WorkflowCatalogSnapshot:
        return WorkflowCatalogSnapshot(
            workflows=(
                WorkflowSnapshot(
                    workflow_id="cyrvanta-simulate-user-block",
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
        service.settings, "n8n_allowed_workflow_ids", "cyrvanta-simulate-user-block"
    )

    result = await service.playbooks(limit=10, offset=0, query=None)

    assert result.synchronized is True
    assert result.total == 1
    assert result.items[0].workflow_id == "cyrvanta-simulate-user-block"
    assert result.items[0].connectors[0].credential_names == ["Synthetic credential label"]


async def test_playbook_catalog_is_bounded_and_searchable(
    monkeypatch: MonkeyPatch,
) -> None:
    service = OperationsService()
    monkeypatch.setattr(
        service.settings,
        "n8n_allowed_workflow_ids",
        "cyrvanta-simulate-user-block,another-safe-workflow",
    )

    result = await service.playbooks(limit=1, offset=0, query="simulate")

    assert result.total == 1
    assert len(result.items) == 1
    assert result.items[0].workflow_id == "cyrvanta-simulate-user-block"
