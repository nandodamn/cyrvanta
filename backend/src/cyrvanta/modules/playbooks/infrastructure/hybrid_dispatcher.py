from __future__ import annotations

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
        async with SessionFactory() as session:
            tenant_ids = list(
                (
                    await session.scalars(
                        select(TenantModel.id).order_by(TenantModel.created_at).limit(limit)
                    )
                ).all()
            )
        dispatched = 0
        for tenant_id in tenant_ids:
            async with tenant_session(tenant_id) as session:
                execution_ids = list(
                    (
                        await session.scalars(
                            select(PlaybookExecutionModel.id)
                            .where(PlaybookExecutionModel.status == ExecutionStatus.QUEUED.value)
                            .order_by(PlaybookExecutionModel.created_at)
                            .limit(limit - dispatched)
                        )
                    ).all()
                )
            for execution_id in execution_ids:
                outcome = await self.dispatch(tenant_id, execution_id, uuid4())
                if outcome is not None:
                    dispatched += 1
                if dispatched >= limit:
                    return dispatched
        return dispatched

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
                    PlaybookExecutionModel.binding_id == AutomationEngineBindingModel.id,
                )
                .where(
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
            if not self.settings.n8n_enabled:
                return None
            return await self.n8n.dispatch(tenant_id, execution_id, correlation_id)
        return None

    async def reconcile_timeouts(self, limit: int = 100) -> int:
        return await self.n8n.reconcile_timeouts(limit)
