import json
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import quote
from uuid import UUID, uuid4

import httpx
from sqlalchemy import func, select

from cyrvanta.modules.identity.infrastructure.models import TenantModel
from cyrvanta.modules.playbooks.domain.models import (
    ExecutionStatus,
    body_sha256,
    canonical_signature_material,
    sign_request,
)
from cyrvanta.modules.playbooks.infrastructure.models import (
    AutomationEngineBindingModel,
    PlaybookExecutionAttemptModel,
    PlaybookExecutionModel,
    PlaybookVersionModel,
)
from cyrvanta.shared.config import Settings
from cyrvanta.shared.database import SessionFactory, tenant_session
from cyrvanta.shared.domain.events import DomainEvent
from cyrvanta.shared.infrastructure.event_store import SqlEventStore

DISPATCH_REQUESTED_EVENT = "security.playbook_execution.dispatch_requested"


@dataclass(frozen=True, slots=True)
class SignedPackage:
    url: str
    body: str
    headers: dict[str, str]


class N8nPlaybookDispatcher:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def handle(self, event: DomainEvent) -> None:
        if event.event_name != DISPATCH_REQUESTED_EVENT:
            raise ValueError("unexpected playbook dispatch event")
        if not self.settings.playbook_dispatch_enabled:
            return
        await self.dispatch(event.tenant_id, event.aggregate_id, event.correlation_id)

    async def dispatch_pending(self, limit: int = 25) -> int:
        if not self.settings.playbook_dispatch_enabled:
            return 0
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
                ids = list(
                    (
                        await session.scalars(
                            select(PlaybookExecutionModel.id)
                            .where(
                                PlaybookExecutionModel.status
                                == ExecutionStatus.QUEUED.value
                            )
                            .order_by(PlaybookExecutionModel.created_at)
                            .limit(limit - dispatched)
                        )
                    ).all()
                )
            for execution_id in ids:
                await self.dispatch(tenant_id, execution_id, uuid4())
                dispatched += 1
                if dispatched >= limit:
                    return dispatched
        return dispatched

    async def reconcile_timeouts(self, limit: int = 100) -> int:
        now = datetime.now(UTC)
        terminal = {
            ExecutionStatus.SUCCEEDED.value,
            ExecutionStatus.FAILED.value,
            ExecutionStatus.TIMED_OUT.value,
            ExecutionStatus.CANCELLED.value,
        }
        async with SessionFactory() as session:
            tenant_ids = list(
                (
                    await session.scalars(
                        select(TenantModel.id).order_by(TenantModel.created_at)
                    )
                ).all()
            )
        changed = 0
        for tenant_id in tenant_ids:
            async with tenant_session(tenant_id) as session:
                executions = list(
                    (
                        await session.scalars(
                            select(PlaybookExecutionModel)
                            .where(
                                PlaybookExecutionModel.status.not_in(terminal),
                                PlaybookExecutionModel.deadline_at <= now,
                            )
                            .order_by(PlaybookExecutionModel.deadline_at)
                            .with_for_update(skip_locked=True)
                            .limit(limit - changed)
                        )
                    ).all()
                )
                store = SqlEventStore(
                    SessionFactory, self.settings.event_max_payload_bytes
                )
                for execution in executions:
                    execution.status = ExecutionStatus.TIMED_OUT.value
                    execution.completed_at = now
                    execution.error_code = "EXECUTION_DEADLINE_EXCEEDED"
                    await store.recorder(session).add(
                        DomainEvent.create(
                            event_name="security.playbook_execution.timed_out",
                            tenant_id=tenant_id,
                            aggregate_type="playbook_execution",
                            aggregate_id=execution.id,
                            correlation_id=uuid4(),
                            producer="playbooks",
                            payload={
                                "execution_id": str(execution.id),
                                "deadline_at": execution.deadline_at.isoformat(),
                            },
                        )
                    )
                    changed += 1
            if changed >= limit:
                break
        return changed

    async def dispatch(
        self, tenant_id: UUID, execution_id: UUID, correlation_id: UUID
    ) -> None:
        if (
            self.settings.automation_kill_switch
            or not self.settings.n8n_dispatch_key
            or not self.settings.n8n_callback_key
        ):
            return
        dispatch_id = uuid4()
        async with tenant_session(tenant_id) as session:
            execution = await session.scalar(
                select(PlaybookExecutionModel)
                .where(PlaybookExecutionModel.id == execution_id)
                .with_for_update(skip_locked=True)
            )
            if execution is None or execution.status != ExecutionStatus.QUEUED.value:
                return
            if execution.execution_mode != "SYNTHETIC":
                return
            binding = await session.scalar(
                select(AutomationEngineBindingModel).where(
                    AutomationEngineBindingModel.id == execution.binding_id,
                    AutomationEngineBindingModel.active.is_(True),
                    AutomationEngineBindingModel.sync_status == "SYNCHRONIZED",
                )
            )
            version = await session.scalar(
                select(PlaybookVersionModel).where(
                    PlaybookVersionModel.id == execution.playbook_version_id,
                    PlaybookVersionModel.status == "APPROVED",
                )
            )
            if (
                binding is None
                or version is None
                or binding.observed_digest != version.artifact_sha256
            ):
                return
            attempt_number = int(
                await session.scalar(
                    select(func.count(PlaybookExecutionAttemptModel.id)).where(
                        PlaybookExecutionAttemptModel.execution_id == execution.id
                    )
                )
                or 0
            ) + 1
            attempt = PlaybookExecutionAttemptModel(
                tenant_id=tenant_id,
                execution_id=execution.id,
                attempt_number=attempt_number,
                dispatch_id=dispatch_id,
                status=ExecutionStatus.DISPATCHING.value,
            )
            session.add(attempt)
            execution.status = ExecutionStatus.DISPATCHING.value
            await session.flush()
            snapshot = {
                "execution_id": execution.id,
                "incident_id": execution.incident_id,
                "proposal_fingerprint": execution.proposal_fingerprint,
                "inputs": dict(execution.inputs),
                "workflow_code": version.workflow_code,
                "version": version.version,
                "webhook_path": binding.webhook_path,
                "key_id": binding.key_id,
            }

        claim_body = self._json_bytes(
            {
                "dispatch_id": str(dispatch_id),
                "adapter_execution_id": f"n8n-{dispatch_id}",
                "proposal_fingerprint": snapshot["proposal_fingerprint"],
            }
        )
        claim_path = f"/api/v1/internal/playbook-executions/{execution_id}/claim"
        claim = self._package(
            tenant_id=tenant_id,
            path=claim_path,
            body=claim_body,
            secret=self.settings.n8n_dispatch_key,
            key_id=str(snapshot["key_id"]),
        )
        terminal_body = self._json_bytes(
            {
                "adapter_event_id": str(uuid4()),
                "sequence": 2,
                "status": "SUCCEEDED",
                "result": {
                    "simulated": True,
                    "effect": "none",
                    "workflow_code": snapshot["workflow_code"],
                },
                "error_code": None,
                "safe_detail": "Synthetic workflow completed without changing a target system",
                "occurred_at": datetime.now(UTC).isoformat(),
            }
        )
        terminal_path = f"/api/v1/internal/playbook-executions/{execution_id}/updates"
        terminal = self._package(
            tenant_id=tenant_id,
            path=terminal_path,
            body=terminal_body,
            secret=self.settings.n8n_callback_key,
            key_id=str(snapshot["key_id"]),
        )
        dispatch_body = self._json_bytes(
            {
                "schema_version": 1,
                "dispatch_id": str(dispatch_id),
                "execution_id": str(execution_id),
                "incident_id": str(snapshot["incident_id"]),
                "workflow_code": snapshot["workflow_code"],
                "workflow_version": snapshot["version"],
                "execution_mode": "SYNTHETIC",
                "inputs": snapshot["inputs"],
                "claim": {
                    "url": claim.url,
                    "body": claim.body,
                    "headers": claim.headers,
                },
                "terminal_callback": {
                    "url": terminal.url,
                    "body": terminal.body,
                    "headers": terminal.headers,
                },
            }
        )
        workflow_path = quote(str(snapshot["webhook_path"]), safe="")
        webhook_path = f"/webhook/{workflow_path}"
        headers = self._signed_headers(
            tenant_id,
            webhook_path,
            dispatch_body,
            self.settings.n8n_dispatch_key,
            str(snapshot["key_id"]),
        )
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{self.settings.n8n_base_url}{webhook_path}",
                    content=dispatch_body,
                    headers={"Content-Type": "application/json", **headers},
                )
                response.raise_for_status()
        except httpx.HTTPError:
            await self._finish_dispatch(
                tenant_id, execution_id, dispatch_id, correlation_id, "UNKNOWN"
            )
            return
        await self._finish_dispatch(
            tenant_id, execution_id, dispatch_id, correlation_id, "DISPATCHED"
        )

    async def _finish_dispatch(
        self,
        tenant_id: UUID,
        execution_id: UUID,
        dispatch_id: UUID,
        correlation_id: UUID,
        status: str,
    ) -> None:
        async with tenant_session(tenant_id) as session:
            execution = await session.scalar(
                select(PlaybookExecutionModel)
                .where(PlaybookExecutionModel.id == execution_id)
                .with_for_update()
            )
            attempt = await session.scalar(
                select(PlaybookExecutionAttemptModel).where(
                    PlaybookExecutionAttemptModel.dispatch_id == dispatch_id
                )
            )
            if execution is None or attempt is None:
                return
            attempt.status = status
            if execution.status == ExecutionStatus.DISPATCHING.value:
                execution.status = status
            store = SqlEventStore(SessionFactory, self.settings.event_max_payload_bytes)
            await store.recorder(session).add(
                DomainEvent.create(
                    event_name="security.playbook_execution.dispatched",
                    tenant_id=tenant_id,
                    aggregate_type="playbook_execution",
                    aggregate_id=execution_id,
                    correlation_id=correlation_id,
                    producer="playbooks",
                    payload={
                        "execution_id": str(execution_id),
                        "dispatch_id": str(dispatch_id),
                        "delivery_status": status,
                        "current_status": execution.status,
                    },
                )
            )

    def _package(
        self,
        *,
        tenant_id: UUID,
        path: str,
        body: bytes,
        secret: str,
        key_id: str,
    ) -> SignedPackage:
        return SignedPackage(
            url=f"{self.settings.internal_api_url}{path}",
            body=body.decode(),
            headers={
                "Content-Type": "application/json",
                **self._signed_headers(tenant_id, path, body, secret, key_id),
            },
        )

    @staticmethod
    def _signed_headers(
        tenant_id: UUID, path: str, body: bytes, secret: str, key_id: str
    ) -> dict[str, str]:
        timestamp = int(datetime.now(UTC).timestamp())
        nonce = uuid4()
        material = canonical_signature_material(
            method="POST",
            path=path,
            timestamp=timestamp,
            nonce=str(nonce),
            body_digest=body_sha256(body),
            tenant_id=str(tenant_id),
        )
        return {
            "X-Cyrvanta-Key-Id": key_id,
            "X-Cyrvanta-Timestamp": str(timestamp),
            "X-Cyrvanta-Nonce": str(nonce),
            "X-Cyrvanta-Signature": sign_request(secret, material),
        }

    @staticmethod
    def _json_bytes(value: dict[str, object]) -> bytes:
        return json.dumps(
            value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).encode()
