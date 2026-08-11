from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from cyrvanta.modules.decision.infrastructure.models import (
    ActionAuthorizationModel,
    ActionProposalModel,
)
from cyrvanta.modules.identity.infrastructure.models import AuditEventModel
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
        async with tenant_session(tenant_id) as session:
            existing = await session.scalar(
                select(PlaybookExecutionModel).where(
                    PlaybookExecutionModel.tenant_id == tenant_id,
                    PlaybookExecutionModel.idempotency_key == idempotency_key,
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
            if authorization.status != "ACTIVE":
                raise PlaybookConflict("Authorization is not active")
            if authorization.expires_at <= now:
                raise PlaybookConflict("Authorization has expired")
            proposal = await session.scalar(
                select(ActionProposalModel).where(
                    ActionProposalModel.tenant_id == tenant_id,
                    ActionProposalModel.id == authorization.proposal_id,
                )
            )
            if proposal is None:
                raise PlaybookNotFound("Authorized proposal was not found")
            if proposal.status != "AUTHORIZED":
                raise PlaybookConflict("Proposal is not authorized")
            if proposal.fingerprint != authorization.proposal_fingerprint:
                raise PlaybookConflict("Authorization fingerprint no longer matches")
            definition = await session.scalar(
                select(PlaybookDefinitionModel).where(
                    PlaybookDefinitionModel.tenant_id == tenant_id,
                    PlaybookDefinitionModel.action_type == proposal.action_type,
                )
            )
            if definition is None:
                raise PlaybookConflict("No released playbook matches the authorized action")
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
            if version.classification != "SYNTHETIC":
                raise PlaybookConflict("LIVE playbook execution requires an operational approval")
            binding = await session.scalar(
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
            )
            if binding is None or binding.observed_digest != version.artifact_sha256:
                raise PlaybookConflict("Automation binding is unavailable or drifted")
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
                execution_mode="SYNTHETIC",
                status=ExecutionStatus.QUEUED.value,
                inputs={
                    "targets": list(proposal.targets),
                    "parameters": dict(proposal.parameters),
                    "evidence_refs": list(proposal.evidence_refs),
                },
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
                        "execution_mode": "SYNTHETIC",
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
                    "execution_mode": "SYNTHETIC",
                },
            )
            return self._response(execution)

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
                PlaybookExecutionModel.tenant_id == tenant_id
            )
            count_query = select(func.count(PlaybookExecutionModel.id)).where(
                PlaybookExecutionModel.tenant_id == tenant_id
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
            binding = await self._binding(
                session, tenant_id, execution.binding_id, key_id
            )
            replay_digest = await self._nonce_digest(
                session, tenant_id, "DISPATCH", key_id, nonce
            )
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
                    safe_detail="Automation engine claimed the authorized synthetic execution",
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
            binding = await self._binding(
                session, tenant_id, execution.binding_id, key_id
            )
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
        if execution.execution_mode == "SYNTHETIC":
            if version.workflow_code == "simulate-user-block":
                if result != {
                    "execution_mode": "demo",
                    "action": "block_user",
                    "result": "simulated_success",
                }:
                    raise PlaybookSecurityError(
                        "Simulated user block result does not match its exact schema"
                    )
                return
            if result is None or set(result) != {
                "simulated",
                "effect",
                "workflow_code",
            }:
                raise PlaybookSecurityError("Synthetic result does not match its schema")
            if (
                result["simulated"] is not True
                or result["effect"] != "none"
                or result["workflow_code"] != version.workflow_code
            ):
                raise PlaybookSecurityError("Synthetic result material is invalid")

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
