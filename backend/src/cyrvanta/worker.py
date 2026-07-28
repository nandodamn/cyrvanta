import asyncio
import logging

import aio_pika

from cyrvanta.modules.claims.application.service import (
    CLAIM_ASSESSED_EVENT,
    CLAIM_CREATED_EVENT,
    CLAIM_PRESENTATION_CREATED_EVENT,
    CLAIM_RELATED_EVENT,
)
from cyrvanta.modules.integrations.application.finding_ingestion import (
    FINDING_NORMALIZED_EVENT,
)
from cyrvanta.shared.config import get_settings
from cyrvanta.shared.database import SessionFactory
from cyrvanta.shared.domain.events import DomainEvent
from cyrvanta.shared.infrastructure.event_store import SqlEventStore
from cyrvanta.shared.infrastructure.rabbitmq import (
    TRACEABILITY_EVENT,
    EventConsumer,
    OutboxDispatcher,
)
from cyrvanta.shared.logging import configure_logging


async def handle_traceability_probe(event: DomainEvent) -> None:
    # The durable inbox completion is the probe's observable effect.
    if event.event_name != TRACEABILITY_EVENT:
        raise ValueError("unexpected traceability event")


async def handle_normalized_finding(event: DomainEvent) -> None:
    # Later stages attach correlation handlers; durable inbox is the current effect.
    if event.event_name != FINDING_NORMALIZED_EVENT:
        raise ValueError("unexpected normalized finding event")


async def handle_claim_event(event: DomainEvent) -> None:
    expected = {
        CLAIM_CREATED_EVENT,
        CLAIM_ASSESSED_EVENT,
        CLAIM_RELATED_EVENT,
        CLAIM_PRESENTATION_CREATED_EVENT,
    }
    if event.event_name not in expected:
        raise ValueError("unexpected claim event")


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = logging.getLogger("cyrvanta.worker")
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    store = SqlEventStore(SessionFactory, settings.event_max_payload_bytes)
    consumer = EventConsumer(
        connection,
        store,
        settings,
        {
            (TRACEABILITY_EVENT, 1): lambda _session: handle_traceability_probe,
            (FINDING_NORMALIZED_EVENT, 1): lambda _session: handle_normalized_finding,
            (CLAIM_CREATED_EVENT, 1): lambda _session: handle_claim_event,
            (CLAIM_ASSESSED_EVENT, 1): lambda _session: handle_claim_event,
            (CLAIM_RELATED_EVENT, 1): lambda _session: handle_claim_event,
            (CLAIM_PRESENTATION_CREATED_EVENT, 1): lambda _session: handle_claim_event,
        },
    )
    try:
        topology = await consumer.start()
        logger.info("worker_ready")
        await OutboxDispatcher(store, topology, settings).run_forever()
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(run())
