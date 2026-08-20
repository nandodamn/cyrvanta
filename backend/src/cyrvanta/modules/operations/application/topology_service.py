from __future__ import annotations

import asyncio
import logging
import socket
import time
from datetime import UTC, datetime
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from sqlalchemy import desc, select, text
from sqlalchemy.exc import SQLAlchemyError

from cyrvanta.modules.incident.infrastructure.models import AlertReferenceModel
from cyrvanta.modules.integrations.application.connection_service import (
    IntegrationConfigurationError,
    IntegrationConnectionService,
)
from cyrvanta.modules.integrations.infrastructure.models import IntegrationModel
from cyrvanta.modules.operations.application.schemas import (
    NetworkTopologyResponse,
    TopologyEdge,
    TopologyNode,
    TopologyNodeAlert,
    TopologyNodeService,
)
from cyrvanta.shared.config import Settings, get_settings
from cyrvanta.shared.database import SessionFactory, tenant_session

logger = logging.getLogger("cyrvanta.operations.topology")

_PROBE_TIMEOUT_SECONDS = 3.0
# Listing the manager's agents is a real API query, not a reachability probe: it
# authenticates and then reads the agent inventory, which routinely takes longer
# than the probe budget. It gets the connector's own configured timeout instead.
_DEFAULT_WAZUH_TIMEOUT_SECONDS = 10
_MIN_WAZUH_TIMEOUT_SECONDS = 1
_MAX_WAZUH_TIMEOUT_SECONDS = 30
_VALID_SEVERITIES = ("critical", "high", "medium", "low", "informational")

# How far back the map looks. One noisy host can produce hundreds of alerts in
# a row, so a small window would attribute everything to it and report zero for
# every other asset -- the map would show quiet hosts that are not quiet.
_ALERT_SCAN_LIMIT = 1000

# Distinct titles listed per node. The count above the list is not capped by it.
_ALERTS_PER_NODE = 5
# Connectors this platform runs as its own dependency and already probes in
# _core_nodes. They are not detection sources, so the security-feed zone must
# not list them: n8n executes playbooks and Ollama drafts wording, neither
# reports findings.
_CORE_REPRESENTED_CONNECTORS = frozenset({"OPENSEARCH", "N8N", "OLLAMA"})


class _Probe:
    """Result of a real reachability check against one dependency."""

    __slots__ = ("reachable", "latency_ms", "address", "detail")

    def __init__(
        self,
        *,
        reachable: bool,
        latency_ms: int | None,
        address: str | None,
        detail: str,
    ) -> None:
        self.reachable = reachable
        self.latency_ms = latency_ms
        self.address = address
        self.detail = detail


async def _resolve(host: str) -> str | None:
    """Resolve a hostname to its real address, or None when it does not resolve."""
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(
            host, None, family=socket.AF_INET, type=socket.SOCK_STREAM
        )
    except (socket.gaierror, OSError):
        return None
    return infos[0][4][0] if infos else None


async def _probe_tcp(host: str, port: int) -> _Probe:
    """Open a real TCP connection and measure the real round trip."""
    address = await _resolve(host)
    started = time.perf_counter()
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=_PROBE_TIMEOUT_SECONDS
        )
    except (TimeoutError, OSError):
        return _Probe(reachable=False, latency_ms=None, address=address, detail="unreachable")
    latency_ms = max(1, round((time.perf_counter() - started) * 1000))
    writer.close()
    try:
        await writer.wait_closed()
    except OSError:
        pass
    return _Probe(reachable=True, latency_ms=latency_ms, address=address, detail=f"tcp/{port}")


async def _probe_http(url: str) -> _Probe:
    """Issue a real HTTP request and measure the real round trip."""
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    address = await _resolve(host) if host else None
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=_PROBE_TIMEOUT_SECONDS, verify=True) as client:
            response = await client.get(url)
    except httpx.HTTPError:
        return _Probe(reachable=False, latency_ms=None, address=address, detail="unreachable")
    latency_ms = max(1, round((time.perf_counter() - started) * 1000))
    return _Probe(
        reachable=response.is_success,
        latency_ms=latency_ms,
        address=address,
        detail=f"HTTP {response.status_code}",
    )


async def _probe_database() -> _Probe:
    """Run a real query on the application's own pool and measure it."""
    settings = get_settings()
    host = urlsplit(settings.database_url).hostname or "postgres"
    address = await _resolve(host)
    started = time.perf_counter()
    try:
        async with SessionFactory() as session:
            await asyncio.wait_for(
                session.execute(text("SELECT 1")), timeout=_PROBE_TIMEOUT_SECONDS
            )
    except (TimeoutError, SQLAlchemyError, OSError):
        return _Probe(reachable=False, latency_ms=None, address=address, detail="query failed")
    latency_ms = max(1, round((time.perf_counter() - started) * 1000))
    return _Probe(reachable=True, latency_ms=latency_ms, address=address, detail="SELECT 1")


def _resolve_wazuh_timeout(configured: object) -> int:
    """Clamp the connector's configured timeout the same way integrations do."""
    try:
        timeout = int(configured)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return _DEFAULT_WAZUH_TIMEOUT_SECONDS
    if isinstance(configured, bool):
        return _DEFAULT_WAZUH_TIMEOUT_SECONDS
    return min(_MAX_WAZUH_TIMEOUT_SECONDS, max(_MIN_WAZUH_TIMEOUT_SECONDS, timeout))


def _subnet_of(address: str | None) -> str:
    if not address:
        return "unresolved"
    octets = address.split(".")
    if len(octets) != 4:
        return "unresolved"
    return f"{'.'.join(octets[:3])}.0/24"


class NetworkTopologyService:
    """Live view of what is actually connected to Cyrvanta, and of Cyrvanta itself.

    Every node, address, latency and status in this projection comes from a real
    measurement taken when the request is served:

    * Cyrvanta's own dependencies are resolved by DNS and probed over TCP/HTTP.
    * Monitored assets are the agents the Wazuh manager actually reports.
    * Security feeds are the tenant's configured integration rows.

    Nothing is invented: an unresolved address reads "unresolved", an unmeasured
    latency stays ``None``, and a dependency that does not answer is ``OFFLINE``.
    A host this platform cannot see does not appear at all.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def get_topology(self, tenant_id: UUID) -> NetworkTopologyResponse:
        now_iso = datetime.now(UTC).isoformat()
        core_nodes = await self._core_nodes(now_iso)
        feed_nodes, wazuh_configured = await self._feed_nodes(tenant_id, now_iso)
        asset_nodes = await self._monitored_assets(tenant_id, now_iso)
        await self._annotate_alerts(tenant_id, asset_nodes, now_iso)

        nodes = [*core_nodes.values(), *feed_nodes.values(), *asset_nodes.values()]
        edges = self._edges(core_nodes, feed_nodes, asset_nodes, wazuh_configured)
        return NetworkTopologyResponse(
            tenant_id=tenant_id, nodes=nodes, edges=edges, updated_at=now_iso
        )

    # ── Cyrvanta itself ────────────────────────────────────────────────────────

    async def _core_nodes(self, now_iso: str) -> dict[str, TopologyNode]:
        """Probe each dependency this backend is actually configured to use."""
        database = urlsplit(self.settings.database_url)
        redis = urlsplit(self.settings.redis_url)
        rabbit = urlsplit(self.settings.rabbitmq_url)

        specs: list[tuple[str, str, str, str, str, str, str]] = [
            # id, display name, type, host, port/url, role_es, role_en
            (
                "db-01",
                "PostgreSQL (sistema de registro)",
                "DATABASE",
                database.hostname or "postgres",
                str(database.port or 5432),
                "Almacenamiento transaccional con aislamiento RLS por tenant",
                "Transactional store with per-tenant Row-Level Security",
            ),
            (
                "cache-01",
                "Redis (sesiones y locks)",
                "SERVER",
                redis.hostname or "redis",
                str(redis.port or 6379),
                "Cache de sesión y coordinación de locks distribuidos",
                "Session cache and distributed lock coordination",
            ),
            (
                "broker-01",
                "RabbitMQ (bus de eventos)",
                "SERVER",
                rabbit.hostname or "rabbitmq",
                str(rabbit.port or 5672),
                "Bus asíncrono de eventos de dominio con outbox/inbox",
                "Asynchronous domain event bus with outbox/inbox delivery",
            ),
        ]

        # PostgreSQL is checked by actually running a query on the pool the
        # application uses: proving the port is open would not prove the system
        # of record answers. The other two are checked at the transport level.
        probes = await asyncio.gather(
            _probe_database(),
            *(_probe_tcp(host, int(port)) for _, _, _, host, port, _, _ in specs[1:]),
        )

        nodes: dict[str, TopologyNode] = {}
        for (node_id, name, node_type, host, port, role_es, role_en), probe in zip(
            specs, probes, strict=True
        ):
            nodes[node_id] = self._node(
                node_id=node_id,
                name=name,
                node_type=node_type,
                category="CYRVANTA_CORE",
                probe=probe,
                host=host,
                services=[
                    TopologyNodeService(
                        name=name.split(" (")[0],
                        port=int(port),
                        protocol="TCP",
                        status="ONLINE" if probe.reachable else "OFFLINE",
                    )
                ],
                now_iso=now_iso,
                role_es=role_es,
                role_en=role_en,
            )

        # Optional dependencies: only shown when this deployment actually enables
        # them, so the map never advertises a capability that is switched off.
        optional: list[tuple[str, str, str, str, str, str, str]] = []
        if self.settings.opensearch_mode == "live":
            optional.append(
                (
                    "telemetry-01",
                    "OpenSearch (telemetría)",
                    "SERVER",
                    f"{self.settings.opensearch_url}/_cluster/health",
                    self.settings.opensearch_url,
                    "Índice de telemetría y evidencia de alto volumen",
                    "High-volume telemetry and evidence index",
                )
            )
        if self.settings.n8n_mode == "live":
            optional.append(
                (
                    "soar-01",
                    "n8n (motor externo opcional)",
                    "SERVER",
                    f"{self.settings.n8n_base_url}/healthz",
                    self.settings.n8n_base_url,
                    "Motor de automatización externo, opcional por binding",
                    "External automation engine, optional per binding",
                )
            )
        if self.settings.ollama_mode == "live":
            optional.append(
                (
                    "ai-01",
                    "Ollama (redacción asistida)",
                    "SERVER",
                    f"{self.settings.ollama_base_url}/api/tags",
                    self.settings.ollama_base_url,
                    "Modelo local de redacción; nunca autoriza ni ejecuta",
                    "Local drafting model; never authorizes nor executes",
                )
            )

        if optional:
            opt_probes = await asyncio.gather(
                *(_probe_http(url) for _, _, _, url, _, _, _ in optional)
            )
            for (node_id, name, node_type, _, base_url, role_es, role_en), probe in zip(
                optional, opt_probes, strict=True
            ):
                parsed = urlsplit(base_url)
                nodes[node_id] = self._node(
                    node_id=node_id,
                    name=name,
                    node_type=node_type,
                    category="CYRVANTA_CORE",
                    probe=probe,
                    host=parsed.hostname or base_url,
                    services=[
                        TopologyNodeService(
                            name=name.split(" (")[0],
                            port=parsed.port,
                            protocol=(parsed.scheme or "http").upper(),
                            status="ONLINE" if probe.reachable else "OFFLINE",
                        )
                    ],
                    now_iso=now_iso,
                    role_es=role_es,
                    role_en=role_en,
                )
        return nodes

    def _node(
        self,
        *,
        node_id: str,
        name: str,
        node_type: str,
        category: str,
        probe: _Probe,
        host: str,
        services: list[TopologyNodeService],
        now_iso: str,
        role_es: str,
        role_en: str,
        os_info: str | None = None,
        monitored_by: list[str] | None = None,
    ) -> TopologyNode:
        address = probe.address or host
        return TopologyNode(
            id=node_id,
            name=name,
            type=node_type,  # type: ignore[arg-type]
            category=category,  # type: ignore[arg-type]
            ip_address=address,
            ip_addresses=[address],
            services=services,
            subnet=_subnet_of(probe.address),
            status="ONLINE" if probe.reachable else "OFFLINE",
            latency_ms=probe.latency_ms,
            last_ping=now_iso,
            active_alerts_count=0,
            active_alerts=[],
            os_info=os_info,
            monitored_by=monitored_by or [],
            role_description_es=role_es,
            role_description_en=role_en,
        )

    # ── Configured detection sources ───────────────────────────────────────────

    async def _feed_nodes(
        self, tenant_id: UUID, now_iso: str
    ) -> tuple[dict[str, TopologyNode], bool]:
        """One node per integration row the tenant actually has configured."""
        nodes: dict[str, TopologyNode] = {}
        wazuh_configured = False
        async with tenant_session(tenant_id) as session:
            integrations = list(
                (
                    await session.scalars(
                        select(IntegrationModel)
                        .where(IntegrationModel.tenant_id == tenant_id)
                        .order_by(IntegrationModel.connector_type)
                    )
                ).all()
            )

        for integration in integrations:
            connector = integration.connector_type.upper()
            if connector in _CORE_REPRESENTED_CONNECTORS:
                # Drawing these here would put the same system on the map twice,
                # once probed as a core dependency and once as a configuration
                # row, with two different statuses for one service.
                continue
            if connector == "WAZUH":
                wazuh_configured = True
            node_id = f"integ-{connector.lower()}"
            # "Enabled" is not "working": a connector that never passed a health
            # check cannot be used by any action, so the map must not paint it
            # online just because a row says active.
            verified = (
                integration.status == "active"
                and integration.last_error_code is None
                and integration.last_health_check_at is not None
            )
            node_type = "SIEM" if connector == "WAZUH" else "SERVER"
            nodes[node_id] = TopologyNode(
                id=node_id,
                name=integration.name,
                type=node_type,  # type: ignore[arg-type]
                category="SECURITY_FEED",
                ip_address=connector.lower(),
                ip_addresses=[],
                services=[
                    TopologyNodeService(
                        name=f"{connector} connector",
                        protocol="HTTPS",
                        status="ONLINE" if verified else "OFFLINE",
                    )
                ],
                subnet="integración configurada",
                status="ONLINE" if verified else "OFFLINE",
                latency_ms=None,
                last_ping=(
                    integration.last_health_check_at.isoformat()
                    if integration.last_health_check_at
                    else now_iso
                ),
                active_alerts_count=0,
                active_alerts=[],
                monitored_by=[],
                role_description_es=(
                    f"Fuente de detección configurada ({connector})"
                    if verified
                    else f"Configurada sin verificar ({connector}): falta un health check correcto"
                ),
                role_description_en=(
                    f"Configured detection source ({connector})"
                    if verified
                    else f"Configured but unverified ({connector}): "
                    "a successful health check is missing"
                ),
            )
        return nodes, wazuh_configured

    # ── Assets Cyrvanta can actually see ───────────────────────────────────────

    async def _monitored_assets(self, tenant_id: UUID, now_iso: str) -> dict[str, TopologyNode]:
        """The agents the Wazuh manager really reports -- never a synthesised host."""
        if self.settings.wazuh_mode != "live":
            return {}
        try:
            credential = await IntegrationConnectionService(self.settings).resolve_single_connector(
                tenant_id, "WAZUH"
            )
        except IntegrationConfigurationError as error:
            # An unusable connector means the map genuinely cannot see any asset,
            # but staying silent made an empty map indistinguishable from a
            # tenant that monitors nothing.
            logger.warning(
                "topology: no usable Wazuh connector for tenant %s: %s",
                tenant_id,
                error,
            )
            return {}

        values = credential.values
        base_url = str(values.get("base_url", "")).rstrip("/")
        if not base_url:
            logger.warning("topology: Wazuh connector for tenant %s has no base_url", tenant_id)
            return {}
        timeout_seconds = _resolve_wazuh_timeout(values.get("timeout_seconds"))
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds, verify=True) as client:
                token_response = await client.get(
                    f"{base_url}/security/user/authenticate?raw=true",
                    auth=(str(values.get("username", "")), str(values.get("password", ""))),
                )
                token_response.raise_for_status()
                agents_response = await client.get(
                    f"{base_url}/agents",
                    headers={"Authorization": f"Bearer {token_response.text.strip()}"},
                    params={"select": "id,name,ip,os.name,os.version,status,lastKeepAlive"},
                )
                agents_response.raise_for_status()
                payload = agents_response.json()
        except (httpx.HTTPError, ValueError, KeyError) as error:
            logger.warning(
                "topology: could not read Wazuh agents for tenant %s from %s (timeout %ss): %s: %s",
                tenant_id,
                base_url,
                timeout_seconds,
                type(error).__name__,
                error,
            )
            return {}

        nodes: dict[str, TopologyNode] = {}
        for agent in payload.get("data", {}).get("affected_items", []):
            agent_id = str(agent.get("id", "")).strip()
            name = str(agent.get("name", "")).strip()
            if not agent_id or not name:
                continue
            # Agent 000 is the manager's own local agent, already shown as a feed.
            if agent_id == "000":
                continue
            address = str(agent.get("ip") or "").strip()
            operating_system = agent.get("os") or {}
            os_info = (
                " ".join(
                    part
                    for part in (
                        str(operating_system.get("name") or "").strip(),
                        str(operating_system.get("version") or "").strip(),
                    )
                    if part
                )
                or None
            )
            reported = str(agent.get("status", "")).strip().lower()
            status = "ONLINE" if reported == "active" else "OFFLINE"
            last_keep_alive = str(agent.get("lastKeepAlive") or "").strip()
            nodes[f"agent-{agent_id}"] = TopologyNode(
                id=f"agent-{agent_id}",
                name=name,
                type="ENDPOINT",
                category="MONITORED_ASSET",
                ip_address=address or "unresolved",
                ip_addresses=[address] if address else [],
                services=[],
                subnet=_subnet_of(address or None),
                status=status,  # type: ignore[arg-type]
                latency_ms=None,
                last_ping=last_keep_alive or now_iso,
                active_alerts_count=0,
                active_alerts=[],
                os_info=os_info,
                monitored_by=[f"Wazuh agent {agent_id}"],
                role_description_es="Activo con agente Wazuh reportando al manager",
                role_description_en="Asset with a Wazuh agent reporting to the manager",
            )
        return nodes

    async def _annotate_alerts(
        self, tenant_id: UUID, assets: dict[str, TopologyNode], now_iso: str
    ) -> None:
        """Attach real alerts to assets, matching only on what the agent reports.

        An alert about a host Cyrvanta does not monitor never invents a node --
        the map would otherwise claim visibility the platform does not have.
        """
        if not assets:
            return
        async with tenant_session(tenant_id) as session:
            alerts = list(
                (
                    await session.scalars(
                        select(AlertReferenceModel)
                        .where(
                            AlertReferenceModel.tenant_id == tenant_id,
                            AlertReferenceModel.is_simulated.is_(False),
                            # Dismissing an alert has to remove it from the map,
                            # or the badge only ever grows and triage changes
                            # nothing an operator can see. Alerts confirmed
                            # RELEVANT stay: deciding a threat is real does not
                            # resolve it.
                            AlertReferenceModel.triage_status != "DISCARDED",
                        )
                        .order_by(desc(AlertReferenceModel.observed_at))
                        .limit(_ALERT_SCAN_LIMIT)
                    )
                ).all()
            )

        by_identity: dict[str, TopologyNode] = {}
        for node in assets.values():
            by_identity[node.name.casefold()] = node
            for address in node.ip_addresses:
                by_identity[address] = node

        # Repeated titles collapse into one line carrying a count: a host that
        # logs the same routine event dozens of times used to fill every slot
        # with identical rows, so anything else it reported was never shown.
        grouped: dict[int, dict[str, TopologyNodeAlert]] = {}
        for alert in alerts:
            raw = (alert.asset_summary or alert.indicator_summary or "").strip()
            if not raw:
                continue
            candidate = raw.split()[0].rstrip(",:;").split(":")[0]
            node = by_identity.get(candidate) or by_identity.get(candidate.casefold())
            if node is None:
                continue
            severity = (alert.severity or "").lower()
            if severity not in _VALID_SEVERITIES:
                severity = "medium"
            node.active_alerts_count += 1
            if severity in ("critical", "high") and node.status == "ONLINE":
                node.status = "WARNING"

            seen = grouped.setdefault(id(node), {})
            existing = seen.get(alert.title)
            if existing is not None:
                existing.occurrences += 1
                continue
            if len(seen) >= _ALERTS_PER_NODE:
                continue
            entry = TopologyNodeAlert(
                id=str(alert.id),
                title=alert.title,
                severity=severity,  # type: ignore[arg-type]
                category=alert.category or "security",
                observed_at=(alert.observed_at.isoformat() if alert.observed_at else now_iso),
            )
            seen[alert.title] = entry
            node.active_alerts.append(entry)

    # ── Real relationships only ────────────────────────────────────────────────

    @staticmethod
    def _edges(
        core: dict[str, TopologyNode],
        feeds: dict[str, TopologyNode],
        assets: dict[str, TopologyNode],
        wazuh_configured: bool,
    ) -> list[TopologyEdge]:
        edges: list[TopologyEdge] = []

        def link(edge_id: str, source: str, target: str, protocol: str) -> None:
            source_node = core.get(source) or feeds.get(source) or assets.get(source)
            target_node = core.get(target) or feeds.get(target) or assets.get(target)
            if source_node is None or target_node is None:
                return
            degraded = "OFFLINE" in (source_node.status, target_node.status)
            edges.append(
                TopologyEdge(
                    id=edge_id,
                    source_id=source,
                    target_id=target,
                    protocol=protocol,
                    status="DEGRADED" if degraded else "NORMAL",
                )
            )

        link("edge-db", "db-01", "broker-01", "Outbox transaccional")
        link("edge-cache", "cache-01", "broker-01", "Coordinación de locks")
        link("edge-telemetry", "integ-wazuh", "telemetry-01", "Indexación de telemetría")
        link("edge-soar", "broker-01", "soar-01", "Dispatch de playbooks")
        link("edge-ai", "broker-01", "ai-01", "Redacción asistida")

        if wazuh_configured:
            for asset_id in assets:
                link(
                    f"edge-{asset_id}-wazuh",
                    asset_id,
                    "integ-wazuh",
                    "Agente Wazuh (1514/tcp)",
                )
        return edges
