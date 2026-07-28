import asyncio
import logging

import aio_pika

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
        {(TRACEABILITY_EVENT, 1): lambda _session: handle_traceability_probe},
    )
    try:
        topology = await consumer.start()
        logger.info("worker_ready")
        await OutboxDispatcher(store, topology, settings).run_forever()
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(run())
