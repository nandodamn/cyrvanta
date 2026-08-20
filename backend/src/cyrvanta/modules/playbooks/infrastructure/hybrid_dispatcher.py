from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID, uuid4

from sqlalchemy import select

from cyrvanta.modules.identity.infrastructure.models import TenantModel
from cyrvanta.modules.playbooks.domain.models import ExecutionStatus
from cyrvanta.modules.playbooks.infrastructure.dispatcher import (
    DISPATCH_REQUESTED_EVENT,
    N8nPlaybookDispatcher,
)
from cyrvanta.modules.playbooks.infrastructure.models import (
    AutomationEngineBindingModel,
    PlaybookExecutionModel,
)
from cyrvanta.modules.playbooks.infrastructure.native_engine import NativePlaybookDispatcher
from cyrvanta.shared.config import Settings
from cyrvanta.shared.database import SessionFactory, tenant_session
from cyrvanta.shared.domain.events import DomainEvent


class HybridPlaybookDispatcher:
    """Select exactly one engine from the immutable execution binding."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.native = NativePlaybookDispatcher(settings)
        self.n8n = N8nPlaybookDispatcher(settings)

    async def handle(self, event: DomainEvent) -> None:
        if event.event_name != DISPATCH_REQUESTED_EVENT:
            raise ValueError("unexpected playbook dispatch event")
        outcome = await self.dispatch(
            event.tenant_id,
            event.aggregate_id,
            event.correlation_id,
            causation_id=event.event_id,
        )
        if outcome is False:
            raise RuntimeError("playbook dispatch failed")

    async def dispatch_pending(self, limit: int = 25) -> int:
        if limit < 1 or limit > 500:
            raise ValueError("Dispatch batch size must be between 1 and 500")
        async with SessionFactory() as session:
            tenant_ids = list(
                (
                    await session.scalars(
                        select(TenantModel.id)
                        .where(TenantModel.status == "active")
                        .order_by(TenantModel.created_at)
                    )
                ).all()
            )
        pending_batches: list[tuple[UUID, list[UUID]]] = []
        for tenant_id in tenant_ids:
            enabled_engines = self._enabled_engines(tenant_id)
            if not enabled_engines:
                continue
            async with tenant_session(tenant_id) as session:
                execution_ids = list(
                    (
                        await session.scalars(
                            select(PlaybookExecutionModel.id)
                            .join(
                                AutomationEngineBindingModel,
                                (
                                    PlaybookExecutionModel.binding_id
                                    == AutomationEngineBindingModel.id
                                )
                                & (
                                    PlaybookExecutionModel.tenant_id
                                    == AutomationEngineBindingModel.tenant_id
                                ),
                            )
                            .where(
                                PlaybookExecutionModel.tenant_id == tenant_id,
                                PlaybookExecutionModel.status == ExecutionStatus.QUEUED.value,
                                PlaybookExecutionModel.execution_mode == "LIVE",
                                AutomationEngineBindingModel.tenant_id == tenant_id,
                                AutomationEngineBindingModel.active.is_(True),
                                AutomationEngineBindingModel.sync_status == "SYNCHRONIZED",
                                AutomationEngineBindingModel.engine_type.in_(enabled_engines),
                            )
                            .order_by(PlaybookExecutionModel.created_at)
                            .limit(limit)
                        )
                    ).all()
                )
            if execution_ids:
                pending_batches.append((tenant_id, execution_ids))

        dispatched = 0
        for attempted, (tenant_id, execution_id) in enumerate(self._round_robin(pending_batches)):
            if attempted >= limit:
                break
            outcome = await self.dispatch(tenant_id, execution_id, uuid4())
            if outcome is not None:
                dispatched += 1
        return dispatched

    @staticmethod
    def _round_robin(
        batches: list[tuple[UUID, list[UUID]]],
    ) -> Iterator[tuple[UUID, UUID]]:
        positions = [0] * len(batches)
        remaining = True
        while remaining:
            remaining = False
            for index, (tenant_id, execution_ids) in enumerate(batches):
                position = positions[index]
                if position >= len(execution_ids):
                    continue
                remaining = True
                positions[index] += 1
                yield tenant_id, execution_ids[position]

    def _enabled_engines(self, tenant_id: UUID) -> tuple[str, ...]:
        engines: list[str] = []
        allowed_tenants = self.settings.native_enabled_tenant_ids
        if (
            self.settings.playbook_native_engine_enabled
            and self.settings.playbook_live_enabled
            and self.settings.playbook_dispatch_enabled
            and not self.settings.automation_kill_switch
            and (not allowed_tenants or str(tenant_id) in allowed_tenants)
        ):
            engines.append("NATIVE")
        if self._n8n_dispatch_enabled():
            engines.append("N8N")
        return tuple(engines)

    def _n8n_dispatch_enabled(self) -> bool:
        return bool(
            self.settings.n8n_enabled
            and self.settings.playbook_live_enabled
            and self.settings.playbook_dispatch_enabled
            and not self.settings.automation_kill_switch
        )

    async def dispatch(
        self,
        tenant_id: UUID,
        execution_id: UUID,
        correlation_id: UUID,
        *,
        causation_id: UUID | None = None,
    ) -> bool | None:
        async with tenant_session(tenant_id) as session:
            engine_type = await session.scalar(
                select(AutomationEngineBindingModel.engine_type)
                .join(
                    PlaybookExecutionModel,
                    (PlaybookExecutionModel.binding_id == AutomationEngineBindingModel.id)
                    & (PlaybookExecutionModel.tenant_id == AutomationEngineBindingModel.tenant_id),
                )
                .join(
                    TenantModel,
                    TenantModel.id == PlaybookExecutionModel.tenant_id,
                )
                .where(
                    TenantModel.id == tenant_id,
                    TenantModel.status == "active",
                    PlaybookExecutionModel.tenant_id == tenant_id,
                    AutomationEngineBindingModel.tenant_id == tenant_id,
                    PlaybookExecutionModel.id == execution_id,
                    PlaybookExecutionModel.status.in_(
                        (ExecutionStatus.QUEUED.value, ExecutionStatus.RUNNING.value)
                    ),
                )
            )
        return await self._dispatch_selected(
            engine_type, tenant_id, execution_id, correlation_id, causation_id
        )

    async def _dispatch_selected(
        self,
        engine_type: str | None,
        tenant_id: UUID,
        execution_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None,
    ) -> bool | None:
        if engine_type == "NATIVE":
            return await self.native.dispatch(tenant_id, execution_id, correlation_id, causation_id)
        if engine_type == "N8N":
            if not self._n8n_dispatch_enabled():
                return None
            return await self.n8n.dispatch(tenant_id, execution_id, correlation_id)
        return None

    async def reconcile_timeouts(self, limit: int = 100) -> int:
        return await self.n8n.reconcile_timeouts(limit)
