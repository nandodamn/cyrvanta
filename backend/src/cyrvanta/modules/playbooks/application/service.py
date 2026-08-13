from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from cyrvanta.modules.decision.domain.models import (
    ActionImpact,
    EvaluationOutcome,
    ResponseMode,
    evaluate_policy,
)
from cyrvanta.modules.decision.infrastructure.models import (
    ActionAuthorizationModel,
    ActionProposalModel,
    ApprovalDecisionModel,
    ApprovalRequestModel,
    ResponsePolicyVersionModel,
)
from cyrvanta.modules.identity.infrastructure.models import AuditEventModel
from cyrvanta.modules.incident.infrastructure.models import IncidentModel
from cyrvanta.modules.playbooks.application.portable import PortablePlaybookV1
from cyrvanta.modules.playbooks.application.schemas import (
    ExecutionClaim,
    ExecutionUpdate,
    PlaybookExecutionList,
    PlaybookExecutionResponse,
)
from cyrvanta.modules.playbooks.domain.models import (
    ExecutionStatus,
    validate_transition,
)
from cyrvanta.modules.playbooks.infrastructure.action_registry import (
    ActionRegistry,
    ActionUnavailableError,
)
from cyrvanta.modules.playbooks.infrastructure.models import (
    AutomationEngineBindingModel,
    AutomationReplayNonceModel,
    PlaybookDefinitionModel,
    PlaybookExecutionAttemptModel,
    PlaybookExecutionModel,
    PlaybookExecutionUpdateModel,
    PlaybookStepExecutionModel,
    PlaybookVersionModel,
)
from cyrvanta.modules.playbooks.infrastructure.schema_registry import validate_strict_object
from cyrvanta.shared.config import get_settings
from cyrvanta.shared.database import SessionFactory, tenant_session
from cyrvanta.shared.domain.events import DomainEvent
from cyrvanta.shared.infrastructure.event_store import SqlEventStore


class PlaybookNotFound(Exception):
    pass


class PlaybookConflict(Exception):
    pass


class PlaybookSecurityError(Exception):
    pass


class PlaybookExecutionService:
    @staticmethod
    async def resolve_tenant(execution_id: UUID) -> UUID:
        async with SessionFactory() as session:
            tenant_id = await session.scalar(
                text("SELECT resolve_playbook_execution_tenant(:execution_id)"),
                {"execution_id": execution_id},
            )
        if tenant_id is None:
            raise PlaybookNotFound("Execution was not found")
        return UUID(str(tenant_id))

    async def create_from_authorization(
        self,
        *,
        tenant_id: UUID,
        actor_user_id: UUID,
        authorization_id: UUID,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> PlaybookExecutionResponse:
        now = datetime.now(UTC)
        settings = get_settings()
        async with tenant_session(tenant_id) as session:
            existing = await session.scalar(
                select(PlaybookExecutionModel).where(
                    PlaybookExecutionModel.tenant_id == tenant_id,
                    PlaybookExecutionModel.idempotency_key == idempotency_key,
                    PlaybookExecutionModel.execution_mode == "LIVE",
                )
            )
            if existing is not None:
                if existing.authorization_id != authorization_id:
                    raise PlaybookConflict("Idempotency key belongs to another authorization")
                return self._response(existing)
            authorization = await session.scalar(
                select(ActionAuthorizationModel)
                .where(
                    ActionAuthorizationModel.tenant_id == tenant_id,
                    ActionAuthorizationModel.id == authorization_id,
                )
                .with_for_update()
            )
            if authorization is None:
                raise PlaybookNotFound("Authorization was not found")
            proposal = await session.scalar(
                select(ActionProposalModel).where(
                    ActionProposalModel.tenant_id == tenant_id,
                    ActionProposalModel.id == authorization.proposal_id,
                    ActionProposalModel.is_simulated.is_(False),
                )
            )
            if proposal is None:
                raise PlaybookNotFound("Authorized proposal was not found")
            policy = await session.scalar(
                select(ResponsePolicyVersionModel).where(
                    ResponsePolicyVersionModel.tenant_id == tenant_id,
                    ResponsePolicyVersionModel.id == proposal.policy_version_id,
                )
            )
            incident = await session.scalar(
                select(IncidentModel).where(
                    IncidentModel.tenant_id == tenant_id,
                    IncidentModel.id == proposal.incident_id,
                    IncidentModel.is_simulated.is_(False),
                )
            )
            approval_request = await session.scalar(
                select(ApprovalRequestModel).where(
                    ApprovalRequestModel.tenant_id == tenant_id,
                    ApprovalRequestModel.id == authorization.approval_request_id,
                    ApprovalRequestModel.proposal_id == proposal.id,
                )
            )
            if policy is None or incident is None or approval_request is None:
                raise PlaybookNotFound("Authorized decision material was not found")
            approval_count = int(
                await session.scalar(
                    select(func.count(ApprovalDecisionModel.id)).where(
                        ApprovalDecisionModel.tenant_id == tenant_id,
                        ApprovalDecisionModel.approval_request_id == approval_request.id,
                        ApprovalDecisionModel.decision == "APPROVE",
                    )
                )
                or 0
            )
            self._validate_authorized_state(
                authorization=authorization,
                proposal=proposal,
                policy=policy,
                incident=incident,
                approval_request=approval_request,
                approval_count=approval_count,
                global_kill_switch=settings.automation_kill_switch,
                now=now,
            )
            definitions = list(
                (
                    await session.scalars(
                        select(PlaybookDefinitionModel)
                        .where(
                            PlaybookDefinitionModel.tenant_id == tenant_id,
                            PlaybookDefinitionModel.action_type == proposal.action_type,
                        )
                        .limit(2)
                    )
                ).all()
            )
            if len(definitions) != 1:
                raise PlaybookConflict("Released playbook definition is unavailable or ambiguous")
            definition = definitions[0]
            version = await session.scalar(
                select(PlaybookVersionModel).where(
                    PlaybookVersionModel.tenant_id == tenant_id,
                    PlaybookVersionModel.definition_id == definition.id,
                    PlaybookVersionModel.version == proposal.workflow_version,
                    PlaybookVersionModel.status == "APPROVED",
                )
            )
            if version is None:
                raise PlaybookConflict("Authorized playbook version is not released")
            if version.workflow_code != proposal.workflow_id:
                raise PlaybookConflict("Authorized workflow does not match the released artifact")
            self._validate_definition_governance(
                definition_approval_mode=definition.approval_mode,
                version_impact=version.impact,
                proposal=proposal,
                approval_request=approval_request,
                approval_count=approval_count,
            )
            if (
                version.classification != "LIVE"
                or not settings.playbook_live_enabled
                or not settings.playbook_dispatch_enabled
            ):
                raise PlaybookConflict("LIVE playbook execution requires operational activation")
            bindings = list(
                (
                    await session.scalars(
                        select(AutomationEngineBindingModel)
                        .where(
                            AutomationEngineBindingModel.tenant_id == tenant_id,
                            AutomationEngineBindingModel.playbook_version_id == version.id,
                            AutomationEngineBindingModel.active.is_(True),
                            AutomationEngineBindingModel.sync_status == "SYNCHRONIZED",
                        )
                        .order_by(
                            (AutomationEngineBindingModel.engine_type == "NATIVE").desc(),
                            AutomationEngineBindingModel.created_at.desc(),
                        )
                        .limit(2)
                    )
                ).all()
            )
            if len(bindings) != 1:
                raise PlaybookConflict("Automation binding is unavailable or ambiguous")
            binding = bindings[0]
            if (
                binding.observed_digest != version.artifact_sha256
                or binding.desired_digest != version.artifact_sha256
            ):
                raise PlaybookConflict("Automation binding is unavailable or drifted")
            if binding.engine_type == "NATIVE":
                allowed_tenants = settings.native_enabled_tenant_ids
                if not settings.playbook_native_engine_enabled or (
                    allowed_tenants and str(tenant_id) not in allowed_tenants
                ):
                    raise PlaybookConflict("Native playbook engine is disabled")
            elif binding.engine_type == "N8N":
                if not settings.n8n_enabled:
                    raise PlaybookConflict("n8n automation engine is disabled")
            else:
                raise PlaybookConflict("Automation engine is unavailable")
            portable_inputs: dict[str, object] = {
                "targets": list(proposal.targets),
                "parameters": dict(proposal.parameters),
                "evidence_refs": [str(item) for item in proposal.evidence_refs],
                "incident_id": str(incident.id),
                "incident_version": incident.version,
            }
            if not validate_strict_object(version.input_schema, portable_inputs):
                raise PlaybookConflict("Authorized input does not match the released schema")
            execution = PlaybookExecutionModel(
                tenant_id=tenant_id,
                authorization_id=authorization.id,
                proposal_id=proposal.id,
                incident_id=proposal.incident_id,
                playbook_version_id=version.id,
                binding_id=binding.id,
                origin="AUTHORIZED_RESPONSE",
                idempotency_key=idempotency_key,
                proposal_fingerprint=proposal.fingerprint,
                execution_mode="LIVE",
                status=ExecutionStatus.QUEUED.value,
                inputs={**portable_inputs, "actor_user_id": str(actor_user_id)},
                deadline_at=now + timedelta(seconds=version.timeout_seconds),
            )
            session.add(execution)
            authorization.status = "CONSUMED"
            authorization.consumed_at = now
            await session.flush()
            session.add(
                AuditEventModel(
                    tenant_id=tenant_id,
                    actor_user_id=actor_user_id,
                    action="playbook.execution.queued",
                    resource_type="playbook_execution",
                    resource_id=execution.id,
                    outcome="success",
                    correlation_id=correlation_id,
                    details={
                        "authorization_id": str(authorization.id),
                        "proposal_id": str(proposal.id),
                        "playbook_version_id": str(version.id),
                        "execution_mode": "LIVE",
                    },
                )
            )
            await self._event(
                session,
                execution,
                correlation_id,
                "security.playbook_execution.dispatch_requested",
                {
                    "execution_id": str(execution.id),
                    "binding_id": str(binding.id),
                    "playbook_version_id": str(version.id),
                    "proposal_fingerprint": proposal.fingerprint,
                    "execution_mode": "LIVE",
                },
            )
            return self._response(execution)

    @staticmethod
    def _validate_authorized_state(
        *,
        authorization: ActionAuthorizationModel,
        proposal: ActionProposalModel,
        policy: ResponsePolicyVersionModel,
        incident: IncidentModel,
        approval_request: ApprovalRequestModel,
        approval_count: int,
        global_kill_switch: bool,
        now: datetime,
    ) -> None:
        if authorization.status != "ACTIVE" or authorization.consumed_at is not None:
            raise PlaybookConflict("Authorization is not active")
        if authorization.revoked_at is not None:
            raise PlaybookConflict("Authorization was revoked")
        if authorization.expires_at <= now:
            raise PlaybookConflict("Authorization has expired")
        if proposal.status != "AUTHORIZED":
            raise PlaybookConflict("Proposal is not authorized")
        if proposal.fingerprint != authorization.proposal_fingerprint:
            raise PlaybookConflict("Authorization fingerprint no longer matches")
        if policy.status != "ACTIVE" or policy.kill_switch or global_kill_switch:
            raise PlaybookConflict("Response policy or kill switch blocks execution")
        if (
            incident.version != proposal.incident_version
            or incident.is_simulated != proposal.is_simulated
        ):
            raise PlaybookConflict("Incident material changed after authorization")
        if approval_request.status != "APPROVED" or approval_request.expires_at <= now:
            raise PlaybookConflict("Approval request is no longer valid")
        try:
            current_policy = evaluate_policy(
                impact=ActionImpact(proposal.impact),
                requested_mode=ResponseMode(proposal.requested_mode),
                global_kill_switch=global_kill_switch,
                tenant_kill_switch=policy.kill_switch,
                is_simulated=incident.is_simulated,
            )
        except ValueError as exc:
            raise PlaybookConflict("Authorized policy material is invalid") from exc
        if current_policy.outcome is EvaluationOutcome.DENIED:
            raise PlaybookConflict("Current response policy denies execution")
        if (
            approval_request.required_approvals != current_policy.required_approvals
            or approval_count < current_policy.required_approvals
        ):
            raise PlaybookConflict("Approval quorum no longer satisfies current policy")

    @staticmethod
    def _validate_definition_governance(
        *,
        definition_approval_mode: str | None,
        version_impact: str,
        proposal: ActionProposalModel,
        approval_request: ApprovalRequestModel,
        approval_count: int,
    ) -> None:
        response_modes = {
            "AUTOMATIC": ResponseMode.AUTOMATIC,
            "SINGLE": ResponseMode.HUMAN_APPROVAL,
            "FOUR_EYES": ResponseMode.DUAL_APPROVAL,
        }
        try:
            impact = ActionImpact(version_impact)
            response_mode = response_modes[definition_approval_mode]
        except (KeyError, ValueError) as exc:
            raise PlaybookConflict("Released playbook governance is invalid") from exc
        if proposal.impact != impact.value or proposal.requested_mode != response_mode.value:
            raise PlaybookConflict("Playbook governance changed after authorization")
        expected_approvals = (
            2
            if impact is ActionImpact.HIGH or response_mode is ResponseMode.DUAL_APPROVAL
            else 1
            if response_mode is ResponseMode.HUMAN_APPROVAL
            else 0
        )
        if (
            approval_request.required_approvals != expected_approvals
            or approval_count < expected_approvals
        ):
            raise PlaybookConflict("Approval quorum does not satisfy playbook governance")

    async def list(
        self,
        tenant_id: UUID,
        *,
        incident_id: UUID | None,
        limit: int,
        offset: int,
    ) -> PlaybookExecutionList:
        async with tenant_session(tenant_id) as session:
            query = select(PlaybookExecutionModel).where(
                PlaybookExecutionModel.tenant_id == tenant_id,
                PlaybookExecutionModel.execution_mode == "LIVE",
            )
            count_query = select(func.count(PlaybookExecutionModel.id)).where(
                PlaybookExecutionModel.tenant_id == tenant_id,
                PlaybookExecutionModel.execution_mode == "LIVE",
            )
            if incident_id is not None:
                query = query.where(PlaybookExecutionModel.incident_id == incident_id)
                count_query = count_query.where(PlaybookExecutionModel.incident_id == incident_id)
            items = list(
                (
                    await session.scalars(
                        query.order_by(PlaybookExecutionModel.created_at.desc())
                        .limit(limit)
                        .offset(offset)
                    )
                ).all()
            )
            total = int(await session.scalar(count_query) or 0)
            return PlaybookExecutionList(
                items=[self._response(item) for item in items],
                total=total,
            )

    async def get(self, tenant_id: UUID, execution_id: UUID) -> PlaybookExecutionResponse:
        async with tenant_session(tenant_id) as session:
            execution = await session.scalar(
                select(PlaybookExecutionModel).where(
                    PlaybookExecutionModel.tenant_id == tenant_id,
                    PlaybookExecutionModel.id == execution_id,
                    PlaybookExecutionModel.execution_mode == "LIVE",
                )
            )
            if execution is None:
                raise PlaybookNotFound("Execution was not found")
            return self._response(execution)

    async def cancel(
        self,
        *,
        tenant_id: UUID,
        actor_user_id: UUID,
        execution_id: UUID,
        expected_status: ExecutionStatus,
        correlation_id: UUID,
    ) -> PlaybookExecutionResponse:
        now = datetime.now(UTC)
        async with tenant_session(tenant_id) as session:
            execution = await self._locked_execution(session, tenant_id, execution_id)
            if execution.status != expected_status.value:
                raise PlaybookConflict("Execution status changed; refresh and retry")
            if expected_status is ExecutionStatus.CANCELLED:
                return self._response(execution)
            if expected_status in {
                ExecutionStatus.SUCCEEDED,
                ExecutionStatus.FAILED,
                ExecutionStatus.TIMED_OUT,
            }:
                raise PlaybookConflict("A terminal execution cannot be cancelled")
            binding = await session.scalar(
                select(AutomationEngineBindingModel).where(
                    AutomationEngineBindingModel.tenant_id == tenant_id,
                    AutomationEngineBindingModel.id == execution.binding_id,
                )
            )
            if binding is None:
                raise PlaybookConflict("Execution binding is unavailable")
            if binding.engine_type != "NATIVE":
                raise PlaybookConflict(
                    "External-engine cancellation requires adapter reconciliation"
                )
            active_steps = list(
                (
                    await session.scalars(
                        select(PlaybookStepExecutionModel)
                        .where(
                            PlaybookStepExecutionModel.tenant_id == tenant_id,
                            PlaybookStepExecutionModel.execution_id == execution.id,
                            PlaybookStepExecutionModel.status.in_(
                                ("PENDING", "READY", "CLAIMED", "RUNNING")
                            ),
                        )
                        .with_for_update()
                    )
                ).all()
            )
            registry = ActionRegistry()
            for step in active_steps:
                if step.action_code is None:
                    continue
                try:
                    descriptor = registry.get(
                        step.action_code, step.action_version or ""
                    ).describe()
                except ActionUnavailableError as exc:
                    raise PlaybookConflict(
                        "An active step cannot be verified as safely cancellable"
                    ) from exc
                if not descriptor.cancellable:
                    raise PlaybookConflict("An active step is not safely cancellable")
            validate_transition(expected_status, ExecutionStatus.CANCELLED)
            for step in active_steps:
                step.status = "CANCELLED"
                step.error_code = "PLAYBOOK_CANCELLED"
                step.completed_at = now
            execution.status = ExecutionStatus.CANCELLED.value
            execution.error_code = "PLAYBOOK_CANCELLED"
            execution.completed_at = now
            session.add(
                AuditEventModel(
                    tenant_id=tenant_id,
                    actor_user_id=actor_user_id,
                    action="playbook.execution.cancelled",
                    resource_type="playbook_execution",
                    resource_id=execution.id,
                    outcome="success",
                    correlation_id=correlation_id,
                    details={
                        "engine_type": "NATIVE",
                        "previous_status": expected_status.value,
                        "cancelled_active_steps": len(active_steps),
                    },
                )
            )
            await self._event(
                session,
                execution,
                correlation_id,
                "security.playbook_execution.completed",
                {
                    "tenant_id": str(tenant_id),
                    "resource_id": str(execution.id),
                    "occurred_at": now.isoformat(),
                    "status": ExecutionStatus.CANCELLED.value,
                    "correlation_id": str(correlation_id),
                    "causation_id": None,
                    "engine_type": "NATIVE",
                    "error_code": "PLAYBOOK_CANCELLED",
                },
            )
            return self._response(execution)

    async def claim(
        self,
        *,
        tenant_id: UUID,
        execution_id: UUID,
        payload: ExecutionClaim,
        key_id: str,
        nonce: UUID,
        body_digest: str,
        correlation_id: UUID,
    ) -> PlaybookExecutionResponse:
        async with tenant_session(tenant_id) as session:
            execution = await self._locked_execution(session, tenant_id, execution_id)
            binding = await self._binding(session, tenant_id, execution.binding_id, key_id)
            replay_digest = await self._nonce_digest(session, tenant_id, "DISPATCH", key_id, nonce)
            if replay_digest is not None:
                if (
                    replay_digest == body_digest
                    and execution.status == ExecutionStatus.RUNNING.value
                    and execution.adapter_execution_id == payload.adapter_execution_id
                ):
                    return self._response(execution)
                raise PlaybookSecurityError("Signed request nonce was already used")
            await self._remember_nonce(
                session, tenant_id, binding.id, "DISPATCH", key_id, nonce, body_digest
            )
            if execution.proposal_fingerprint != payload.proposal_fingerprint:
                raise PlaybookSecurityError("Claim fingerprint does not match")
            attempt = await session.scalar(
                select(PlaybookExecutionAttemptModel).where(
                    PlaybookExecutionAttemptModel.tenant_id == tenant_id,
                    PlaybookExecutionAttemptModel.execution_id == execution.id,
                    PlaybookExecutionAttemptModel.dispatch_id == payload.dispatch_id,
                )
            )
            if attempt is None:
                raise PlaybookSecurityError("Claim dispatch is unknown")
            if execution.status not in {
                ExecutionStatus.DISPATCHING.value,
                ExecutionStatus.DISPATCHED.value,
            }:
                if (
                    execution.status == ExecutionStatus.RUNNING.value
                    and execution.adapter_execution_id == payload.adapter_execution_id
                ):
                    return self._response(execution)
                raise PlaybookConflict("Execution is not dispatchable")
            execution.status = ExecutionStatus.RUNNING.value
            execution.claimed_at = datetime.now(UTC)
            execution.adapter_execution_id = payload.adapter_execution_id
            session.add(
                PlaybookExecutionUpdateModel(
                    tenant_id=tenant_id,
                    execution_id=execution.id,
                    adapter_event_id=payload.dispatch_id,
                    sequence=1,
                    status=ExecutionStatus.RUNNING.value,
                    safe_detail="Automation engine claimed the authorized LIVE execution",
                    occurred_at=execution.claimed_at,
                )
            )
            await self._event(
                session,
                execution,
                correlation_id,
                "security.playbook_execution.claimed",
                {"execution_id": str(execution.id), "dispatch_id": str(payload.dispatch_id)},
            )
            return self._response(execution)

    async def update(
        self,
        *,
        tenant_id: UUID,
        execution_id: UUID,
        payload: ExecutionUpdate,
        key_id: str,
        nonce: UUID,
        body_digest: str,
        correlation_id: UUID,
    ) -> PlaybookExecutionResponse:
        async with tenant_session(tenant_id) as session:
            execution = await self._locked_execution(session, tenant_id, execution_id)
            binding = await self._binding(session, tenant_id, execution.binding_id, key_id)
            duplicate = await session.scalar(
                select(PlaybookExecutionUpdateModel).where(
                    PlaybookExecutionUpdateModel.tenant_id == tenant_id,
                    PlaybookExecutionUpdateModel.adapter_event_id == payload.adapter_event_id,
                )
            )
            if duplicate is not None:
                replay_digest = await self._nonce_digest(
                    session, tenant_id, "CALLBACK", key_id, nonce
                )
                if replay_digest == body_digest:
                    return self._response(execution)
                raise PlaybookSecurityError("Callback event was replayed with different material")
            await self._remember_nonce(
                session, tenant_id, binding.id, "CALLBACK", key_id, nonce, body_digest
            )
            target = ExecutionStatus(payload.status)
            validate_transition(ExecutionStatus(execution.status), target)
            if target is ExecutionStatus.SUCCEEDED:
                await self._validate_success_result(session, execution, payload.result)
            update = PlaybookExecutionUpdateModel(
                tenant_id=tenant_id,
                execution_id=execution.id,
                adapter_event_id=payload.adapter_event_id,
                sequence=payload.sequence,
                status=payload.status,
                result=payload.result,
                error_code=payload.error_code,
                safe_detail=payload.safe_detail,
                occurred_at=payload.occurred_at,
            )
            session.add(update)
            execution.status = target.value
            execution.result = payload.result
            execution.error_code = payload.error_code
            if target in {
                ExecutionStatus.SUCCEEDED,
                ExecutionStatus.FAILED,
                ExecutionStatus.TIMED_OUT,
                ExecutionStatus.CANCELLED,
            }:
                execution.completed_at = payload.occurred_at
            await self._event(
                session,
                execution,
                correlation_id,
                "security.playbook_execution.updated",
                {
                    "execution_id": str(execution.id),
                    "adapter_event_id": str(payload.adapter_event_id),
                    "status": target.value,
                    "sequence": payload.sequence,
                },
            )
            return self._response(execution)

    @staticmethod
    async def _locked_execution(
        session: AsyncSession, tenant_id: UUID, execution_id: UUID
    ) -> PlaybookExecutionModel:
        execution = await session.scalar(
            select(PlaybookExecutionModel)
            .where(
                PlaybookExecutionModel.tenant_id == tenant_id,
                PlaybookExecutionModel.id == execution_id,
                PlaybookExecutionModel.execution_mode == "LIVE",
            )
            .with_for_update()
        )
        if execution is None:
            raise PlaybookNotFound("Execution was not found")
        return execution

    @staticmethod
    async def _binding(
        session: AsyncSession, tenant_id: UUID, binding_id: UUID, key_id: str
    ) -> AutomationEngineBindingModel:
        binding = await session.scalar(
            select(AutomationEngineBindingModel).where(
                AutomationEngineBindingModel.tenant_id == tenant_id,
                AutomationEngineBindingModel.id == binding_id,
                AutomationEngineBindingModel.active.is_(True),
            )
        )
        if binding is None or binding.key_id != key_id:
            raise PlaybookSecurityError("Automation binding is not trusted")
        return binding

    @staticmethod
    async def _validate_success_result(
        session: AsyncSession,
        execution: PlaybookExecutionModel,
        result: dict[str, object] | None,
    ) -> None:
        version = await session.scalar(
            select(PlaybookVersionModel).where(
                PlaybookVersionModel.tenant_id == execution.tenant_id,
                PlaybookVersionModel.id == execution.playbook_version_id,
            )
        )
        if version is None:
            raise PlaybookSecurityError("Released playbook version is unavailable")
        if (
            execution.execution_mode != "LIVE"
            or result is None
            or not validate_strict_object(version.result_schema, result)
            or result.get("effect") != "applied"
            or result.get("workflow_code") != version.workflow_code
        ):
            raise PlaybookSecurityError("LIVE result does not match its released schema")
        try:
            artifact = PortablePlaybookV1.model_validate(version.portable_artifact)
        except ValueError as exc:
            raise PlaybookSecurityError("Released playbook artifact is invalid") from exc
        receipts = result.get("step_receipts")
        if not isinstance(receipts, dict) or set(receipts) != {step.id for step in artifact.steps}:
            raise PlaybookSecurityError("LIVE result receipts do not match released steps")

    @staticmethod
    async def _nonce_digest(
        session: AsyncSession, tenant_id: UUID, direction: str, key_id: str, nonce: UUID
    ) -> str | None:
        value = await session.scalar(
            select(AutomationReplayNonceModel.body_sha256).where(
                AutomationReplayNonceModel.tenant_id == tenant_id,
                AutomationReplayNonceModel.direction == direction,
                AutomationReplayNonceModel.key_id == key_id,
                AutomationReplayNonceModel.nonce == nonce,
            )
        )
        return str(value) if value is not None else None

    @staticmethod
    async def _remember_nonce(
        session: AsyncSession,
        tenant_id: UUID,
        binding_id: UUID,
        direction: str,
        key_id: str,
        nonce: UUID,
        digest: str,
    ) -> None:
        replay = await session.scalar(
            select(AutomationReplayNonceModel.id).where(
                AutomationReplayNonceModel.tenant_id == tenant_id,
                AutomationReplayNonceModel.direction == direction,
                AutomationReplayNonceModel.key_id == key_id,
                AutomationReplayNonceModel.nonce == nonce,
            )
        )
        if replay is not None:
            raise PlaybookSecurityError("Signed request nonce was already used")
        session.add(
            AutomationReplayNonceModel(
                tenant_id=tenant_id,
                binding_id=binding_id,
                direction=direction,
                key_id=key_id,
                nonce=nonce,
                body_sha256=digest,
                expires_at=datetime.now(UTC) + timedelta(minutes=10),
            )
        )

    @staticmethod
    async def _event(
        session: AsyncSession,
        execution: PlaybookExecutionModel,
        correlation_id: UUID,
        name: str,
        payload: dict[str, object],
    ) -> None:
        store = SqlEventStore(
            session_factory=SessionFactory,
            max_payload_bytes=get_settings().event_max_payload_bytes,
        )
        await store.recorder(session).add(
            DomainEvent.create(
                event_name=name,
                tenant_id=execution.tenant_id,
                aggregate_type="playbook_execution",
                aggregate_id=execution.id,
                correlation_id=correlation_id,
                producer="playbooks",
                payload=payload,
            )
        )

    @staticmethod
    def _response(execution: PlaybookExecutionModel) -> PlaybookExecutionResponse:
        return PlaybookExecutionResponse(
            id=execution.id,
            authorization_id=execution.authorization_id,
            source_event_id=execution.source_event_id,
            proposal_id=execution.proposal_id,
            incident_id=execution.incident_id,
            playbook_version_id=execution.playbook_version_id,
            origin=execution.origin,
            execution_mode=execution.execution_mode,
            status=execution.status,
            inputs=dict(execution.inputs),
            result=dict(execution.result) if execution.result is not None else None,
            error_code=execution.error_code,
            adapter_execution_id=execution.adapter_execution_id,
            claimed_at=execution.claimed_at,
            deadline_at=execution.deadline_at,
            completed_at=execution.completed_at,
            created_at=execution.created_at,
        )
