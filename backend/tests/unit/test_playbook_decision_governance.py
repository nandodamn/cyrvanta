from types import SimpleNamespace
from uuid import uuid4

import pytest

from cyrvanta.modules.decision.application.governance import ActionGovernance
from cyrvanta.modules.decision.application.schemas import ActionProposalCreate
from cyrvanta.modules.decision.application.service import DecisionConflict, DecisionService
from cyrvanta.modules.decision.domain.models import ActionImpact, ResponseMode
from cyrvanta.modules.playbooks.application.service import (
    PlaybookConflict,
    PlaybookExecutionService,
)


def _proposal_payload(
    *,
    impact: ActionImpact = ActionImpact.MODERATE,
    mode: ResponseMode = ResponseMode.HUMAN_APPROVAL,
) -> ActionProposalCreate:
    incident_id = uuid4()
    return ActionProposalCreate(
        incident_id=incident_id,
        action_type="notify-critical-incident",
        impact=impact,
        requested_mode=mode,
        workflow_id="notify-critical-incident",
        workflow_version="1.0.0",
        targets=[str(incident_id)],
    )


def test_proposal_rejects_client_governance_downgrade() -> None:
    payload = _proposal_payload(mode=ResponseMode.HUMAN_APPROVAL)
    governance = ActionGovernance(
        impact=ActionImpact.MODERATE,
        response_mode=ResponseMode.DUAL_APPROVAL,
    )

    with pytest.raises(DecisionConflict, match="approval mode"):
        DecisionService._validate_requested_governance(payload, governance)


def test_execution_revalidates_current_four_eyes_quorum() -> None:
    proposal = SimpleNamespace(
        impact=ActionImpact.MODERATE.value,
        requested_mode=ResponseMode.DUAL_APPROVAL.value,
    )
    approval_request = SimpleNamespace(required_approvals=2)

    with pytest.raises(PlaybookConflict, match="quorum"):
        PlaybookExecutionService._validate_definition_governance(
            definition_approval_mode="FOUR_EYES",
            version_impact=ActionImpact.MODERATE.value,
            proposal=proposal,
            approval_request=approval_request,
            approval_count=1,
        )

    PlaybookExecutionService._validate_definition_governance(
        definition_approval_mode="FOUR_EYES",
        version_impact=ActionImpact.MODERATE.value,
        proposal=proposal,
        approval_request=approval_request,
        approval_count=2,
    )


def test_execution_rejects_governance_changed_after_authorization() -> None:
    proposal = SimpleNamespace(
        impact=ActionImpact.MODERATE.value,
        requested_mode=ResponseMode.HUMAN_APPROVAL.value,
    )
    approval_request = SimpleNamespace(required_approvals=1)

    with pytest.raises(PlaybookConflict, match="changed"):
        PlaybookExecutionService._validate_definition_governance(
            definition_approval_mode="FOUR_EYES",
            version_impact=ActionImpact.MODERATE.value,
            proposal=proposal,
            approval_request=approval_request,
            approval_count=1,
        )
