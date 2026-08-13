from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from cyrvanta.modules.decision.application.governance import (
    ActionGovernance,
    ActionGovernancePort,
)
from cyrvanta.modules.decision.application.schemas import (
    ActionProposalCreate,
    ActionProposalList,
    ActionProposalResponse,
    ApprovalDecisionCreate,
    ApprovalDecisionResponse,
    AuthorizationResponse,
)
from cyrvanta.modules.decision.domain.models import (
    EvaluationOutcome,
    canonical_fingerprint,
    evaluate_policy,
    validate_target_limit,
)
from cyrvanta.modules.decision.infrastructure.models import (
    ActionAuthorizationModel,
    ActionProposalModel,
    ApprovalDecisionModel,
    ApprovalRequestModel,
    PolicyEvaluationModel,
    ResponsePolicyVersionModel,
)
from cyrvanta.modules.identity.infrastructure.models import AuditEventModel, UserModel
from cyrvanta.modules.incident.infrastructure.models import IncidentModel
from cyrvanta.shared.config import get_settings
from cyrvanta.shared.database import SessionFactory, tenant_session
from cyrvanta.shared.domain.events import DomainEvent
from cyrvanta.shared.infrastructure.event_store import SqlEventStore

EVENT_ACTION_PROPOSAL_CREATED = "security.action_proposal.created"
EVENT_POLICY_EVALUATION_COMPLETED = "security.policy_evaluation.completed"
EVENT_APPROVAL_REQUESTED = "security.approval.requested"
EVENT_APPROVAL_DECIDED = "security.approval.decided"
EVENT_AUTHORIZATION_ISSUED = "security.authorization.issued"
EVENT_AUTHORIZATION_REVOKED = "security.authorization.revoked"
EVENT_AUTHORIZATION_EXPIRED = "security.authorization.expired"
DECISION_EVENT_NAMES = frozenset(
    {
        EVENT_ACTION_PROPOSAL_CREATED,
        EVENT_POLICY_EVALUATION_COMPLETED,
        EVENT_APPROVAL_REQUESTED,
        EVENT_APPROVAL_DECIDED,
        EVENT_AUTHORIZATION_ISSUED,
        EVENT_AUTHORIZATION_REVOKED,
        EVENT_AUTHORIZATION_EXPIRED,
    }
)


class DecisionConflict(ValueError):
    pass


class DecisionNotFound(LookupError):
    pass


class DecisionService:
    def __init__(self, governance: ActionGovernancePort | None = None) -> None:
        self._governance = governance

    async def expire_due(self, batch_size: int = 100) -> tuple[int, int]:
        if batch_size < 1 or batch_size > 500:
            raise ValueError("Decision expiration batch size must be between 1 and 500")
        async with SessionFactory() as discovery_session, discovery_session.begin():
            request_rows = (
                (
                    await discovery_session.execute(
                        text(
                            "SELECT * FROM public."
                            "list_due_approval_request_expirations(:batch_size)"
                        ),
                        {"batch_size": batch_size},
                    )
                )
                .mappings()
                .all()
            )
            authorization_rows = (
                (
                    await discovery_session.execute(
                        text(
                            "SELECT * FROM public.list_due_authorization_expirations(:batch_size)"
                        ),
                        {"batch_size": batch_size},
                    )
                )
                .mappings()
                .all()
            )

        expired_requests = 0
        for row in request_rows:
            tenant_id = UUID(str(row["tenant_id"]))
            request_id = UUID(str(row["approval_request_id"]))
            correlation_id = uuid4()
            async with tenant_session(tenant_id) as session:
                request = await session.scalar(
                    select(ApprovalRequestModel)
                    .where(
                        ApprovalRequestModel.tenant_id == tenant_id,
                        ApprovalRequestModel.id == request_id,
                    )
                    .with_for_update()
                )
                if (
                    request is None
                    or request.status != "PENDING"
                    or request.expires_at > datetime.now(UTC)
                ):
                    continue
                proposal = await session.scalar(
                    select(ActionProposalModel)
                    .where(
                        ActionProposalModel.tenant_id == tenant_id,
                        ActionProposalModel.is_simulated.is_(False),
                        ActionProposalModel.id == request.proposal_id,
                    )
                    .with_for_update()
                )
                if proposal is None:
                    continue
                request.status = "EXPIRED"
                proposal.status = "EXPIRED"
                await self._record(
                    session,
                    tenant_id,
                    None,
                    correlation_id,
                    "response.approval.expired",
                    request.id,
                    {
                        "proposal_id": str(proposal.id),
                        "expiration_instant": request.expires_at.isoformat(),
                    },
                )
                expired_requests += 1

        expired_authorizations = 0
        for row in authorization_rows:
            tenant_id = UUID(str(row["tenant_id"]))
            authorization_id = UUID(str(row["authorization_id"]))
            correlation_id = uuid4()
            async with tenant_session(tenant_id) as session:
                authorization = await session.scalar(
                    select(ActionAuthorizationModel)
                    .where(
                        ActionAuthorizationModel.tenant_id == tenant_id,
                        ActionAuthorizationModel.id == authorization_id,
                    )
                    .with_for_update()
                )
                if (
                    authorization is None
                    or authorization.status != "ACTIVE"
                    or authorization.expires_at > datetime.now(UTC)
                ):
                    continue
                proposal = await session.scalar(
                    select(ActionProposalModel)
                    .where(
                        ActionProposalModel.tenant_id == tenant_id,
                        ActionProposalModel.is_simulated.is_(False),
                        ActionProposalModel.id == authorization.proposal_id,
                    )
                    .with_for_update()
                )
                if proposal is None:
                    continue
                authorization.status = "EXPIRED"
                proposal.status = "EXPIRED"
                await self._record(
                    session,
                    tenant_id,
                    None,
                    correlation_id,
                    "response.authorization.expired",
                    authorization.id,
                    {
                        "proposal_id": str(proposal.id),
                        "fingerprint": authorization.proposal_fingerprint,
                        "expiration_instant": authorization.expires_at.isoformat(),
                    },
                )
                await self._event(
                    session,
                    tenant_id,
                    correlation_id,
                    EVENT_AUTHORIZATION_EXPIRED,
                    authorization.id,
                    {
                        "authorization_id": str(authorization.id),
                        "proposal_id": str(proposal.id),
                        "fingerprint": authorization.proposal_fingerprint,
                        "expired_at": authorization.expires_at.isoformat(),
                    },
                )
                expired_authorizations += 1
        return expired_requests, expired_authorizations

    async def create_proposal(
        self,
        *,
        tenant_id: UUID,
        requester_user_id: UUID,
        payload: ActionProposalCreate,
        correlation_id: UUID,
        idempotency_key: str,
    ) -> ActionProposalResponse:
        if self._governance is None:
            raise DecisionConflict("Authoritative action governance is unavailable")
        governance = await self._governance.resolve(
            tenant_id=tenant_id,
            action_type=payload.action_type,
            workflow_id=payload.workflow_id,
            workflow_version=payload.workflow_version,
        )
        self._validate_requested_governance(payload, governance)
        validate_target_limit(payload.impact, len(payload.targets))
        if len(json.dumps(payload.parameters, ensure_ascii=False).encode()) > 32 * 1024:
            raise DecisionConflict("Parameters exceed the approved size limit")
        now = datetime.now(UTC)
        async with tenant_session(tenant_id) as session:
            incident = await session.scalar(
                select(IncidentModel).where(
                    IncidentModel.tenant_id == tenant_id,
                    IncidentModel.id == payload.incident_id,
                    IncidentModel.is_simulated.is_(False),
                )
            )
            requester = await session.scalar(
                select(UserModel).where(
                    UserModel.tenant_id == tenant_id,
                    UserModel.id == requester_user_id,
                    UserModel.is_active.is_(True),
                )
            )
            policy = await session.scalar(
                select(ResponsePolicyVersionModel)
                .where(
                    ResponsePolicyVersionModel.tenant_id == tenant_id,
                    ResponsePolicyVersionModel.status == "ACTIVE",
                )
                .order_by(ResponsePolicyVersionModel.created_at.desc())
                .limit(1)
            )
            if incident is None or requester is None or policy is None:
                raise DecisionNotFound("Required tenant resource was not found")
            material = {
                "tenant_id": str(tenant_id),
                "incident_id": str(incident.id),
                "incident_version": incident.version,
                "requester_user_id": str(requester_user_id),
                "action_type": payload.action_type,
                "impact": payload.impact.value,
                "requested_mode": payload.requested_mode.value,
                "workflow_id": payload.workflow_id,
                "workflow_version": payload.workflow_version,
                "targets": payload.targets,
                "parameters": payload.parameters,
                "evidence_refs": sorted(str(item) for item in payload.evidence_refs),
                "policy_version_id": str(policy.id),
                "idempotency_key": idempotency_key,
            }
            fingerprint = canonical_fingerprint(material)
            existing = await session.scalar(
                select(ActionProposalModel).where(
                    ActionProposalModel.tenant_id == tenant_id,
                    ActionProposalModel.is_simulated.is_(False),
                    ActionProposalModel.fingerprint == fingerprint,
                )
            )
            if existing is not None:
                return await self._response(session, existing)
            result = evaluate_policy(
                impact=payload.impact,
                requested_mode=payload.requested_mode,
                global_kill_switch=get_settings().automation_kill_switch,
                tenant_kill_switch=policy.kill_switch,
                is_simulated=incident.is_simulated,
            )
            proposal = ActionProposalModel(
                tenant_id=tenant_id,
                incident_id=incident.id,
                requester_user_id=requester_user_id,
                policy_version_id=policy.id,
                action_type=payload.action_type,
                impact=payload.impact.value,
                requested_mode=payload.requested_mode.value,
                workflow_id=payload.workflow_id,
                workflow_version=payload.workflow_version,
                targets=payload.targets,
                parameters=payload.parameters,
                evidence_refs=[str(item) for item in payload.evidence_refs],
                incident_version=incident.version,
                is_simulated=incident.is_simulated,
                fingerprint=fingerprint,
                status=(
                    "DENIED" if result.outcome is EvaluationOutcome.DENIED else "AWAITING_APPROVAL"
                ),
            )
            session.add(proposal)
            await session.flush()
            evaluation = PolicyEvaluationModel(
                tenant_id=tenant_id,
                proposal_id=proposal.id,
                policy_version_id=policy.id,
                outcome=result.outcome.value,
                required_approvals=result.required_approvals,
                reason_codes=list(result.reason_codes),
                input_fingerprint=fingerprint,
            )
            session.add(evaluation)
            await session.flush()
            request: ApprovalRequestModel | None = None
            if result.required_approvals:
                request = ApprovalRequestModel(
                    tenant_id=tenant_id,
                    proposal_id=proposal.id,
                    evaluation_id=evaluation.id,
                    required_approvals=result.required_approvals,
                    status="PENDING",
                    expires_at=now + timedelta(minutes=30),
                )
                session.add(request)
                await session.flush()
            await self._record(
                session,
                tenant_id,
                requester_user_id,
                correlation_id,
                "response.proposal.created",
                proposal.id,
                {
                    "action_type": proposal.action_type,
                    "impact": proposal.impact,
                    "outcome": result.outcome.value,
                    "fingerprint": fingerprint,
                    "simulated": incident.is_simulated,
                },
            )
            await self._event(
                session,
                tenant_id,
                correlation_id,
                EVENT_ACTION_PROPOSAL_CREATED,
                proposal.id,
                {
                    "proposal_id": str(proposal.id),
                    "incident_id": str(proposal.incident_id),
                    "fingerprint": fingerprint,
                    "action_type": proposal.action_type,
                    "impact": proposal.impact,
                    "outcome": result.outcome.value,
                },
            )
            await self._event(
                session,
                tenant_id,
                correlation_id,
                EVENT_POLICY_EVALUATION_COMPLETED,
                evaluation.id,
                {
                    "evaluation_id": str(evaluation.id),
                    "proposal_id": str(proposal.id),
                    "policy_version_id": str(policy.id),
                    "fingerprint": fingerprint,
                    "outcome": result.outcome.value,
                    "required_approvals": result.required_approvals,
                    "reason_codes": list(result.reason_codes),
                },
            )
            if request is not None:
                await self._event(
                    session,
                    tenant_id,
                    correlation_id,
                    EVENT_APPROVAL_REQUESTED,
                    request.id,
                    {
                        "approval_request_id": str(request.id),
                        "proposal_id": str(proposal.id),
                        "fingerprint": fingerprint,
                        "required_approvals": request.required_approvals,
                        "expires_at": request.expires_at.isoformat(),
                    },
                )
            return await self._response(session, proposal)

    @staticmethod
    def _validate_requested_governance(
        payload: ActionProposalCreate,
        governance: ActionGovernance | None,
    ) -> None:
        if governance is None:
            raise DecisionConflict("Released playbook governance was not found")
        if payload.impact is not governance.impact:
            raise DecisionConflict("Requested impact does not match released playbook governance")
        if payload.requested_mode is not governance.response_mode:
            raise DecisionConflict(
                "Requested approval mode does not match tenant playbook governance"
            )

    async def list_proposals(
        self, tenant_id: UUID, *, incident_id: UUID | None, limit: int, offset: int
    ) -> ActionProposalList:
        async with tenant_session(tenant_id) as session:
            statement = select(ActionProposalModel).where(
                ActionProposalModel.tenant_id == tenant_id,
                ActionProposalModel.is_simulated.is_(False),
            )
            count_statement = select(func.count(ActionProposalModel.id)).where(
                ActionProposalModel.tenant_id == tenant_id,
                ActionProposalModel.is_simulated.is_(False),
            )
            if incident_id is not None:
                statement = statement.where(ActionProposalModel.incident_id == incident_id)
                count_statement = count_statement.where(
                    ActionProposalModel.incident_id == incident_id
                )
            proposals = list(
                (
                    await session.scalars(
                        statement.order_by(ActionProposalModel.created_at.desc())
                        .limit(limit)
                        .offset(offset)
                    )
                ).all()
            )
            total = int(await session.scalar(count_statement) or 0)
            return ActionProposalList(
                items=[await self._response(session, item) for item in proposals],
                total=total,
            )

    async def get_proposal(self, tenant_id: UUID, proposal_id: UUID) -> ActionProposalResponse:
        async with tenant_session(tenant_id) as session:
            proposal = await session.scalar(
                select(ActionProposalModel).where(
                    ActionProposalModel.tenant_id == tenant_id,
                    ActionProposalModel.is_simulated.is_(False),
                    ActionProposalModel.id == proposal_id,
                )
            )
            if proposal is None:
                raise DecisionNotFound("Proposal was not found")
            return await self._response(session, proposal)

    async def decide(
        self,
        *,
        tenant_id: UUID,
        actor_user_id: UUID,
        approval_request_id: UUID,
        payload: ApprovalDecisionCreate,
        correlation_id: UUID,
    ) -> ActionProposalResponse:
        now = datetime.now(UTC)
        async with tenant_session(tenant_id) as session:
            request = await session.scalar(
                select(ApprovalRequestModel)
                .where(
                    ApprovalRequestModel.tenant_id == tenant_id,
                    ApprovalRequestModel.id == approval_request_id,
                )
                .with_for_update()
            )
            if request is None:
                raise DecisionNotFound("Approval request was not found")
            proposal = await session.scalar(
                select(ActionProposalModel).where(
                    ActionProposalModel.tenant_id == tenant_id,
                    ActionProposalModel.is_simulated.is_(False),
                    ActionProposalModel.id == request.proposal_id,
                )
            )
            actor = await session.scalar(
                select(UserModel).where(
                    UserModel.tenant_id == tenant_id,
                    UserModel.id == actor_user_id,
                    UserModel.is_active.is_(True),
                )
            )
            if proposal is None or actor is None:
                raise DecisionNotFound("Required tenant resource was not found")
            if request.status != "PENDING":
                raise DecisionConflict("Approval request is not pending")
            if request.expires_at <= now:
                request.status = "EXPIRED"
                proposal.status = "EXPIRED"
                raise DecisionConflict("Approval request has expired")
            if proposal.fingerprint != payload.expected_proposal_fingerprint:
                raise DecisionConflict("Proposal fingerprint no longer matches")
            if actor_user_id == proposal.requester_user_id:
                raise DecisionConflict("Requester cannot approve the proposal")
            existing = await session.scalar(
                select(ApprovalDecisionModel).where(
                    ApprovalDecisionModel.tenant_id == tenant_id,
                    ApprovalDecisionModel.approval_request_id == request.id,
                    ApprovalDecisionModel.actor_user_id == actor_user_id,
                )
            )
            if existing is not None:
                if existing.decision == payload.decision:
                    return await self._response(session, proposal)
                raise DecisionConflict("Actor already decided this request")
            decision = ApprovalDecisionModel(
                tenant_id=tenant_id,
                approval_request_id=request.id,
                actor_user_id=actor_user_id,
                decision=payload.decision,
                reason=payload.reason.strip(),
                proposal_fingerprint=proposal.fingerprint,
            )
            session.add(decision)
            await session.flush()
            authorization: ActionAuthorizationModel | None = None
            if payload.decision == "REJECT":
                request.status = "REJECTED"
                proposal.status = "REJECTED"
            else:
                approvals = int(
                    await session.scalar(
                        select(func.count(ApprovalDecisionModel.id)).where(
                            ApprovalDecisionModel.tenant_id == tenant_id,
                            ApprovalDecisionModel.approval_request_id == request.id,
                            ApprovalDecisionModel.decision == "APPROVE",
                        )
                    )
                    or 0
                )
                if approvals >= request.required_approvals:
                    request.status = "APPROVED"
                    proposal.status = "AUTHORIZED"
                    authorization = ActionAuthorizationModel(
                        tenant_id=tenant_id,
                        proposal_id=proposal.id,
                        approval_request_id=request.id,
                        proposal_fingerprint=proposal.fingerprint,
                        status="ACTIVE",
                        expires_at=now + timedelta(minutes=5),
                    )
                    session.add(authorization)
                    await session.flush()
            await self._record(
                session,
                tenant_id,
                actor_user_id,
                correlation_id,
                "response.approval.decided",
                request.id,
                {
                    "proposal_id": str(proposal.id),
                    "decision": payload.decision,
                    "status": request.status,
                    "fingerprint": proposal.fingerprint,
                },
            )
            await self._event(
                session,
                tenant_id,
                correlation_id,
                EVENT_APPROVAL_DECIDED,
                request.id,
                {
                    "approval_request_id": str(request.id),
                    "proposal_id": str(proposal.id),
                    "decision": payload.decision,
                    "status": request.status,
                    "fingerprint": proposal.fingerprint,
                },
            )
            if authorization is not None:
                await self._event(
                    session,
                    tenant_id,
                    correlation_id,
                    EVENT_AUTHORIZATION_ISSUED,
                    authorization.id,
                    {
                        "authorization_id": str(authorization.id),
                        "approval_request_id": str(request.id),
                        "proposal_id": str(proposal.id),
                        "fingerprint": proposal.fingerprint,
                        "expires_at": authorization.expires_at.isoformat(),
                    },
                )
            await session.flush()
            return await self._response(session, proposal)

    async def revoke(
        self,
        *,
        tenant_id: UUID,
        actor_user_id: UUID,
        authorization_id: UUID,
        correlation_id: UUID,
    ) -> ActionProposalResponse:
        now = datetime.now(UTC)
        async with tenant_session(tenant_id) as session:
            authorization = await session.scalar(
                select(ActionAuthorizationModel)
                .where(
                    ActionAuthorizationModel.tenant_id == tenant_id,
                    ActionAuthorizationModel.id == authorization_id,
                )
                .with_for_update()
            )
            if authorization is None:
                raise DecisionNotFound("Authorization was not found")
            if authorization.status != "ACTIVE":
                raise DecisionConflict("Authorization is not active")
            authorization.status = "REVOKED"
            authorization.revoked_at = now
            proposal = await session.scalar(
                select(ActionProposalModel).where(
                    ActionProposalModel.tenant_id == tenant_id,
                    ActionProposalModel.is_simulated.is_(False),
                    ActionProposalModel.id == authorization.proposal_id,
                )
            )
            if proposal is None:
                raise DecisionNotFound("Proposal was not found")
            proposal.status = "REVOKED"
            await self._record(
                session,
                tenant_id,
                actor_user_id,
                correlation_id,
                "response.authorization.revoked",
                authorization.id,
                {"proposal_id": str(proposal.id), "fingerprint": proposal.fingerprint},
            )
            await self._event(
                session,
                tenant_id,
                correlation_id,
                EVENT_AUTHORIZATION_REVOKED,
                authorization.id,
                {
                    "authorization_id": str(authorization.id),
                    "proposal_id": str(proposal.id),
                    "fingerprint": proposal.fingerprint,
                    "revoked_at": now.isoformat(),
                },
            )
            return await self._response(session, proposal)

    async def _response(
        self, session: AsyncSession, proposal: ActionProposalModel
    ) -> ActionProposalResponse:
        evaluation = await session.scalar(
            select(PolicyEvaluationModel)
            .where(
                PolicyEvaluationModel.tenant_id == proposal.tenant_id,
                PolicyEvaluationModel.proposal_id == proposal.id,
            )
            .order_by(PolicyEvaluationModel.created_at.desc())
            .limit(1)
        )
        if evaluation is None:
            raise RuntimeError("Proposal evaluation is missing")
        request = await session.scalar(
            select(ApprovalRequestModel).where(
                ApprovalRequestModel.tenant_id == proposal.tenant_id,
                ApprovalRequestModel.proposal_id == proposal.id,
            )
        )
        decisions: list[ApprovalDecisionModel] = []
        authorization = None
        if request is not None:
            decisions = list(
                (
                    await session.scalars(
                        select(ApprovalDecisionModel)
                        .where(
                            ApprovalDecisionModel.tenant_id == proposal.tenant_id,
                            ApprovalDecisionModel.approval_request_id == request.id,
                        )
                        .order_by(ApprovalDecisionModel.created_at)
                    )
                ).all()
            )
            authorization = await session.scalar(
                select(ActionAuthorizationModel).where(
                    ActionAuthorizationModel.tenant_id == proposal.tenant_id,
                    ActionAuthorizationModel.approval_request_id == request.id,
                )
            )
        return ActionProposalResponse(
            id=proposal.id,
            incident_id=proposal.incident_id,
            requester_user_id=proposal.requester_user_id,
            action_type=proposal.action_type,
            impact=proposal.impact,
            requested_mode=proposal.requested_mode,
            workflow_id=proposal.workflow_id,
            workflow_version=proposal.workflow_version,
            targets=list(proposal.targets),
            parameters=dict(proposal.parameters),
            evidence_refs=[UUID(item) for item in proposal.evidence_refs],
            incident_version=proposal.incident_version,
            is_simulated=proposal.is_simulated,
            fingerprint=proposal.fingerprint,
            status=proposal.status,
            evaluation_outcome=evaluation.outcome,
            reason_codes=list(evaluation.reason_codes),
            approval_request_id=request.id if request else None,
            required_approvals=evaluation.required_approvals,
            approval_status=request.status if request else None,
            approval_expires_at=request.expires_at if request else None,
            decisions=[
                ApprovalDecisionResponse(
                    id=item.id,
                    actor_user_id=item.actor_user_id,
                    decision=item.decision,
                    reason=item.reason,
                    created_at=item.created_at,
                )
                for item in decisions
            ],
            authorization=(
                AuthorizationResponse(
                    id=authorization.id,
                    status=authorization.status,
                    expires_at=authorization.expires_at,
                )
                if authorization
                else None
            ),
            created_at=proposal.created_at,
        )

    async def _event(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        correlation_id: UUID,
        event_name: str,
        aggregate_id: UUID,
        payload: dict[str, object],
    ) -> None:
        store = SqlEventStore(
            session_factory=SessionFactory,
            max_payload_bytes=get_settings().event_max_payload_bytes,
        )
        await store.recorder(session).add(
            DomainEvent.create(
                event_name=event_name,
                tenant_id=tenant_id,
                aggregate_type="response_decision",
                aggregate_id=aggregate_id,
                correlation_id=correlation_id,
                producer="decision",
                payload=payload,
            )
        )

    @staticmethod
    async def _record(
        session: AsyncSession,
        tenant_id: UUID,
        actor_user_id: UUID | None,
        correlation_id: UUID,
        action: str,
        resource_id: UUID,
        details: dict[str, object],
    ) -> None:
        session.add(
            AuditEventModel(
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                action=action,
                resource_type="response_decision",
                resource_id=resource_id,
                outcome="success",
                correlation_id=correlation_id,
                details=details,
            )
        )
