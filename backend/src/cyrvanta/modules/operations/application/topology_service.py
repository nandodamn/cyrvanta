from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import desc, select

from cyrvanta.modules.incident.infrastructure.models import AlertReferenceModel, IncidentModel
from cyrvanta.modules.integrations.infrastructure.models import IntegrationModel
from cyrvanta.modules.operations.application.schemas import (
    NetworkTopologyResponse,
    TopologyEdge,
    TopologyNode,
    TopologyNodeAlert,
)
from cyrvanta.shared.database import tenant_session


class NetworkTopologyService:
    async def get_topology(self, tenant_id: UUID) -> NetworkTopologyResponse:
        now_iso = datetime.now(UTC).isoformat()

        # Core security stack nodes
        nodes_dict: dict[str, TopologyNode] = {
            "gw-01": TopologyNode(
                id="gw-01",
                name="Gateway Ingress / Reverse Proxy",
                type="GATEWAY",
                ip_address="10.0.0.1",
                subnet="10.0.0.0/24 DMZ",
                status="ONLINE",
                latency_ms=2,
                last_ping=now_iso,
                active_alerts_count=0,
                active_alerts=[],
                role_description_es="Gateway perimetral y terminación SSL/TLS segura",
                role_description_en="Perimeter ingress gateway and SSL/TLS proxy",
            ),
            "siem-01": TopologyNode(
                id="siem-01",
                name="Wazuh SIEM Manager",
                type="SIEM",
                ip_address="10.0.1.10",
                subnet="10.0.1.0/24 SecOps",
                status="ONLINE",
                latency_ms=5,
                last_ping=now_iso,
                active_alerts_count=0,
                active_alerts=[],
                role_description_es="Gestor central de eventos de seguridad y agentes",
                role_description_en="Central security event manager and agent coordinator",
            ),
            "db-01": TopologyNode(
                id="db-01",
                name="PostgreSQL Core Database",
                type="DATABASE",
                ip_address="10.0.1.20",
                subnet="10.0.1.0/24 Data",
                status="ONLINE",
                latency_ms=1,
                last_ping=now_iso,
                active_alerts_count=0,
                active_alerts=[],
                role_description_es="Almacenamiento relacional con aislamiento RLS",
                role_description_en="Relational storage with Row-Level Security isolation",
            ),
            "telemetry-01": TopologyNode(
                id="telemetry-01",
                name="OpenSearch Telemetry Cluster",
                type="SERVER",
                ip_address="10.0.1.30",
                subnet="10.0.1.0/24 Telemetry",
                status="ONLINE",
                latency_ms=4,
                last_ping=now_iso,
                active_alerts_count=0,
                active_alerts=[],
                role_description_es="Indexador de telemetría masiva y evidencias",
                role_description_en="High-volume telemetry and evidence indexer",
            ),
            "broker-01": TopologyNode(
                id="broker-01",
                name="RabbitMQ Event Broker",
                type="SERVER",
                ip_address="10.0.1.40",
                subnet="10.0.1.0/24 MessageBus",
                status="ONLINE",
                latency_ms=3,
                last_ping=now_iso,
                active_alerts_count=0,
                active_alerts=[],
                role_description_es="Broker de mensajería asíncrona de eventos SOC",
                role_description_en="Asynchronous message broker for SOC events",
            ),
            "soar-01": TopologyNode(
                id="soar-01",
                name="n8n Automation Engine",
                type="SERVER",
                ip_address="10.0.1.50",
                subnet="10.0.1.0/24 Automation",
                status="ONLINE",
                latency_ms=6,
                last_ping=now_iso,
                active_alerts_count=0,
                active_alerts=[],
                role_description_es="Motor de orquestación y flujos de respuesta",
                role_description_en="Playbook orchestration and automation workflows",
            ),
        }

        # Query configured integrations for this tenant
        try:
            async with tenant_session(tenant_id) as session:
                integrations = list(
                    (
                        await session.scalars(
                            select(IntegrationModel)
                            .where(IntegrationModel.tenant_id == tenant_id)
                            .order_by(IntegrationModel.name)
                        )
                    ).all()
                )

                # Map core stack integrations to base nodes to keep topology unified and updated
                mapped_core_types = {
                    "WAZUH": "siem-01",
                    "OPENSEARCH": "telemetry-01",
                    "N8N": "soar-01",
                }

                for integ in integrations:
                    status = "ONLINE" if integ.status in ("active", "healthy") else "WARNING" if integ.status == "pending_verification" else "OFFLINE"
                    target_base_node = mapped_core_types.get(integ.connector_type)

                    if target_base_node and target_base_node in nodes_dict:
                        # Enrich existing stack node with real tenant integration state
                        existing_node = nodes_dict[target_base_node]
                        nodes_dict[target_base_node] = TopologyNode(
                            id=existing_node.id,
                            name=integ.name,
                            type=existing_node.type,
                            ip_address=existing_node.ip_address,
                            subnet=existing_node.subnet,
                            status=status,
                            latency_ms=existing_node.latency_ms,
                            last_ping=integ.last_health_check_at.isoformat() if integ.last_health_check_at else now_iso,
                            active_alerts_count=existing_node.active_alerts_count,
                            active_alerts=existing_node.active_alerts,
                            role_description_es=existing_node.role_description_es,
                            role_description_en=existing_node.role_description_en,
                        )
                    else:
                        # Additional or custom external connector
                        integ_id = f"integ-{integ.connector_type.lower()}"
                        node_type = "FIREWALL" if "FIREWALL" in integ.connector_type or "PALO" in integ.name.upper() else "SERVER"
                        if integ_id not in nodes_dict:
                            nodes_dict[integ_id] = TopologyNode(
                                id=integ_id,
                                name=integ.name,
                                type=node_type,
                                ip_address="10.0.3." + str(10 + len(nodes_dict)),
                                subnet="10.0.3.0/24 Integrations",
                                status=status,
                                latency_ms=12,
                                last_ping=integ.last_health_check_at.isoformat() if integ.last_health_check_at else now_iso,
                                active_alerts_count=0,
                                active_alerts=[],
                                role_description_es=f"Conector de integración {integ.connector_type}",
                                role_description_en=f"Integration connector {integ.connector_type}",
                            )

                # Query recent alert references to discover active assets and workstations
                alerts = list(
                    (
                        await session.scalars(
                            select(AlertReferenceModel)
                            .where(AlertReferenceModel.tenant_id == tenant_id)
                            .order_by(desc(AlertReferenceModel.observed_at))
                            .limit(50)
                        )
                    ).all()
                )

                # Process alerts for dynamic asset nodes
                for alert in alerts:
                    raw_asset = (alert.asset_summary or alert.indicator_summary or "").strip()
                    if not raw_asset:
                        continue

                    # Clean asset name
                    clean_name = raw_asset.split()[0].rstrip(",:;")
                    slug = re.sub(r"[^a-zA-Z0-9-]", "-", clean_name.lower())[:32]
                    asset_id = f"asset-{slug}"

                    is_ip = bool(re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", clean_name))
                    ip_addr = clean_name if is_ip else f"10.0.2.{abs(hash(clean_name)) % 200 + 10}"
                    node_name = clean_name if not is_ip else f"Host-{clean_name.replace('.', '-')}"
                    is_server = "SRV" in clean_name.upper() or "DC" in clean_name.upper() or "DB" in clean_name.upper()
                    node_type = "SERVER" if is_server else "ENDPOINT"

                    severity_str = alert.severity.lower() if alert.severity else "medium"
                    valid_severities = ("critical", "high", "medium", "low", "informational")
                    normalized_severity = severity_str if severity_str in valid_severities else "medium"

                    alert_item = TopologyNodeAlert(
                        id=str(alert.id),
                        title=alert.title,
                        severity=normalized_severity, # type: ignore[arg-type]
                        category=alert.category or "Security",
                        observed_at=alert.observed_at.isoformat() if alert.observed_at else now_iso,
                    )

                    if asset_id not in nodes_dict:
                        node_status = "WARNING" if normalized_severity in ("critical", "high") else "ONLINE"
                        nodes_dict[asset_id] = TopologyNode(
                            id=asset_id,
                            name=node_name,
                            type=node_type,
                            ip_address=ip_addr,
                            subnet="10.0.2.0/24 Corporate LAN" if node_type == "ENDPOINT" else "10.0.1.0/24 Servers",
                            status=node_status,
                            latency_ms=15,
                            last_ping=now_iso,
                            active_alerts_count=1,
                            active_alerts=[alert_item],
                            role_description_es=f"Activo monitorizado en telemetría ({node_type})",
                            role_description_en=f"Monitored telemetry asset ({node_type})",
                        )
                    else:
                        existing_node = nodes_dict[asset_id]
                        if len(existing_node.active_alerts) < 5:
                            existing_node.active_alerts.append(alert_item)
                        existing_node.active_alerts_count += 1
                        if normalized_severity in ("critical", "high"):
                            existing_node.status = "WARNING"

        except Exception:
            # Resilient fallback: preserve core nodes if DB session or queries encounter any issues
            pass

        # Build dynamic topology edges
        edges: list[TopologyEdge] = [
            TopologyEdge(
                id="edge-gw-siem",
                source_id="gw-01",
                target_id="siem-01",
                protocol="HTTPS / TLS 1.3",
                status="NORMAL",
            ),
            TopologyEdge(
                id="edge-gw-db",
                source_id="gw-01",
                target_id="db-01",
                protocol="PostgreSQL TLS",
                status="NORMAL",
            ),
            TopologyEdge(
                id="edge-siem-telemetry",
                source_id="siem-01",
                target_id="telemetry-01",
                protocol="OpenSearch REST",
                status="NORMAL",
            ),
            TopologyEdge(
                id="edge-gw-broker",
                source_id="gw-01",
                target_id="broker-01",
                protocol="AMQP TLS",
                status="NORMAL",
            ),
            TopologyEdge(
                id="edge-broker-soar",
                source_id="broker-01",
                target_id="soar-01",
                protocol="REST Hook",
                status="NORMAL",
            ),
        ]

        # Link discovered assets to SIEM and Gateway
        for node_id, node in nodes_dict.items():
            if node_id.startswith("asset-"):
                edge_status = "DEGRADED" if node.status == "WARNING" else "BLOCKED" if node.status == "BLOCKED" else "NORMAL"
                edges.append(
                    TopologyEdge(
                        id=f"edge-{node_id}-siem",
                        source_id=node_id,
                        target_id="siem-01",
                        protocol="Wazuh-Agent TLS",
                        status=edge_status,
                    )
                )
            elif node_id.startswith("integ-"):
                edges.append(
                    TopologyEdge(
                        id=f"edge-soar-{node_id}",
                        source_id="soar-01",
                        target_id=node_id,
                        protocol="API Connector",
                        status="NORMAL",
                    )
                )

        return NetworkTopologyResponse(
            tenant_id=tenant_id,
            nodes=list(nodes_dict.values()),
            edges=edges,
            updated_at=now_iso,
        )
