from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class WorkflowNodeSnapshot:
    node_type: str
    name: str
    credential_names: tuple[str, ...]


@dataclass(frozen=True)
class WorkflowSnapshot:
    workflow_id: str
    name: str
    active: bool
    version_id: str | None
    nodes: tuple[WorkflowNodeSnapshot, ...]


@dataclass(frozen=True)
class WorkflowCatalogSnapshot:
    workflows: tuple[WorkflowSnapshot, ...]
    synchronized: bool
    detail: str


class WorkflowCatalogPort(Protocol):
    async def list_workflows(self) -> WorkflowCatalogSnapshot: ...
