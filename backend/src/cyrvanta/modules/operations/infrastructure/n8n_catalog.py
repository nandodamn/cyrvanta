from collections.abc import Mapping
from typing import Any

import httpx

from cyrvanta.modules.operations.application.ports import (
    WorkflowCatalogSnapshot,
    WorkflowNodeSnapshot,
    WorkflowSnapshot,
)
from cyrvanta.shared.config import Settings


class N8nWorkflowCatalog:
    """Read-only n8n metadata adapter. Credential values are never requested."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def list_workflows(self) -> WorkflowCatalogSnapshot:
        if not self.settings.n8n_api_key:
            return WorkflowCatalogSnapshot((), False, "api_key_not_configured")
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(
                    f"{self.settings.n8n_base_url}/api/v1/workflows",
                    params={"limit": 100},
                    headers={"X-N8N-API-KEY": self.settings.n8n_api_key},
                )
                response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            return WorkflowCatalogSnapshot((), False, "n8n_api_unavailable")

        raw_workflows = payload.get("data") if isinstance(payload, Mapping) else None
        if not isinstance(raw_workflows, list):
            return WorkflowCatalogSnapshot((), False, "invalid_n8n_response")

        workflows = tuple(
            workflow
            for item in raw_workflows
            if isinstance(item, Mapping) and (workflow := self._workflow(item)) is not None
        )
        return WorkflowCatalogSnapshot(workflows, True, "synchronized")

    @staticmethod
    def _workflow(item: Mapping[str, Any]) -> WorkflowSnapshot | None:
        workflow_id = item.get("id")
        name = item.get("name")
        if not isinstance(workflow_id, str) or not isinstance(name, str):
            return None
        raw_nodes = item.get("nodes")
        nodes = (
            tuple(
                node
                for value in raw_nodes
                if isinstance(value, Mapping)
                if (node := N8nWorkflowCatalog._node(value)) is not None
            )
            if isinstance(raw_nodes, list)
            else ()
        )
        version_id = item.get("versionId")
        return WorkflowSnapshot(
            workflow_id=workflow_id,
            name=name,
            active=item.get("active") is True,
            version_id=version_id if isinstance(version_id, str) else None,
            nodes=nodes,
        )

    @staticmethod
    def _node(item: Mapping[str, Any]) -> WorkflowNodeSnapshot | None:
        node_type = item.get("type")
        name = item.get("name")
        if not isinstance(node_type, str) or not isinstance(name, str):
            return None
        credential_names: list[str] = []
        raw_credentials = item.get("credentials")
        if isinstance(raw_credentials, Mapping):
            for credential in raw_credentials.values():
                if isinstance(credential, Mapping):
                    credential_name = credential.get("name")
                    if isinstance(credential_name, str):
                        credential_names.append(credential_name)
        return WorkflowNodeSnapshot(
            node_type=node_type,
            name=name,
            credential_names=tuple(sorted(set(credential_names))),
        )
