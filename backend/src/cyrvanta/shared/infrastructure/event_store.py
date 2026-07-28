import json
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cyrvanta.shared.domain.events import DomainEvent
from cyrvanta.shared.infrastructure.event_envelope import EventEnvelopeV1


@dataclass(frozen=True, slots=True)
class ClaimedOutboxEvent:
    envelope: EventEnvelopeV1
    lease_token: UUID


class InboxClaim(StrEnum):
    ACQUIRED = "acquired"
    DUPLICATE = "duplicate"
    BUSY = "busy"


class SqlEventRecorder:
    def __init__(self, store: "SqlEventStore", session: AsyncSession) -> None:
        self._store = store
        self._session = session

    async def add(self, event: DomainEvent) -> None:
        await self._store.add(self._session, event)


class SqlEventStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], max_payload_bytes: int):
        self._session_factory = session_factory
        self._max_payload_bytes = max_payload_bytes

    def recorder(self, session: AsyncSession) -> SqlEventRecorder:
        return SqlEventRecorder(self, session)

    async def add(self, session: AsyncSession, event: DomainEvent) -> None:
        envelope = EventEnvelopeV1.from_domain(event)
        if envelope.payload_size() > self._max_payload_bytes:
            raise ValueError("event payload exceeds configured maximum")
        await session.execute(
            text(
                """
                INSERT INTO event_outbox (
                  event_id, tenant_id, event_name, schema_version,
                  aggregate_type, aggregate_id, occurred_at, correlation_id,
                  causation_id, producer, payload
                ) VALUES (
                  :event_id, :tenant_id, :event_name, :schema_version,
                  :aggregate_type, :aggregate_id, :occurred_at, :correlation_id,
                  :causation_id, :producer, CAST(:payload AS jsonb)
                )
                """
            ),
            {
                **envelope.model_dump(exclude={"payload"}),
                "payload": json.dumps(
                    envelope.model_dump(mode="json")["payload"],
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ),
            },
        )

    async def claim_outbox(self, batch_size: int, lease_seconds: int) -> list[ClaimedOutboxEvent]:
        async with self._session_factory() as session, session.begin():
            rows = (
                await session.execute(
                    text("SELECT * FROM claim_event_outbox(:batch_size, :lease_seconds)"),
                    {"batch_size": batch_size, "lease_seconds": lease_seconds},
                )
            ).mappings()
            return [
                ClaimedOutboxEvent(
                    envelope=EventEnvelopeV1(
                        event_id=row["event_id"],
                        tenant_id=row["tenant_id"],
                        event_name=row["event_name"],
                        schema_version=row["schema_version"],
                        aggregate_type=row["aggregate_type"],
                        aggregate_id=row["aggregate_id"],
                        occurred_at=row["occurred_at"],
                        correlation_id=row["correlation_id"],
                        causation_id=row["causation_id"],
                        producer=row["producer"],
                        payload=row["payload"],
                    ),
                    lease_token=row["lease_token"],
                )
                for row in rows
            ]

    async def confirm_outbox(self, event_id: UUID, lease_token: UUID) -> bool:
        async with self._session_factory() as session, session.begin():
            return bool(
                await session.scalar(
                    text("SELECT confirm_event_outbox(:event_id, :lease_token)"),
                    {"event_id": event_id, "lease_token": lease_token},
                )
            )

    async def fail_outbox(
        self, event_id: UUID, lease_token: UUID, error_code: str, retry_seconds: int
    ) -> bool:
        async with self._session_factory() as session, session.begin():
            return bool(
                await session.scalar(
                    text(
                        """
                        SELECT fail_event_outbox(
                          :event_id, :lease_token, :error_code, :retry_seconds
                        )
                        """
                    ),
                    {
                        "event_id": event_id,
                        "lease_token": lease_token,
                        "error_code": error_code,
                        "retry_seconds": retry_seconds,
                    },
                )
            )

    async def claim_inbox(
        self,
        session: AsyncSession,
        envelope: EventEnvelopeV1,
        consumer_name: str,
        lease_seconds: int,
    ) -> InboxClaim:
        inserted = await session.scalar(
            text(
                """
                INSERT INTO event_inbox (
                  tenant_id, event_id, consumer_name, event_name,
                  schema_version, status, lease_expires_at
                ) VALUES (
                  :tenant_id, :event_id, :consumer_name, :event_name,
                  :schema_version, 'processing',
                  now() + make_interval(secs => :lease_seconds)
                )
                ON CONFLICT (tenant_id, consumer_name, event_id) DO NOTHING
                RETURNING true
                """
            ),
            {
                "tenant_id": envelope.tenant_id,
                "event_id": envelope.event_id,
                "consumer_name": consumer_name,
                "event_name": envelope.event_name,
                "schema_version": envelope.schema_version,
                "lease_seconds": lease_seconds,
            },
        )
        if inserted:
            return InboxClaim.ACQUIRED

        status = await session.scalar(
            text(
                """
                SELECT status
                FROM event_inbox
                WHERE tenant_id = :tenant_id
                  AND consumer_name = :consumer_name
                  AND event_id = :event_id
                """
            ),
            {
                "tenant_id": envelope.tenant_id,
                "consumer_name": consumer_name,
                "event_id": envelope.event_id,
            },
        )
        if status == "completed":
            return InboxClaim.DUPLICATE

        reclaimed = await session.scalar(
            text(
                """
                UPDATE event_inbox
                SET
                  status = 'processing',
                  attempt_count = attempt_count + 1,
                  last_received_at = now(),
                  lease_expires_at = now() + make_interval(secs => :lease_seconds),
                  last_error_code = NULL
                WHERE tenant_id = :tenant_id
                  AND consumer_name = :consumer_name
                  AND event_id = :event_id
                  AND (
                    status = 'failed'
                    OR (status = 'processing' AND lease_expires_at < now())
                  )
                RETURNING true
                """
            ),
            {
                "tenant_id": envelope.tenant_id,
                "consumer_name": consumer_name,
                "event_id": envelope.event_id,
                "lease_seconds": lease_seconds,
            },
        )
        return InboxClaim.ACQUIRED if reclaimed else InboxClaim.BUSY

    async def complete_inbox(
        self, session: AsyncSession, event_id: UUID, consumer_name: str
    ) -> None:
        changed = await session.scalar(
            text(
                """
                UPDATE event_inbox
                SET
                  status = 'completed',
                  completed_at = now(),
                  lease_expires_at = NULL,
                  last_error_code = NULL
                WHERE event_id = :event_id
                  AND consumer_name = :consumer_name
                  AND status = 'processing'
                RETURNING true
                """
            ),
            {"event_id": event_id, "consumer_name": consumer_name},
        )
        if not changed:
            raise RuntimeError("inbox completion lost its processing lease")

    async def fail_inbox(
        self,
        session: AsyncSession,
        event_id: UUID,
        consumer_name: str,
        error_code: str,
    ) -> None:
        await session.execute(
            text(
                """
                UPDATE event_inbox
                SET
                  status = 'failed',
                  lease_expires_at = NULL,
                  last_error_code = :error_code
                WHERE event_id = :event_id
                  AND consumer_name = :consumer_name
                  AND status = 'processing'
                """
            ),
            {
                "event_id": event_id,
                "consumer_name": consumer_name,
                "error_code": error_code,
            },
        )
