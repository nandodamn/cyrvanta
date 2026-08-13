from uuid import UUID

from sqlalchemy import select

from cyrvanta.modules.decision.application.governance import (
    ActionGovernance,
    ActionGovernancePort,
)
from cyrvanta.modules.decision.domain.models import ActionImpact, ResponseMode
from cyrvanta.modules.playbooks.infrastructure.models import (
    PlaybookDefinitionModel,
    PlaybookVersionModel,
)
from cyrvanta.shared.database import tenant_session

APPROVAL_RESPONSE_MODES = {
    "AUTOMATIC": ResponseMode.AUTOMATIC,
    "SINGLE": ResponseMode.HUMAN_APPROVAL,
    "FOUR_EYES": ResponseMode.DUAL_APPROVAL,
}


class PlaybookActionGovernanceAdapter(ActionGovernancePort):
    async def resolve(
        self,
        *,
        tenant_id: UUID,
        action_type: str,
        workflow_id: str,
        workflow_version: str,
    ) -> ActionGovernance | None:
        async with tenant_session(tenant_id) as session:
            rows = list(
                (
                    await session.execute(
                        select(PlaybookDefinitionModel, PlaybookVersionModel)
                        .join(
                            PlaybookVersionModel,
                            PlaybookVersionModel.definition_id == PlaybookDefinitionModel.id,
                        )
                        .where(
                            PlaybookDefinitionModel.tenant_id == tenant_id,
                            PlaybookDefinitionModel.action_type == action_type,
                            PlaybookVersionModel.tenant_id == tenant_id,
                            PlaybookVersionModel.workflow_code == workflow_id,
                            PlaybookVersionModel.version == workflow_version,
                            PlaybookVersionModel.status == "APPROVED",
                            PlaybookVersionModel.classification == "LIVE",
                        )
                        .limit(2)
                    )
                ).all()
            )
        if len(rows) != 1:
            return None
        definition, version = rows[0]
        try:
            return ActionGovernance(
                impact=ActionImpact(version.impact),
                response_mode=APPROVAL_RESPONSE_MODES[definition.approval_mode],
            )
        except (KeyError, ValueError):
            return None
