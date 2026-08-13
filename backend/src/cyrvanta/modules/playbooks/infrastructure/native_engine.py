from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, text

from cyrvanta.modules.identity.infrastructure.models import AuditEventModel
from cyrvanta.modules.playbooks.application.engine_ports import EngineContext
from cyrvanta.modules.playbooks.application.portable import (
    ActionStep,
    ConditionExpression,
    ConditionStep,
    PortablePlaybookV1,
    portable_playbook_sha256,
)
from cyrvanta.modules.playbooks.domain.models import ExecutionStatus
from cyrvanta.modules.playbooks.infrastructure.action_registry import (
    ActionRegistry,
    ActionUnavailableError,
)
from cyrvanta.modules.playbooks.infrastructure.models import (
    AutomationEngineBindingModel,
    NativeActionBindingModel,
    PlaybookExecutionModel,
    PlaybookStepAttemptModel,
    PlaybookStepAttemptOutcomeModel,
    PlaybookStepExecutionModel,
    PlaybookVersionModel,
)
from cyrvanta.shared.config import Settings
from cyrvanta.shared.database import SessionFactory, engine, tenant_session
from cyrvanta.shared.domain.events import DomainEvent
from cyrvanta.shared.infrastructure.event_store import SqlEventStore

TERMINAL_STEP_STATUSES = {"SUCCEEDED", "FAILED", "SKIPPED", "CANCELLED", "UNKNOWN"}


class NativeEngineRejected(RuntimeError):
    def __init__(self, error_code: str) -> None:
        super().__init__(error_code)
        self.error_code = error_code


class NativePlaybookDispatcher:
    def __init__(self, settings: Settings, registry: ActionRegistry | None = None) -> None:
        self.settings = settings
        self.registry = registry or ActionRegistry()
        self.store = SqlEventStore(SessionFactory, settings.event_max_payload_bytes)

    async def dispatch(
        self,
        tenant_id: UUID,
        execution_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> bool | None:
        async with self._execution_lease(tenant_id, execution_id) as acquired:
            if not acquired:
                return None
            return await self._dispatch_exclusively(
                tenant_id,
                execution_id,
                correlation_id,
                causation_id,
            )

    async def _dispatch_exclusively(
        self,
        tenant_id: UUID,
        execution_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None,
    ) -> bool | None:
        try:
            artifact, deadline, workflow_code, execution_inputs = await self._claim_execution(
                tenant_id, execution_id, correlation_id, causation_id
            )
        except NativeEngineRejected as exc:
            await self._reject_execution(
                tenant_id, execution_id, correlation_id, causation_id, exc.error_code
            )
            return False
        if artifact is None:
            return None

        context = EngineContext(
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            deadline=deadline,
        )
        outcomes, outputs = await self._load_progress(tenant_id, execution_id)
        failed = "FAILURE" in outcomes.values()
        try:
            for step in self._topological_steps(artifact):
                if step.id in outcomes:
                    continue
                if not self._is_selected(artifact, step.id, outcomes):
                    await self._skip_step(context, execution_id, step)
                    outcomes[step.id] = "SKIPPED"
                    continue
                if datetime.now(UTC) >= deadline:
                    raise NativeEngineRejected("PLAYBOOK_DEADLINE_EXCEEDED")
                if isinstance(step, ConditionStep):
                    matched = self._evaluate(
                        step.expression, artifact_input=execution_inputs, outputs=outputs
                    )
                    await self._complete_condition(context, execution_id, step, matched)
                    outcomes[step.id] = "TRUE" if matched else "FALSE"
                    outputs[step.id] = {"matched": matched}
                    continue
                result = await self._execute_action(context, execution_id, step)
                outputs[step.id] = result
                succeeded = bool(result.get("succeeded"))
                outcomes[step.id] = "SUCCESS" if succeeded else "FAILURE"
                failed = failed or not succeeded
        except NativeEngineRejected as exc:
            await self._complete_execution(
                context,
                execution_id,
                workflow_code,
                status=ExecutionStatus.TIMED_OUT.value
                if exc.error_code == "PLAYBOOK_DEADLINE_EXCEEDED"
                else ExecutionStatus.FAILED.value,
                error_code=exc.error_code,
            )
            return False

        await self._complete_execution(
            context,
            execution_id,
            workflow_code,
            status=ExecutionStatus.FAILED.value if failed else ExecutionStatus.SUCCEEDED.value,
            error_code="PLAYBOOK_ACTION_FAILED" if failed else None,
        )
        return not failed

    @asynccontextmanager
    async def _execution_lease(
        self, tenant_id: UUID, execution_id: UUID
    ) -> AsyncIterator[bool]:
        lock_key = self._execution_lock_key(tenant_id, execution_id)
        async with engine.connect() as connection, connection.begin():
            acquired = bool(
                await connection.scalar(
                    text("SELECT pg_try_advisory_xact_lock(:lock_key)"),
                    {"lock_key": lock_key},
                )
            )
            yield acquired

    @staticmethod
    def _execution_lock_key(tenant_id: UUID, execution_id: UUID) -> int:
        digest = hashlib.sha256(f"{tenant_id}:{execution_id}".encode()).digest()
        return int.from_bytes(digest[:8], byteorder="big", signed=True)

    async def _load_progress(
        self, tenant_id: UUID, execution_id: UUID
    ) -> tuple[dict[str, str], dict[str, dict[str, object]]]:
        async with tenant_session(tenant_id) as session:
            rows = list(
                (
                    await session.scalars(
                        select(PlaybookStepExecutionModel).where(
                            PlaybookStepExecutionModel.tenant_id == tenant_id,
                            PlaybookStepExecutionModel.execution_id == execution_id,
                        )
                    )
                ).all()
            )
        return self._progress_from_rows(rows)

    @staticmethod
    def _progress_from_rows(
        rows: list[PlaybookStepExecutionModel],
    ) -> tuple[dict[str, str], dict[str, dict[str, object]]]:
        outcomes: dict[str, str] = {}
        outputs: dict[str, dict[str, object]] = {}
        for row in rows:
            if row.result is not None:
                outputs[row.step_id] = dict(row.result)
            if row.status == "SUCCEEDED":
                if row.step_type == "ACTION":
                    outcomes[row.step_id] = "SUCCESS"
                else:
                    matched = bool((row.result or {}).get("matched"))
                    outcomes[row.step_id] = "TRUE" if matched else "FALSE"
            elif row.status == "FAILED":
                outcomes[row.step_id] = "FAILURE"
            elif row.status == "SKIPPED":
                outcomes[row.step_id] = "SKIPPED"
            elif row.status in {"CANCELLED", "UNKNOWN"}:
                raise NativeEngineRejected("PLAYBOOK_STATE_CONFLICT")
        return outcomes, outputs

    async def _claim_execution(
        self,
        tenant_id: UUID,
        execution_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None,
    ) -> tuple[PortablePlaybookV1 | None, datetime, str, dict[str, object]]:
        now = datetime.now(UTC)
        async with tenant_session(tenant_id) as session:
            execution = await session.scalar(
                select(PlaybookExecutionModel)
                .where(
                    PlaybookExecutionModel.tenant_id == tenant_id,
                    PlaybookExecutionModel.id == execution_id,
                )
                .with_for_update(skip_locked=True)
            )
            if execution is None or execution.status not in {
                ExecutionStatus.QUEUED.value,
                ExecutionStatus.RUNNING.value,
            }:
                return None, now, "", {}
            recovering = execution.status == ExecutionStatus.RUNNING.value
            self._guard_global(tenant_id, execution)
            binding = await session.scalar(
                select(AutomationEngineBindingModel).where(
                    AutomationEngineBindingModel.tenant_id == tenant_id,
                    AutomationEngineBindingModel.id == execution.binding_id,
                    AutomationEngineBindingModel.engine_type == "NATIVE",
                    AutomationEngineBindingModel.active.is_(True),
                    AutomationEngineBindingModel.sync_status == "SYNCHRONIZED",
                )
            )
            version = await session.scalar(
                select(PlaybookVersionModel).where(
                    PlaybookVersionModel.tenant_id == tenant_id,
                    PlaybookVersionModel.id == execution.playbook_version_id,
                    PlaybookVersionModel.status == "APPROVED",
                )
            )
            if binding is None or version is None:
                raise NativeEngineRejected("PLAYBOOK_BINDING_UNAVAILABLE")
            if (
                binding.observed_digest != version.artifact_sha256
                or binding.desired_digest != version.artifact_sha256
            ):
                raise NativeEngineRejected("PLAYBOOK_BINDING_DRIFTED")
            if (
                version.portable_artifact is None
                or version.portable_schema_version != "1.0"
                or version.validated_sha256 != version.artifact_sha256
                or version.validated_at is None
            ):
                raise NativeEngineRejected("PLAYBOOK_INVALID")
            artifact = PortablePlaybookV1.model_validate(version.portable_artifact)
            if portable_playbook_sha256(artifact) != version.artifact_sha256:
                raise NativeEngineRejected("PLAYBOOK_DIGEST_MISMATCH")
            await self._validate_action_bindings(session, tenant_id, artifact)
            if recovering:
                persisted_step_ids = set(
                    (
                        await session.scalars(
                            select(PlaybookStepExecutionModel.step_id).where(
                                PlaybookStepExecutionModel.tenant_id == tenant_id,
                                PlaybookStepExecutionModel.execution_id == execution.id,
                            )
                        )
                    ).all()
                )
                if persisted_step_ids != {step.id for step in artifact.steps}:
                    raise NativeEngineRejected("PLAYBOOK_STATE_CONFLICT")
                session.add(
                    AuditEventModel(
                        tenant_id=tenant_id,
                        actor_user_id=None,
                        action="playbook.native.execution.recovered",
                        resource_type="playbook_execution",
                        resource_id=execution.id,
                        outcome="success",
                        correlation_id=correlation_id,
                        details={"engine_type": "NATIVE"},
                    )
                )
            else:
                execution.status = ExecutionStatus.RUNNING.value
                execution.claimed_at = now
                execution.adapter_execution_id = f"native-{execution.id}"
                for step in artifact.steps:
                    step_input = self._step_input(execution.inputs, step)
                    session.add(
                        PlaybookStepExecutionModel(
                            tenant_id=tenant_id,
                            execution_id=execution.id,
                            step_id=step.id,
                            step_type=step.type,
                            action_code=(step.action if isinstance(step, ActionStep) else None),
                            action_version=(
                                step.action_version if isinstance(step, ActionStep) else None
                            ),
                            status="PENDING",
                            input_sha256=self._digest(step_input),
                        )
                    )
                session.add(
                    AuditEventModel(
                        tenant_id=tenant_id,
                        actor_user_id=None,
                        action="playbook.native.execution.claimed",
                        resource_type="playbook_execution",
                        resource_id=execution.id,
                        outcome="success",
                        correlation_id=correlation_id,
                        details={"engine_type": "NATIVE", "mode": "SIMULATED"},
                    )
                )
                await self._event(
                    session,
                    context=EngineContext(
                        tenant_id, correlation_id, causation_id, execution.deadline_at
                    ),
                    name="security.native_playbook.dispatch_requested",
                    resource_type="playbook_execution",
                    resource_id=execution.id,
                    status="RUNNING",
                    extra={"engine_type": "NATIVE"},
                )
            return (
                artifact,
                execution.deadline_at,
                version.workflow_code,
                dict(execution.inputs),
            )

    def _guard_global(self, tenant_id: UUID, execution: PlaybookExecutionModel) -> None:
        if self.settings.automation_kill_switch or not self.settings.playbook_native_engine_enabled:
            raise NativeEngineRejected("PLAYBOOK_ENGINE_DISABLED")
        allowed = self.settings.native_enabled_tenant_ids
        if allowed and str(tenant_id) not in allowed:
            raise NativeEngineRejected("PLAYBOOK_ENGINE_DISABLED")
        if execution.execution_mode != "SYNTHETIC":
            raise NativeEngineRejected("PLAYBOOK_LIVE_DISABLED")
        if datetime.now(UTC) >= execution.deadline_at:
            raise NativeEngineRejected("PLAYBOOK_DEADLINE_EXCEEDED")

    async def _validate_action_bindings(
        self, session: Any, tenant_id: UUID, artifact: PortablePlaybookV1
    ) -> None:
        for step in artifact.steps:
            if not isinstance(step, ActionStep):
                continue
            try:
                connector = self.registry.get(step.action, step.action_version)
            except ActionUnavailableError as exc:
                raise NativeEngineRejected("PLAYBOOK_ACTION_UNAVAILABLE") from exc
            binding = await session.scalar(
                select(NativeActionBindingModel).where(
                    NativeActionBindingModel.action_code == step.action,
                    NativeActionBindingModel.tenant_id == tenant_id,
                    NativeActionBindingModel.action_version == step.action_version,
                    NativeActionBindingModel.connector_type == "SIMULATED",
                    NativeActionBindingModel.active.is_(True),
                    NativeActionBindingModel.last_verified_at.is_not(None),
                )
            )
            if binding is None or binding.credential_key_id is not None:
                raise NativeEngineRejected("PLAYBOOK_ACTION_UNAVAILABLE")
            if binding.configuration_sha256 != self._digest(binding.configuration):
                raise NativeEngineRejected("PLAYBOOK_ACTION_CONFIG_INVALID")
            validation = connector.validate_configuration(binding.configuration)
            if not validation.valid:
                raise NativeEngineRejected(validation.error_codes[0])
            if step.credential_aliases:
                raise NativeEngineRejected("PLAYBOOK_CREDENTIAL_UNAVAILABLE")

    async def _execute_action(
        self, context: EngineContext, execution_id: UUID, step: ActionStep
    ) -> dict[str, object]:
        now = datetime.now(UTC)
        step_input: dict[str, object]
        async with tenant_session(context.tenant_id) as session:
            execution = await self._active_execution(
                session, context.tenant_id, execution_id
            )
            self._guard_global(context.tenant_id, execution)
            step_row = await self._locked_step(
                session, context.tenant_id, execution_id, step.id
            )
            binding = await session.scalar(
                select(NativeActionBindingModel).where(
                    NativeActionBindingModel.action_code == step.action,
                    NativeActionBindingModel.tenant_id == context.tenant_id,
                    NativeActionBindingModel.action_version == step.action_version,
                    NativeActionBindingModel.connector_type == "SIMULATED",
                    NativeActionBindingModel.active.is_(True),
                    NativeActionBindingModel.last_verified_at.is_not(None),
                )
            )
            if binding is None:
                raise NativeEngineRejected("PLAYBOOK_ACTION_UNAVAILABLE")
            step_input = self._step_input(execution.inputs, step)
            input_digest = self._digest(step_input)
            attempt = await session.scalar(
                select(PlaybookStepAttemptModel).where(
                    PlaybookStepAttemptModel.tenant_id == context.tenant_id,
                    PlaybookStepAttemptModel.step_execution_id == step_row.id,
                    PlaybookStepAttemptModel.attempt_number == 1,
                )
            )
            if attempt is not None:
                outcome_exists = await session.scalar(
                    select(PlaybookStepAttemptOutcomeModel.id).where(
                        PlaybookStepAttemptOutcomeModel.tenant_id == context.tenant_id,
                        PlaybookStepAttemptOutcomeModel.attempt_id == attempt.id,
                    )
                )
                self._validate_recoverable_attempt(
                    attempt,
                    outcome_exists=outcome_exists,
                    input_digest=input_digest,
                )
            else:
                attempt = PlaybookStepAttemptModel(
                    tenant_id=context.tenant_id,
                    step_execution_id=step_row.id,
                    attempt_number=1,
                    claim_id=uuid4(),
                    idempotency_key=f"native:{execution_id}:{step.id}:1",
                    input_sha256=input_digest,
                    started_at=now,
                    deadline_at=min(context.deadline, now + timedelta(seconds=30)),
                )
                session.add(attempt)
                step_row.status = "CLAIMED"
                step_row.claimed_at = now
                await session.flush()
                session.add(
                    AuditEventModel(
                        tenant_id=context.tenant_id,
                        actor_user_id=None,
                        action="playbook.native.step.claimed",
                        resource_type="playbook_step_execution",
                        resource_id=step_row.id,
                        outcome="success",
                        correlation_id=context.correlation_id,
                        details={
                            "execution_id": str(execution_id),
                            "step_id": step.id,
                            "action_code": step.action,
                            "action_version": step.action_version,
                        },
                    )
                )
                await self._event(
                    session,
                    context=context,
                    name="security.playbook_step.claimed",
                    resource_type="playbook_step_execution",
                    resource_id=step_row.id,
                    status="CLAIMED",
                    extra={
                        "execution_id": str(execution_id),
                        "step_id": step.id,
                        "action_code": step.action,
                        "action_version": step.action_version,
                    },
                )
            attempt_id = attempt.id
            idempotency_key = attempt.idempotency_key

        connector = self.registry.get(step.action, step.action_version)
        result = await connector.execute(context, step_input, idempotency_key, None)
        completed_at = datetime.now(UTC)
        status = "SUCCEEDED" if result.succeeded else "FAILED"
        late_after_cancel = False
        async with tenant_session(context.tenant_id) as session:
            step_row = await session.scalar(
                select(PlaybookStepExecutionModel)
                .where(
                    PlaybookStepExecutionModel.tenant_id == context.tenant_id,
                    PlaybookStepExecutionModel.execution_id == execution_id,
                    PlaybookStepExecutionModel.step_id == step.id,
                )
                .with_for_update()
            )
            if step_row is None:
                raise NativeEngineRejected("PLAYBOOK_NOT_FOUND")
            if step_row.status in TERMINAL_STEP_STATUSES - {"CANCELLED"}:
                raise NativeEngineRejected("PLAYBOOK_STATE_CONFLICT")
            session.add(
                PlaybookStepAttemptOutcomeModel(
                    tenant_id=context.tenant_id,
                    attempt_id=attempt_id,
                    outcome_event_id=uuid4(),
                    sequence=1,
                    status=status,
                    result=result.output,
                    result_sha256=self._digest(result.output),
                    error_code=result.error_code,
                    safe_detail=result.safe_detail,
                    occurred_at=completed_at,
                )
            )
            late_after_cancel = step_row.status == "CANCELLED"
            if late_after_cancel:
                session.add(
                    AuditEventModel(
                        tenant_id=context.tenant_id,
                        actor_user_id=None,
                        action="playbook.native.step.late_outcome",
                        resource_type="playbook_step_execution",
                        resource_id=step_row.id,
                        outcome="success",
                        correlation_id=context.correlation_id,
                        details={
                            "execution_id": str(execution_id),
                            "step_id": step.id,
                            "outcome_status": status,
                        },
                    )
                )
                await self._event(
                    session,
                    context=context,
                    name="security.playbook_step.completed",
                    resource_type="playbook_step_execution",
                    resource_id=step_row.id,
                    status=status,
                    extra={
                        "execution_id": str(execution_id),
                        "step_id": step.id,
                        "action_code": step.action,
                        "action_version": step.action_version,
                        "sequence": 1,
                        "error_code": result.error_code,
                    },
                )
            else:
                step_row.status = status
                step_row.result = result.output
                step_row.error_code = result.error_code
                step_row.completed_at = completed_at
                await self._record_step_completion(
                    session,
                    context,
                    execution_id,
                    step_row.id,
                    step.id,
                    status,
                    result.error_code,
                )
        if late_after_cancel:
            raise NativeEngineRejected("PLAYBOOK_CANCELLED")
        return {**result.output, "succeeded": result.succeeded}

    @staticmethod
    def _validate_recoverable_attempt(
        attempt: PlaybookStepAttemptModel,
        *,
        outcome_exists: UUID | None,
        input_digest: str,
    ) -> None:
        if outcome_exists is not None or attempt.input_sha256 != input_digest:
            raise NativeEngineRejected("PLAYBOOK_STATE_CONFLICT")

    async def _complete_condition(
        self,
        context: EngineContext,
        execution_id: UUID,
        step: ConditionStep,
        matched: bool,
    ) -> None:
        async with tenant_session(context.tenant_id) as session:
            row = await self._locked_step(
                session, context.tenant_id, execution_id, step.id
            )
            row.status = "SUCCEEDED"
            row.result = {"matched": matched}
            row.completed_at = datetime.now(UTC)
            await self._record_step_completion(
                session, context, execution_id, row.id, step.id, "SUCCEEDED", None
            )

    async def _skip_step(
        self,
        context: EngineContext,
        execution_id: UUID,
        step: ActionStep | ConditionStep,
    ) -> None:
        async with tenant_session(context.tenant_id) as session:
            row = await self._locked_step(
                session, context.tenant_id, execution_id, step.id
            )
            row.status = "SKIPPED"
            row.completed_at = datetime.now(UTC)
            await self._record_step_completion(
                session, context, execution_id, row.id, step.id, "SKIPPED", None
            )

    async def _complete_execution(
        self,
        context: EngineContext,
        execution_id: UUID,
        workflow_code: str,
        *,
        status: str,
        error_code: str | None,
    ) -> None:
        async with tenant_session(context.tenant_id) as session:
            execution = await self._active_execution(
                session, context.tenant_id, execution_id, allow_terminal=True
            )
            if execution.status in {
                ExecutionStatus.SUCCEEDED.value,
                ExecutionStatus.FAILED.value,
                ExecutionStatus.TIMED_OUT.value,
                ExecutionStatus.CANCELLED.value,
            }:
                return
            execution.status = status
            execution.error_code = error_code
            execution.completed_at = datetime.now(UTC)
            if status == ExecutionStatus.SUCCEEDED.value:
                execution.result = {
                    "simulated": True,
                    "effect": "none",
                    "workflow_code": workflow_code,
                }
            session.add(
                AuditEventModel(
                    tenant_id=context.tenant_id,
                    actor_user_id=None,
                    action="playbook.native.execution.completed",
                    resource_type="playbook_execution",
                    resource_id=execution_id,
                    outcome="success" if status == ExecutionStatus.SUCCEEDED.value else "failure",
                    correlation_id=context.correlation_id,
                    details={"status": status, "error_code": error_code},
                )
            )
            await self._event(
                session,
                context=context,
                name="security.playbook_execution.completed",
                resource_type="playbook_execution",
                resource_id=execution_id,
                status=status,
                extra={"engine_type": "NATIVE", "error_code": error_code},
            )

    async def _reject_execution(
        self,
        tenant_id: UUID,
        execution_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None,
        error_code: str,
    ) -> None:
        async with tenant_session(tenant_id) as session:
            execution = await session.scalar(
                select(PlaybookExecutionModel)
                .where(
                    PlaybookExecutionModel.tenant_id == tenant_id,
                    PlaybookExecutionModel.id == execution_id,
                )
                .with_for_update()
            )
            if execution is None or execution.status not in {
                ExecutionStatus.QUEUED.value,
                ExecutionStatus.RUNNING.value,
            }:
                return
            now = datetime.now(UTC)
            terminal_status = (
                ExecutionStatus.TIMED_OUT.value
                if error_code == "PLAYBOOK_DEADLINE_EXCEEDED"
                else ExecutionStatus.FAILED.value
            )
            execution.status = terminal_status
            execution.error_code = error_code
            execution.completed_at = now
            active_steps = list(
                (
                    await session.scalars(
                        select(PlaybookStepExecutionModel).where(
                            PlaybookStepExecutionModel.tenant_id == tenant_id,
                            PlaybookStepExecutionModel.execution_id == execution_id,
                            PlaybookStepExecutionModel.status.in_(
                                ("PENDING", "READY", "CLAIMED", "RUNNING")
                            ),
                        )
                    )
                ).all()
            )
            for step in active_steps:
                step.status = "UNKNOWN" if error_code == "PLAYBOOK_STATE_CONFLICT" else "FAILED"
                step.error_code = error_code
                step.completed_at = now
            context = EngineContext(tenant_id, correlation_id, causation_id, execution.deadline_at)
            session.add(
                AuditEventModel(
                    tenant_id=tenant_id,
                    actor_user_id=None,
                    action="playbook.native.execution.rejected",
                    resource_type="playbook_execution",
                    resource_id=execution_id,
                    outcome="failure",
                    correlation_id=correlation_id,
                    details={"error_code": error_code},
                )
            )
            await self._event(
                session,
                context=context,
                name="security.playbook_execution.completed",
                resource_type="playbook_execution",
                resource_id=execution_id,
                status=terminal_status,
                extra={"engine_type": "NATIVE", "error_code": error_code},
            )

    async def _record_step_completion(
        self,
        session: Any,
        context: EngineContext,
        execution_id: UUID,
        row_id: UUID,
        step_id: str,
        status: str,
        error_code: str | None,
    ) -> None:
        session.add(
            AuditEventModel(
                tenant_id=context.tenant_id,
                actor_user_id=None,
                action="playbook.native.step.completed",
                resource_type="playbook_step_execution",
                resource_id=row_id,
                outcome="success" if status in {"SUCCEEDED", "SKIPPED"} else "failure",
                correlation_id=context.correlation_id,
                details={
                    "execution_id": str(execution_id),
                    "step_id": step_id,
                    "status": status,
                    "error_code": error_code,
                },
            )
        )
        await self._event(
            session,
            context=context,
            name="security.playbook_step.completed",
            resource_type="playbook_step_execution",
            resource_id=row_id,
            status=status,
            extra={
                "execution_id": str(execution_id),
                "step_id": step_id,
                "error_code": error_code,
            },
        )

    async def _event(
        self,
        session: Any,
        *,
        context: EngineContext,
        name: str,
        resource_type: str,
        resource_id: UUID,
        status: str,
        extra: dict[str, object],
    ) -> None:
        occurred_at = datetime.now(UTC)
        await self.store.recorder(session).add(
            DomainEvent.create(
                event_name=name,
                tenant_id=context.tenant_id,
                aggregate_type=resource_type,
                aggregate_id=resource_id,
                correlation_id=context.correlation_id,
                causation_id=context.causation_id,
                producer="playbooks",
                payload={
                    "tenant_id": str(context.tenant_id),
                    "resource_id": str(resource_id),
                    "occurred_at": occurred_at.isoformat(),
                    "status": status,
                    "correlation_id": str(context.correlation_id),
                    "causation_id": (str(context.causation_id) if context.causation_id else None),
                    **extra,
                },
                occurred_at=occurred_at,
            )
        )

    @staticmethod
    async def _active_execution(
        session: Any,
        tenant_id: UUID,
        execution_id: UUID,
        *,
        allow_terminal: bool = False,
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
            raise NativeEngineRejected("PLAYBOOK_NOT_FOUND")
        if not allow_terminal and execution.status != ExecutionStatus.RUNNING.value:
            raise NativeEngineRejected("PLAYBOOK_STATE_CONFLICT")
        return execution

    @staticmethod
    async def _locked_step(
        session: Any, tenant_id: UUID, execution_id: UUID, step_id: str
    ) -> Any:
        row = await session.scalar(
            select(PlaybookStepExecutionModel)
            .where(
                PlaybookStepExecutionModel.tenant_id == tenant_id,
                PlaybookStepExecutionModel.execution_id == execution_id,
                PlaybookStepExecutionModel.step_id == step_id,
            )
            .with_for_update()
        )
        if row is None or row.status in TERMINAL_STEP_STATUSES:
            raise NativeEngineRejected("PLAYBOOK_STATE_CONFLICT")
        return row

    @staticmethod
    def _step_input(
        execution_inputs: dict[str, object], step: ActionStep | ConditionStep
    ) -> dict[str, object]:
        if isinstance(step, ActionStep):
            return {"inputs": execution_inputs, "parameters": step.parameters}
        return {"expression": step.expression.model_dump(mode="json", exclude_none=True)}

    @staticmethod
    def _digest(value: object) -> str:
        material = json.dumps(
            value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).encode()
        return hashlib.sha256(material).hexdigest()

    @staticmethod
    def _topological_steps(
        artifact: PortablePlaybookV1,
    ) -> list[ActionStep | ConditionStep]:
        by_id = {step.id: step for step in artifact.steps}
        outgoing: dict[str, list[str]] = {step.id: [] for step in artifact.steps}
        indegree = dict.fromkeys(by_id, 0)
        for edge in artifact.edges:
            outgoing[edge.from_step].append(edge.to_step)
            indegree[edge.to_step] += 1
        ready = sorted(step_id for step_id, degree in indegree.items() if degree == 0)
        ordered: list[ActionStep | ConditionStep] = []
        while ready:
            current = ready.pop(0)
            ordered.append(by_id[current])
            for target in sorted(outgoing[current]):
                indegree[target] -= 1
                if indegree[target] == 0:
                    ready.append(target)
                    ready.sort()
        return ordered

    @staticmethod
    def _is_selected(artifact: PortablePlaybookV1, step_id: str, outcomes: dict[str, str]) -> bool:
        incoming = [edge for edge in artifact.edges if edge.to_step == step_id]
        if not incoming:
            return True
        return any(
            outcomes.get(edge.from_step) == edge.outcome
            or (edge.outcome == "ALWAYS" and edge.from_step in outcomes)
            for edge in incoming
        )

    @classmethod
    def _evaluate(
        cls,
        expression: ConditionExpression,
        *,
        artifact_input: dict[str, object],
        outputs: dict[str, dict[str, object]],
    ) -> bool:
        if expression.operator == "and":
            return all(
                cls._evaluate(item, artifact_input=artifact_input, outputs=outputs)
                for item in expression.operands
            )
        if expression.operator == "or":
            return any(
                cls._evaluate(item, artifact_input=artifact_input, outputs=outputs)
                for item in expression.operands
            )
        if expression.operator == "not":
            return not cls._evaluate(
                expression.operands[0], artifact_input=artifact_input, outputs=outputs
            )
        actual, exists = cls._resolve_path(expression.path or "", artifact_input, outputs)
        if expression.operator == "exists":
            return exists
        if not exists:
            return False
        expected = expression.value
        if expression.operator == "eq":
            return actual == expected
        if expression.operator == "ne":
            return actual != expected
        if expression.operator == "in":
            return isinstance(expected, list) and actual in expected
        try:
            if expression.operator == "gt":
                return bool(actual > expected)  # type: ignore[operator]
            if expression.operator == "gte":
                return bool(actual >= expected)  # type: ignore[operator]
            if expression.operator == "lt":
                return bool(actual < expected)  # type: ignore[operator]
            if expression.operator == "lte":
                return bool(actual <= expected)  # type: ignore[operator]
        except TypeError:
            return False
        return False

    @staticmethod
    def _resolve_path(
        path: str,
        artifact_input: dict[str, object],
        outputs: dict[str, dict[str, object]],
    ) -> tuple[object, bool]:
        parts = path.split(".")
        if parts[0] == "input":
            current: object = artifact_input
            parts = parts[1:]
        elif len(parts) >= 3 and parts[0] == "steps" and parts[2] == "output":
            current = outputs.get(parts[1], {})
            parts = parts[3:]
        else:
            return None, False
        for part in parts:
            if not isinstance(current, dict) or part not in current:
                return None, False
            current = current[part]
        return current, True
