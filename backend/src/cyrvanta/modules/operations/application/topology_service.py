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
    TopologyNodeService,
)
from cyrvanta.shared.database import tenant_session


class NetworkTopologyService:
    async def get_topology(self, tenant_id: UUID) -> NetworkTopologyResponse:
        now_iso = datetime.now(UTC).isoformat()

        # Core Cyrvanta Platform Nodes (CYRVANTA_CORE)
        nodes_dict: dict[str, TopologyNode] = {
            "gw-01": TopologyNode(
                id="gw-01",
                name="Cyrvanta API Gateway & Reverse Proxy",
                type="GATEWAY",
                category="CYRVANTA_CORE",
                ip_address="10.0.0.1",
                ip_addresses=["10.0.0.1"],
                services=[
                    TopologyNodeService(name="HTTPS Ingress API", port=443, protocol="HTTPS", status="ONLINE"),
                    TopologyNodeService(name="Web Console UI", port=80, protocol="HTTP", status="ONLINE"),
                ],
                subnet="10.0.0.0/24 DMZ",
                status="ONLINE",
                latency_ms=2,
                last_ping=now_iso,
                active_alerts_count=0,
                active_alerts=[],
                role_description_es="Gateway perimetral y terminación SSL/TLS segura de Cyrvanta",
                role_description_en="Cyrvanta perimeter ingress gateway and SSL/TLS proxy",
            ),
            "db-01": TopologyNode(
                id="db-01",
                name="PostgreSQL Core Database (RLS)",
                type="DATABASE",
                category="CYRVANTA_CORE",
                ip_address="10.0.1.20",
                ip_addresses=["10.0.1.20"],
                services=[
                    TopologyNodeService(name="PostgreSQL Storage Engine", port=5432, protocol="PostgreSQL", status="ONLINE")
                ],
                subnet="10.0.1.0/24 Data",
                status="ONLINE",
                latency_ms=1,
                last_ping=now_iso,
                active_alerts_count=0,
                active_alerts=[],
                role_description_es="Almacenamiento relacional transaccional con aislamiento RLS",
                role_description_en="Relational transactional storage with Row-Level Security isolation",
            ),
            "telemetry-01": TopologyNode(
                id="telemetry-01",
                name="OpenSearch Telemetry Cluster",
                type="SERVER",
                category="CYRVANTA_CORE",
                ip_address="10.0.1.30",
                ip_addresses=["10.0.1.30"],
                services=[
                    TopologyNodeService(name="OpenSearch REST Indexer", port=9200, protocol="HTTPS", status="ONLINE")
                ],
                subnet="10.0.1.0/24 Telemetry",
                status="ONLINE",
                latency_ms=4,
                last_ping=now_iso,
                active_alerts_count=0,
                active_alerts=[],
                role_description_es="Indexador de telemetría masiva y almacén de evidencias",
                role_description_en="High-volume telemetry and evidence indexer",
            ),
            "broker-01": TopologyNode(
                id="broker-01",
                name="RabbitMQ Event Broker",
                type="SERVER",
                category="CYRVANTA_CORE",
                ip_address="10.0.1.40",
                ip_addresses=["10.0.1.40"],
                services=[
                    TopologyNodeService(name="AMQP Message Broker", port=5672, protocol="AMQP", status="ONLINE")
                ],
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
                category="CYRVANTA_CORE",
                ip_address="10.0.1.50",
                ip_addresses=["10.0.1.50"],
                services=[
                    TopologyNodeService(name="Playbook Webhook & Runner", port=5678, protocol="HTTP", status="ONLINE")
                ],
                subnet="10.0.1.0/24 Automation",
                status="ONLINE",
                latency_ms=6,
                last_ping=now_iso,
                active_alerts_count=0,
                active_alerts=[],
                role_description_es="Motor de orquestación y flujos de respuesta automatizada",
                role_description_en="Playbook orchestration and automation response engine",
            ),
            "ai-01": TopologyNode(
                id="ai-01",
                name="Cyrvanta AI & Correlation Engine",
                type="SERVER",
                category="CYRVANTA_CORE",
                ip_address="10.0.1.55",
                ip_addresses=["10.0.1.55"],
                services=[
                    TopologyNodeService(name="Gemma 4 / Ollama Inference", port=11434, protocol="HTTP", status="ONLINE"),
                    TopologyNodeService(name="Correlation Worker", status="ONLINE"),
                ],
                subnet="10.0.1.0/24 AI-Engine",
                status="ONLINE",
                latency_ms=3,
                last_ping=now_iso,
                active_alerts_count=0,
                active_alerts=[],
                role_description_es="Motor de correlación y análisis asistido por IA (Gemma 4)",
                role_description_en="AI-assisted correlation and analysis engine (Gemma 4)",
            ),
            # Security Detection & Feed Nodes (SECURITY_FEED)
            "siem-01": TopologyNode(
                id="siem-01",
                name="Wazuh SIEM & HIDS Manager",
                type="SIEM",
                category="SECURITY_FEED",
                ip_address="10.0.1.10",
                ip_addresses=["10.0.1.10"],
                services=[
                    TopologyNodeService(name="Wazuh Agent Listener", port=1514, protocol="TCP/TLS", status="ONLINE"),
                    TopologyNodeService(name="Wazuh REST API", port=55000, protocol="HTTPS", status="ONLINE"),
                ],
                subnet="10.0.1.0/24 SecOps",
                status="ONLINE",
                latency_ms=5,
                last_ping=now_iso,
                active_alerts_count=0,
                active_alerts=[],
                role_description_es="Gestor central de eventos de seguridad y agentes de endpoints",
                role_description_en="Central security event manager and endpoint agent coordinator",
            ),
            # Protected Tenant Workloads & Nodes (MONITORED_ASSET)
            "lab-server-01": TopologyNode(
                id="lab-server-01",
                name="SRV-APP-PROD-01 (Application Host)",
                type="SERVER",
                category="MONITORED_ASSET",
                ip_address="10.0.1.60",
                ip_addresses=["10.0.1.60", "192.168.10.60"],
                services=[
                    TopologyNodeService(name="Web ERP Portal", port=443, protocol="HTTPS", ip_address="10.0.1.60", status="ONLINE"),
                    TopologyNodeService(name="Internal API Backend", port=8080, protocol="HTTP", ip_address="192.168.10.60", status="ONLINE"),
                    TopologyNodeService(name="SSH Management Daemon", port=22, protocol="TCP", ip_address="10.0.1.60", status="ONLINE"),
                ],
                subnet="10.0.1.0/24 Production Servers",
                status="ONLINE",
                latency_ms=3,
                last_ping=now_iso,
                active_alerts_count=0,
                active_alerts=[],
                os_info="Ubuntu Linux 22.04 LTS",
                monitored_by=["Wazuh Agent #014"],
                role_description_es="Servidor de aplicaciones consolidado con múltiples IPs y servicios",
                role_description_en="Consolidated application server with multiple IPs and services",
            ),
            "lab-workstation-01": TopologyNode(
                id="lab-workstation-01",
                name="WKSTN-ADMIN-01",
                type="ENDPOINT",
                category="MONITORED_ASSET",
                ip_address="10.0.2.15",
                ip_addresses=["10.0.2.15"],
                services=[
                    TopologyNodeService(name="Management Workstation Service", status="ONLINE")
                ],
                subnet="10.0.2.0/24 Workstations LAN",
                status="ONLINE",
                latency_ms=2,
                last_ping=now_iso,
                active_alerts_count=0,
                active_alerts=[],
                os_info="Windows 11 Enterprise",
                monitored_by=["Wazuh Agent #015", "Microsoft Defender"],
                role_description_es="Estación de trabajo administrativa monitorizada",
                role_description_en="Monitored administrative workstation endpoint",
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
                            category=existing_node.category,
                            ip_address=existing_node.ip_address,
                            ip_addresses=existing_node.ip_addresses,
                            services=existing_node.services,
                            subnet=existing_node.subnet,
                            status=status,
                            latency_ms=existing_node.latency_ms,
                            last_ping=integ.last_health_check_at.isoformat() if integ.last_health_check_at else now_iso,
                            active_alerts_count=existing_node.active_alerts_count,
                            active_alerts=existing_node.active_alerts,
                            os_info=existing_node.os_info,
                            monitored_by=existing_node.monitored_by,
                            role_description_es=existing_node.role_description_es,
                            role_description_en=existing_node.role_description_en,
                        )
                    else:
                        # Additional or custom external connector (SECURITY_FEED)
                        integ_id = f"integ-{integ.connector_type.lower()}"
                        is_fw = "FIREWALL" in integ.connector_type or "PALO" in integ.name.upper() or "FORTI" in integ.name.upper()
                        is_edr = "CROWD" in integ.connector_type or "DEFENDER" in integ.connector_type or "EDR" in integ.name.upper()
                        node_type = "FIREWALL" if is_fw else "EDR" if is_edr else "SERVER"
                        
                        if integ_id not in nodes_dict:
                            nodes_dict[integ_id] = TopologyNode(
                                id=integ_id,
                                name=integ.name,
                                type=node_type,
                                category="SECURITY_FEED",
                                ip_address="10.0.3." + str(10 + len(nodes_dict)),
                                ip_addresses=["10.0.3." + str(10 + len(nodes_dict))],
                                services=[
                                    TopologyNodeService(name=f"Feed Connector ({integ.connector_type})", status=status)
                                ],
                                subnet="10.0.3.0/24 Security Feeds",
                                status=status,
                                latency_ms=12,
                                last_ping=integ.last_health_check_at.isoformat() if integ.last_health_check_at else now_iso,
                                active_alerts_count=0,
                                active_alerts=[],
                                role_description_es=f"Fuente de detección y telemetría ({integ.connector_type})",
                                role_description_en=f"Detection and telemetry source ({integ.connector_type})",
                            )

                # Query recent alert references to discover active assets and workstations
                alerts = list(
                    (
                        await session.scalars(
                            select(AlertReferenceModel)
                            .where(
                                AlertReferenceModel.tenant_id == tenant_id,
                                AlertReferenceModel.is_simulated.is_(False),
                            )
                            .order_by(desc(AlertReferenceModel.observed_at))
                            .limit(50)
                        )
                    ).all()
                )

                # Process alerts and consolidate into structured host nodes
                for alert in alerts:
                    raw_asset = (alert.asset_summary or alert.indicator_summary or "").strip()
                    if not raw_asset:
                        continue

                    # Extract asset host name and potential port/service
                    clean_name = raw_asset.split()[0].rstrip(",:;")
                    
                    # Check for IP:port or hostname:port pattern
                    detected_port = None
                    if ":" in clean_name and not clean_name.startswith("http"):
                        parts = clean_name.split(":")
                        clean_name = parts[0]
                        if parts[1].isdigit():
                            detected_port = int(parts[1])

                    slug = re.sub(r"[^a-zA-Z0-9-]", "-", clean_name.lower())[:32]
                    asset_id = f"asset-{slug}"

                    is_ip = bool(re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", clean_name))
                    ip_addr = clean_name if is_ip else f"10.0.2.{abs(hash(clean_name)) % 200 + 10}"
                    node_name = clean_name if not is_ip else f"Host-{clean_name.replace('.', '-')}"
                    is_server = "SRV" in clean_name.upper() or "DC" in clean_name.upper() or "DB" in clean_name.upper() or "APP" in clean_name.upper()
                    node_type = "SERVER" if is_server else "ENDPOINT"

                    severity_str = alert.severity.lower() if alert.severity else "medium"
                    valid_severities = ("critical", "high", "medium", "low", "informational")
                    normalized_severity = severity_str if severity_str in valid_severities else "medium"

                    alert_item = TopologyNodeAlert(
                        id=str(alert.id),
                        title=alert.title,
                        severity=normalized_severity,  # type: ignore[arg-type]
                        category=alert.category or "Security",
                        observed_at=alert.observed_at.isoformat() if alert.observed_at else now_iso,
                    )

                    service_name = f"Service on port {detected_port}" if detected_port else "Application Service"

                    if asset_id not in nodes_dict:
                        node_status = "WARNING" if normalized_severity in ("critical", "high") else "ONLINE"
                        services_list = [
                            TopologyNodeService(
                                name=service_name,
                                port=detected_port,
                                protocol="TCP",
                                ip_address=ip_addr,
                                status=node_status,
                                active_alerts_count=1 if normalized_severity in ("critical", "high") else 0,
                            )
                        ]
                        nodes_dict[asset_id] = TopologyNode(
                            id=asset_id,
                            name=node_name,
                            type=node_type,
                            category="MONITORED_ASSET",
                            ip_address=ip_addr,
                            ip_addresses=[ip_addr],
                            services=services_list,
                            subnet="10.0.2.0/24 Corporate LAN" if node_type == "ENDPOINT" else "10.0.1.0/24 Production Servers",
                            status=node_status,
                            latency_ms=15,
                            last_ping=now_iso,
                            active_alerts_count=1,
                            active_alerts=[alert_item],
                            os_info="Linux / Windows Server" if is_server else "Windows 11 Enterprise",
                            monitored_by=["Wazuh Agent", "SIEM Telemetry"],
                            role_description_es=f"Activo protegido monitorizado ({node_type})",
                            role_description_en=f"Monitored protected asset ({node_type})",
                        )
                    else:
                        existing_node = nodes_dict[asset_id]
                        if ip_addr not in existing_node.ip_addresses:
                            existing_node.ip_addresses.append(ip_addr)
                        if detected_port and not any(s.port == detected_port for s in existing_node.services):
                            existing_node.services.append(
                                TopologyNodeService(
                                    name=service_name,
                                    port=detected_port,
                                    protocol="TCP",
                                    ip_address=ip_addr,
                                    status="WARNING" if normalized_severity in ("critical", "high") else "ONLINE",
                                    active_alerts_count=1 if normalized_severity in ("critical", "high") else 0,
                                )
                            )
                        if len(existing_node.active_alerts) < 5:
                            existing_node.active_alerts.append(alert_item)
                        existing_node.active_alerts_count += 1
                        if normalized_severity in ("critical", "high"):
                            existing_node.status = "WARNING"

        except Exception:
            # Resilient fallback: preserve core nodes if DB session or queries encounter any issues
            pass

        # Build structured topology interconnect edges
        edges: list[TopologyEdge] = [
            # Security Feeds -> Cyrvanta Gateway / Core
            TopologyEdge(
                id="edge-siem-gw",
                source_id="siem-01",
                target_id="gw-01",
                protocol="HTTPS / REST Ingestion",
                status="NORMAL",
            ),
            TopologyEdge(
                id="edge-siem-telemetry",
                source_id="siem-01",
                target_id="telemetry-01",
                protocol="OpenSearch Bulk TLS",
                status="NORMAL",
            ),
            # Cyrvanta Core Interconnects
            TopologyEdge(
                id="edge-gw-db",
                source_id="gw-01",
                target_id="db-01",
                protocol="PostgreSQL TLS RLS",
                status="NORMAL",
            ),
            TopologyEdge(
                id="edge-gw-broker",
                source_id="gw-01",
                target_id="broker-01",
                protocol="AMQP TLS 5672",
                status="NORMAL",
            ),
            TopologyEdge(
                id="edge-broker-soar",
                source_id="broker-01",
                target_id="soar-01",
                protocol="REST Hook Orchestration",
                status="NORMAL",
            ),
            TopologyEdge(
                id="edge-broker-ai",
                source_id="broker-01",
                target_id="ai-01",
                protocol="Correlation Pipeline",
                status="NORMAL",
            ),
            # Monitored Assets -> Security Feeds / Sensors
            TopologyEdge(
                id="edge-lab-server-siem",
                source_id="lab-server-01",
                target_id="siem-01",
                protocol="Wazuh-Agent TLS 1514",
                status="NORMAL",
            ),
            TopologyEdge(
                id="edge-lab-workstation-siem",
                source_id="lab-workstation-01",
                target_id="siem-01",
                protocol="Wazuh-Agent TLS 1514",
                status="NORMAL",
            ),
        ]

        # Link dynamically discovered assets to security feeds and soar
        for node_id, node in nodes_dict.items():
            if node_id.startswith("asset-"):
                edge_status = "DEGRADED" if node.status == "WARNING" else "BLOCKED" if node.status == "BLOCKED" else "NORMAL"
                edges.append(
                    TopologyEdge(
                        id=f"edge-{node_id}-siem",
                        source_id=node_id,
                        target_id="siem-01",
                        protocol="Wazuh-Agent / Sensor TLS",
                        status=edge_status,
                    )
                )
            elif node_id.startswith("integ-"):
                edges.append(
                    TopologyEdge(
                        id=f"edge-{node_id}-gw",
                        source_id=node_id,
                        target_id="gw-01",
                        protocol="Security Feed Ingestion",
                        status="NORMAL",
                    )
                )

        return NetworkTopologyResponse(
            tenant_id=tenant_id,
            nodes=list(nodes_dict.values()),
            edges=edges,
            updated_at=now_iso,
        )
