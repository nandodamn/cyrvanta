import argparse
import asyncio
import re
from datetime import UTC, datetime
from uuid import UUID, uuid4

from cyrvanta.shared.config import get_settings
from cyrvanta.shared.database import SessionFactory, tenant_session
from cyrvanta.shared.domain.events import DomainEvent
from cyrvanta.shared.infrastructure.event_store import SqlEventStore
from cyrvanta.shared.infrastructure.rabbitmq import TRACEABILITY_EVENT

PROBE_CODE = re.compile(r"^[a-zA-Z0-9_.-]{1,80}$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a synthetic tenant-scoped traceability event."
    )
    parser.add_argument("--tenant-id", required=True, type=UUID)
    parser.add_argument("--code", default="manual-probe")
    return parser.parse_args()


async def create_probe(tenant_id: UUID, code: str) -> DomainEvent:
    if PROBE_CODE.fullmatch(code) is None:
        raise ValueError("probe code must contain only letters, digits, dot, dash or underscore")
    settings = get_settings()
    store = SqlEventStore(SessionFactory, settings.event_max_payload_bytes)
    correlation_id = uuid4()
    event = DomainEvent.create(
        event_name=TRACEABILITY_EVENT,
        tenant_id=tenant_id,
        aggregate_type="traceability_probe",
        aggregate_id=uuid4(),
        correlation_id=correlation_id,
        producer="cyrvanta.traceability_probe",
        payload={
            "probe_code": code,
            "requested_at": datetime.now(UTC).isoformat(),
            "synthetic": True,
        },
    )
    async with tenant_session(tenant_id) as session:
        await store.recorder(session).add(event)
    return event


async def run() -> None:
    args = parse_args()
    event = await create_probe(args.tenant_id, args.code)
    print(f"event_id={event.event_id}")
    print(f"correlation_id={event.correlation_id}")
    print("data_classification=synthetic")


if __name__ == "__main__":
    asyncio.run(run())
