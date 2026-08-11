from datetime import UTC, datetime
from uuid import UUID

from cyrvanta.modules.operations.application.schemas import NetworkTopologyResponse


class NetworkTopologyService:
    async def get_topology(self, tenant_id: UUID) -> NetworkTopologyResponse:
        """Return no topology until a tenant-owned asset inventory is available."""
        return NetworkTopologyResponse(
            tenant_id=tenant_id,
            nodes=[],
            edges=[],
            updated_at=datetime.now(UTC).isoformat(),
        )
