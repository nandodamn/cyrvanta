import asyncio
import logging
from uuid import UUID

import aio_pika

from cyrvanta.modules.claims.application.correlation import ClaimCorrelationAdapter
from cyrvanta.modules.claims.application.service import (
    CLAIM_ASSESSED_EVENT,
    CLAIM_CREATED_EVENT,
    CLAIM_PRESENTATION_CREATED_EVENT,
    CLAIM_RELATED_EVENT,
)
from cyrvanta.modules.correlation.application.service import (
    CORRELATION_MATCHED_EVENT,
    CORRELATION_MEMBER_ADDED_EVENT,
    CorrelationService,
)
from cyrvanta.modules.correlation.infrastructure.repository import (
    SqlCorrelationRepository,
)
from cyrvanta.modules.incident.application.correlation import (
    IncidentCorrelationAdapter,
)
from cyrvanta.modules.integrations.application.finding_ingestion import (
    FINDING_NORMALIZED_EVENT,
)
from cyrvanta.modules.playbooks.infrastructure.dispatcher import DISPATCH_REQUESTED_EVENT
from cyrvanta.modules.playbooks.infrastructure.hybrid_dispatcher import (
    HybridPlaybookDispatcher,
)
from cyrvanta.modules.threat_knowledge.application.service import (
    EXPLANATION_FAILED_EVENT,
    EXPLANATION_GENERATED_EVENT,
    RISK_ASSESSED_EVENT,
    THREAT_MAPPING_ASSESSED_EVENT,
    ThreatEnrichmentService,
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


async def handle_normalized_finding(
    event: DomainEvent,
    service: CorrelationService,
) -> None:
    if event.event_name != FINDING_NORMALIZED_EVENT:
        raise ValueError("unexpected normalized finding event")
    await service.handle_normalized_finding(event)


async def handle_claim_event(event: DomainEvent) -> None:
    expected = {
        CLAIM_CREATED_EVENT,
        CLAIM_ASSESSED_EVENT,
        CLAIM_RELATED_EVENT,
        CLAIM_PRESENTATION_CREATED_EVENT,
    }
    if event.event_name not in expected:
        raise ValueError("unexpected claim event")


async def handle_correlation_event(event: DomainEvent, service: ThreatEnrichmentService) -> None:
    if event.event_name not in {
        CORRELATION_MATCHED_EVENT,
        CORRELATION_MEMBER_ADDED_EVENT,
    }:
        raise ValueError("unexpected correlation event")
    try:
        incident_id = UUID(str(event.payload["incident_id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("correlation event payload is invalid") from exc
    await service.enrich(
        event.tenant_id,
        incident_id,
        event.correlation_id,
        causation_id=event.event_id,
    )


async def handle_enrichment_event(event: DomainEvent) -> None:
    if event.event_name not in {
        THREAT_MAPPING_ASSESSED_EVENT,
        RISK_ASSESSED_EVENT,
        EXPLANATION_GENERATED_EVENT,
        EXPLANATION_FAILED_EVENT,
    }:
        raise ValueError("unexpected enrichment event")


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
            (FINDING_NORMALIZED_EVENT, 1): lambda session: (
                lambda event: handle_normalized_finding(
                    event,
                    CorrelationService(
                        SqlCorrelationRepository(session),
                        IncidentCorrelationAdapter(session),
                        ClaimCorrelationAdapter(session),
                        store.recorder(session),
                    ),
                )
            ),
            (CLAIM_CREATED_EVENT, 1): lambda _session: handle_claim_event,
            (CLAIM_ASSESSED_EVENT, 1): lambda _session: handle_claim_event,
            (CLAIM_RELATED_EVENT, 1): lambda _session: handle_claim_event,
            (CLAIM_PRESENTATION_CREATED_EVENT, 1): lambda _session: handle_claim_event,
            (CORRELATION_MATCHED_EVENT, 1): lambda session: (
                lambda event: handle_correlation_event(
                    event,
                    ThreatEnrichmentService(session, store.recorder(session)),
                )
            ),
            (CORRELATION_MEMBER_ADDED_EVENT, 1): lambda session: (
                lambda event: handle_correlation_event(
                    event,
                    ThreatEnrichmentService(session, store.recorder(session)),
                )
            ),
            (THREAT_MAPPING_ASSESSED_EVENT, 1): lambda _session: handle_enrichment_event,
            (RISK_ASSESSED_EVENT, 1): lambda _session: handle_enrichment_event,
            (EXPLANATION_GENERATED_EVENT, 1): lambda _session: handle_enrichment_event,
            (EXPLANATION_FAILED_EVENT, 1): lambda _session: handle_enrichment_event,
            (DISPATCH_REQUESTED_EVENT, 1): lambda _session: (
                HybridPlaybookDispatcher(settings).handle
            ),
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
