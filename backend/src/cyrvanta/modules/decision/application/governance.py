from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from cyrvanta.modules.decision.domain.models import ActionImpact, ResponseMode


@dataclass(frozen=True)
class ActionGovernance:
    impact: ActionImpact
    response_mode: ResponseMode


class ActionGovernancePort(Protocol):
    async def resolve(
        self,
        *,
        tenant_id: UUID,
        action_type: str,
        workflow_id: str,
        workflow_version: str,
    ) -> ActionGovernance | None: ...
