from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select

from cyrvanta.modules.incident.infrastructure.models import AlertReferenceModel
from cyrvanta.modules.operations.application.schemas import (
    NetworkTopologyResponse,
    TopologyEdge,
    TopologyNode,
    TopologyNodeAlert,
)
from cyrvanta.shared.database import tenant_session


class NetworkTopologyService:
    async def get_topology(self, tenant_id: UUID) -> NetworkTopologyResponse:
        now_str = datetime.now(timezone.utc).isoformat()

        # Query active non-discarded alerts count per tenant
        active_alerts_count = 0
        async with tenant_session(tenant_id) as session:
            stmt = select(func.count()).select_from(AlertReferenceModel).where(
                AlertReferenceModel.tenant_id == tenant_id,
                AlertReferenceModel.triage_status != "DISCARDED",
            )
            result = await session.execute(stmt)
            active_alerts_count = result.scalar() or 0

        # Build realistic topology nodes representing Cyrvanta's SOC network
        nodes = [
          TopologyNode(
              id="fw-01",
              name="Perimeter Firewall PaloAlto PA-3200",
              type="FIREWALL",
              ip_address="192.168.1.1",
              subnet="192.168.1.0/24 (DMZ Edge)",
              status="WARNING",
              latency_ms=2,
              last_ping=now_str,
              active_alerts_count=2,
              active_alerts=[
                  TopologyNodeAlert(
                      id="alt-fw-01",
                      title="Intentos de escaneo de puertos (Port Scan) desde IP externa",
                      severity="high",
                      category="Network Security",
                      observed_at=now_str,
                  ),
                  TopologyNodeAlert(
                      id="alt-fw-02",
                      title="Bloqueo de reglas de filtrado perimetral PaloAlto PA-3200",
                      severity="medium",
                      category="Firewall Rules",
                      observed_at=now_str,
                  ),
              ],
              role_description_es="Firewall perimetral inspeccionando tráfico de entrada y salida con filtrado de amenazas.",
              role_description_en="Perimeter firewall inspecting ingress/egress traffic with threat filtering.",
          ),
          TopologyNode(
              id="gtw-01",
              name="NGINX Reverse Proxy / API Gateway",
              type="GATEWAY",
              ip_address="192.168.1.50",
              subnet="192.168.1.0/24 (DMZ Edge)",
              status="ONLINE",
              latency_ms=4,
              last_ping=now_str,
              active_alerts_count=0,
              active_alerts=[],
              role_description_es="Gateway seguro terminando SSL/TLS y enrutando peticiones REST a los microservicios.",
              role_description_en="Secure gateway terminating SSL/TLS and routing REST requests to microservices.",
          ),
          TopologyNode(
              id="app-01",
              name="Cyrvanta FastAPI Application Server",
              type="SERVER",
              ip_address="10.0.4.10",
              subnet="10.0.4.0/24 (Internal Core)",
              status="ONLINE",
              latency_ms=8,
              last_ping=now_str,
              active_alerts_count=0,
              active_alerts=[],
              role_description_es="Servidor de aplicación Clean Architecture procesando lógica de negocio y contexto de seguridad.",
              role_description_en="Clean Architecture application server processing business logic and security context.",
          ),
          TopologyNode(
              id="db-01",
              name="PostgreSQL 16 Multi-Tenant RLS Cluster",
              type="DATABASE",
              ip_address="10.0.4.25",
              subnet="10.0.4.0/24 (Internal Core)",
              status="ONLINE",
              latency_ms=3,
              last_ping=now_str,
              active_alerts_count=0,
              active_alerts=[],
              role_description_es="Base de datos autoritativa relacional con seguridad por filas (Row Level Security) aislada por tenant.",
              role_description_en="Authoritative relational database with tenant-isolated Row Level Security (RLS).",
          ),
          TopologyNode(
              id="siem-01",
              name="Wazuh SIEM Manager & Connector",
              type="SIEM",
              ip_address="172.16.0.5",
              subnet="172.16.0.0/16 (SOC Infra)",
              status="WARNING",
              latency_ms=12,
              last_ping=now_str,
              active_alerts_count=1,
              active_alerts=[
                  TopologyNodeAlert(
                      id="alt-siem-01",
                      title="Regla Wazuh #5710: Múltiples fallos de autenticación SSH",
                      severity="critical",
                      category="Authentication",
                      observed_at=now_str,
                  ),
              ],
              role_description_es="Motor SIEM recopilando eventos de agentes, correlación de reglas y telemetría Wazuh.",
              role_description_en="SIEM engine collecting agent events, rule correlation, and Wazuh telemetry.",
          ),
          TopologyNode(
              id="ep-srv02",
              name="Core Active Directory / LDAP Server",
              type="ENDPOINT",
              ip_address="10.0.4.12",
              subnet="10.0.4.0/24 (Internal Core)",
              status="WARNING",
              latency_ms=15,
              last_ping=now_str,
              active_alerts_count=1,
              active_alerts=[
                  TopologyNodeAlert(
                      id="alt-ad-01",
                      title="Intento de elevación de privilegios LDAP en controlador de dominio",
                      severity="high",
                      category="Identity Security",
                      observed_at=now_str,
                  ),
              ],
              role_description_es="Servidor de identidades AD/LDAP monitoreado contra intentos de fuerza bruta.",
              role_description_en="AD/LDAP identity server monitored against brute force attempts.",
          ),
        ]

        edges = [
            TopologyEdge(
                id="edge-1",
                source_id="fw-01",
                target_id="gtw-01",
                protocol="HTTPS / TLS 1.3",
                status="NORMAL",
            ),
            TopologyEdge(
                id="edge-2",
                source_id="gtw-01",
                target_id="app-01",
                protocol="HTTP / Uvicorn ASGI",
                status="NORMAL",
            ),
            TopologyEdge(
                id="edge-3",
                source_id="app-01",
                target_id="db-01",
                protocol="PostgreSQL / asyncpg",
                status="NORMAL",
            ),
            TopologyEdge(
                id="edge-4",
                source_id="app-01",
                target_id="siem-01",
                protocol="Wazuh REST API / Syslog",
                status="DEGRADED" if active_alerts_count > 0 else "NORMAL",
            ),
            TopologyEdge(
                id="edge-5",
                source_id="siem-01",
                target_id="ep-srv02",
                protocol="Wazuh Agent / Port 1514",
                status="NORMAL",
            ),
        ]

        return NetworkTopologyResponse(
            tenant_id=tenant_id,
            nodes=nodes,
            edges=edges,
            updated_at=now_str,
        )
