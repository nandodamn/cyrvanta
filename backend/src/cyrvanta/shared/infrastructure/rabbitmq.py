from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from aio_pika import DeliveryMode, ExchangeType, Message
from aio_pika.abc import (
    AbstractChannel,
    AbstractExchange,
    AbstractIncomingMessage,
    AbstractRobustConnection,
)
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from cyrvanta.shared.application.messaging import EventHandler
from cyrvanta.shared.config import Settings
from cyrvanta.shared.database import tenant_session
from cyrvanta.shared.infrastructure.event_envelope import EventEnvelopeV1
from cyrvanta.shared.infrastructure.event_store import (
    InboxClaim,
    SqlEventStore,
)

EVENTS_EXCHANGE = "cyrvanta.events"
RETRY_EXCHANGE = "cyrvanta.retry"
DEADLETTER_EXCHANGE = "cyrvanta.deadletter"
TRACEABILITY_QUEUE = "cyrvanta.traceability.v1"
TRACEABILITY_DLQ = f"{TRACEABILITY_QUEUE}.dlq"
TRACEABILITY_EVENT = "platform.traceability.probe.created"
TRACEABILITY_CONSUMER = "traceability-probe-v1"
EventHandlerFactory = Callable[[AsyncSession], EventHandler]


class PermanentMessageError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class RabbitTopology:
    events: AbstractExchange
    retry: AbstractExchange
    deadletter: AbstractExchange


async def declare_topology(
    channel: AbstractChannel, retry_delays: tuple[int, ...]
) -> RabbitTopology:
    events = await channel.declare_exchange(EVENTS_EXCHANGE, ExchangeType.TOPIC, durable=True)
    retry = await channel.declare_exchange(RETRY_EXCHANGE, ExchangeType.TOPIC, durable=True)
    deadletter = await channel.declare_exchange(
        DEADLETTER_EXCHANGE, ExchangeType.TOPIC, durable=True
    )
    main_queue = await channel.declare_queue(
        TRACEABILITY_QUEUE,
        durable=True,
        arguments={"x-dead-letter-exchange": DEADLETTER_EXCHANGE},
    )
    await main_queue.bind(events, routing_key=TRACEABILITY_EVENT)

    for attempt, delay in enumerate(retry_delays, start=1):
        retry_queue = await channel.declare_queue(
            f"{TRACEABILITY_QUEUE}.retry.{attempt}",
            durable=True,
            arguments={
                "x-message-ttl": delay * 1000,
                "x-dead-letter-exchange": EVENTS_EXCHANGE,
                "x-dead-letter-routing-key": TRACEABILITY_EVENT,
            },
        )
        await retry_queue.bind(retry, routing_key=f"traceability.{attempt}")

    dlq = await channel.declare_queue(TRACEABILITY_DLQ, durable=True)
    await dlq.bind(deadletter, routing_key="#")
    return RabbitTopology(events=events, retry=retry, deadletter=deadletter)


def persistent_message(envelope: EventEnvelopeV1, *, attempt: int = 0) -> Message:
    return Message(
        body=envelope.message_body(),
        content_type="application/json",
        delivery_mode=DeliveryMode.PERSISTENT,
        message_id=str(envelope.event_id),
        type=envelope.event_name,
        correlation_id=str(envelope.correlation_id),
        timestamp=envelope.occurred_at,
        headers={
            "schema_version": envelope.schema_version,
            "tenant_id": str(envelope.tenant_id),
            "x-cyrvanta-attempt": attempt,
        },
    )


class OutboxDispatcher:
    def __init__(
        self,
        store: SqlEventStore,
        topology: RabbitTopology,
        settings: Settings,
    ) -> None:
        self._store = store
        self._topology = topology
        self._settings = settings
        self._logger = logging.getLogger("cyrvanta.worker.outbox")

    async def run_forever(self) -> None:
        while True:
            claimed = await self._store.claim_outbox(
                self._settings.outbox_batch_size,
                self._settings.outbox_lease_seconds,
            )
            if not claimed:
                await asyncio.sleep(self._settings.outbox_poll_interval_seconds)
                continue
            for item in claimed:
                try:
                    await self._topology.events.publish(
                        persistent_message(item.envelope),
                        routing_key=item.envelope.event_name,
                        mandatory=True,
                    )
                    confirmed = await self._store.confirm_outbox(
                        item.envelope.event_id, item.lease_token
                    )
                    if not confirmed:
                        self._logger.error(
                            "outbox_confirmation_lease_lost",
                            extra=_log_context(item.envelope),
                        )
                except asyncio.CancelledError:
                    raise
                except Exception:
                    self._logger.exception(
                        "outbox_publish_failed",
                        extra=_log_context(item.envelope),
                    )
                    await self._store.fail_outbox(
                        item.envelope.event_id,
                        item.lease_token,
                        "rabbitmq_publish_failed",
                        self._settings.retry_delays_seconds[0],
                    )


class EventConsumer:
    def __init__(
        self,
        connection: AbstractRobustConnection,
        store: SqlEventStore,
        settings: Settings,
        handlers: dict[tuple[str, int], EventHandlerFactory],
    ) -> None:
        self._connection = connection
        self._store = store
        self._settings = settings
        self._handlers = handlers
        self._logger = logging.getLogger("cyrvanta.worker.consumer")
        self._topology: RabbitTopology | None = None

    async def start(self) -> RabbitTopology:
        channel = await self._connection.channel(publisher_confirms=True)
        await channel.set_qos(prefetch_count=self._settings.event_consumer_prefetch)
        topology = await declare_topology(channel, self._settings.retry_delays_seconds)
        queue = await channel.get_queue(TRACEABILITY_QUEUE, ensure=True)
        await queue.consume(self._on_message)
        self._topology = topology
        return topology

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        attempt = _message_attempt(message)
        try:
            envelope = self._validate_message(message)
            handler_factory = self._handlers.get((envelope.event_name, envelope.schema_version))
            if handler_factory is None:
                raise PermanentMessageError("unsupported_schema")
            claim = await self._claim(envelope)
            if claim == InboxClaim.DUPLICATE:
                self._logger.info("event_duplicate", extra=_log_context(envelope))
                await message.ack()
                return
            if claim == InboxClaim.BUSY:
                await self._retry_or_deadletter(
                    message, attempt, "inbox_processing_busy", permanent=False
                )
                return
            try:
                async with asyncio.timeout(self._settings.event_handler_timeout_seconds):
                    async with tenant_session(envelope.tenant_id) as session:
                        handler = handler_factory(session)
                        await handler(envelope.to_domain())
                        await self._store.complete_inbox(
                            session, envelope.event_id, TRACEABILITY_CONSUMER
                        )
            except TimeoutError:
                await self._mark_failed(envelope, "handler_timeout")
                await self._retry_or_deadletter(
                    message, attempt, "handler_timeout", permanent=False
                )
                return
            except Exception:
                self._logger.exception("event_handler_failed", extra=_log_context(envelope))
                await self._mark_failed(envelope, "handler_failed")
                await self._retry_or_deadletter(message, attempt, "handler_failed", permanent=False)
                return
            self._logger.info("event_completed", extra=_log_context(envelope))
            await message.ack()
        except PermanentMessageError as exc:
            self._logger.warning("event_rejected", extra={"error_code": exc.code})
            await self._retry_or_deadletter(message, attempt, exc.code, permanent=True)
        except asyncio.CancelledError:
            raise
        except Exception:
            self._logger.exception("event_consumer_unexpected_error")
            await self._retry_or_deadletter(
                message, attempt, "consumer_unexpected", permanent=False
            )

    def _validate_message(self, message: AbstractIncomingMessage) -> EventEnvelopeV1:
        if len(message.body) > self._settings.event_max_payload_bytes * 2:
            raise PermanentMessageError("invalid_envelope_size")
        if message.content_type != "application/json":
            raise PermanentMessageError("invalid_content_type")
        try:
            envelope = EventEnvelopeV1.model_validate_json(message.body)
        except ValidationError as exc:
            raise PermanentMessageError("invalid_envelope") from exc
        if envelope.payload_size() > self._settings.event_max_payload_bytes:
            raise PermanentMessageError("payload_too_large")
        if message.message_id != str(envelope.event_id):
            raise PermanentMessageError("message_id_mismatch")
        if message.type != envelope.event_name:
            raise PermanentMessageError("event_name_mismatch")
        if message.correlation_id != str(envelope.correlation_id):
            raise PermanentMessageError("correlation_id_mismatch")
        return envelope

    async def _claim(self, envelope: EventEnvelopeV1) -> InboxClaim:
        async with tenant_session(envelope.tenant_id) as session:
            return await self._store.claim_inbox(
                session,
                envelope,
                TRACEABILITY_CONSUMER,
                self._settings.event_handler_timeout_seconds * 2,
            )

    async def _mark_failed(self, envelope: EventEnvelopeV1, error_code: str) -> None:
        async with tenant_session(envelope.tenant_id) as session:
            await self._store.fail_inbox(
                session, envelope.event_id, TRACEABILITY_CONSUMER, error_code
            )

    async def _retry_or_deadletter(
        self,
        message: AbstractIncomingMessage,
        attempt: int,
        error_code: str,
        *,
        permanent: bool,
    ) -> None:
        if self._topology is None:
            await message.reject(requeue=True)
            return
        envelope = _best_effort_envelope(message.body)
        headers = dict(message.headers or {})
        headers["x-error-code"] = error_code
        headers["x-cyrvanta-attempt"] = attempt + 1
        outgoing = Message(
            body=message.body,
            content_type=message.content_type,
            delivery_mode=DeliveryMode.PERSISTENT,
            message_id=message.message_id,
            type=message.type,
            correlation_id=message.correlation_id,
            timestamp=message.timestamp,
            headers=headers,
        )
        if not permanent and attempt < len(self._settings.retry_delays_seconds):
            await self._topology.retry.publish(
                outgoing,
                routing_key=f"traceability.{attempt + 1}",
                mandatory=True,
            )
            self._logger.warning(
                "event_retry_scheduled",
                extra={
                    **_optional_log_context(envelope),
                    "attempt": attempt + 1,
                    "error_code": error_code,
                },
            )
        else:
            routing_key = envelope.event_name if envelope else "invalid.envelope"
            await self._topology.deadletter.publish(
                outgoing, routing_key=routing_key, mandatory=True
            )
            self._logger.error(
                "event_deadlettered",
                extra={
                    **_optional_log_context(envelope),
                    "attempt": attempt,
                    "error_code": error_code,
                },
            )
        await message.ack()


def _message_attempt(message: AbstractIncomingMessage) -> int:
    raw_attempt: Any = (message.headers or {}).get("x-cyrvanta-attempt", 0)
    try:
        attempt = int(raw_attempt)
    except (TypeError, ValueError):
        return 0
    return max(0, min(attempt, 100))


def _best_effort_envelope(body: bytes) -> EventEnvelopeV1 | None:
    try:
        return EventEnvelopeV1.model_validate_json(body)
    except ValidationError:
        return None


def _log_context(envelope: EventEnvelopeV1) -> dict[str, str | int | None]:
    return {
        "event_id": str(envelope.event_id),
        "event_name": envelope.event_name,
        "schema_version": envelope.schema_version,
        "tenant_id": str(envelope.tenant_id),
        "correlation_id": str(envelope.correlation_id),
        "causation_id": str(envelope.causation_id) if envelope.causation_id else None,
    }


def _optional_log_context(
    envelope: EventEnvelopeV1 | None,
) -> dict[str, str | int | None]:
    return _log_context(envelope) if envelope else {}
