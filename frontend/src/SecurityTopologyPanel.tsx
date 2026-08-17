import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { getNetworkTopology, TopologyNode } from "./api";


export function SecurityTopologyPanel() {
  const { t, i18n } = useTranslation();
  const [viewMode, setViewMode] = useState<"graph" | "list">("graph");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [searchFilter, setSearchFilter] = useState<string>("");
  const [categoryFilter, setCategoryFilter] = useState<string>("ALL");

  const topology = useQuery({
    queryKey: ["operations", "topology"],
    queryFn: getNetworkTopology,
    refetchInterval: 60_000,
  });

  const nodes = topology.data?.nodes ?? [];
  const edges = topology.data?.edges ?? [];

  const selectedNode = nodes.find((n) => n.id === selectedNodeId) ?? (nodes.length > 0 ? nodes[0] : null);

  const onlineCount = nodes.filter((n) => n.status === "ONLINE").length;
  const warningCount = nodes.filter((n) => n.status === "WARNING").length;
  const totalAlerts = nodes.reduce((acc, n) => acc + (n.active_alerts_count || 0), 0);

  // Group nodes by operational zone
  const feedsNodes = nodes.filter(
    (n) => n.category === "SECURITY_FEED" || n.id.startsWith("integ-") || n.id.startsWith("siem-")
  );
  const coreNodes = nodes.filter(
    (n) =>
      n.category === "CYRVANTA_CORE" ||
      ["gw-01", "db-01", "telemetry-01", "broker-01", "soar-01", "ai-01"].includes(n.id)
  );
  const assetNodes = nodes.filter(
    (n) =>
      n.category === "MONITORED_ASSET" ||
      n.id.startsWith("asset-") ||
      n.id.startsWith("lab-")
  );

  // Filtered nodes for Table view
  const filteredNodes = nodes.filter((n) => {
    const matchesSearch =
      searchFilter.trim() === "" ||
      n.name.toLowerCase().includes(searchFilter.toLowerCase()) ||
      n.ip_address.includes(searchFilter) ||
      (n.ip_addresses && n.ip_addresses.some((ip) => ip.includes(searchFilter))) ||
      n.subnet.includes(searchFilter) ||
      n.type.toLowerCase().includes(searchFilter.toLowerCase()) ||
      (n.services && n.services.some((s) => s.name.toLowerCase().includes(searchFilter.toLowerCase())));

    const matchesCategory =
      categoryFilter === "ALL" ||
      (categoryFilter === "MONITORED_ASSET" && (n.category === "MONITORED_ASSET" || n.id.startsWith("asset-") || n.id.startsWith("lab-"))) ||
      (categoryFilter === "SECURITY_FEED" && (n.category === "SECURITY_FEED" || n.id.startsWith("integ-") || n.id.startsWith("siem-"))) ||
      (categoryFilter === "CYRVANTA_CORE" && (n.category === "CYRVANTA_CORE" || ["gw-01", "db-01", "telemetry-01", "broker-01", "soar-01", "ai-01"].includes(n.id)));

    return matchesSearch && matchesCategory;
  });

  // The canvas grows with the busiest zone instead of clipping it. A security
  // map that silently drops nodes is worse than a taller one: the operator has
  // no way to tell "nothing else is connected" from "the rest did not fit".
  const FEED_PITCH = 72;
  const CORE_PITCH = 72;
  const ASSET_PITCH = 95;
  const FEED_HEIGHT = 60;
  const CORE_HEIGHT = 60;
  const ASSET_HEIGHT = 82;
  const ZONE_TOP = 15;
  const FIRST_NODE_Y = 65;
  const CANVAS_PADDING = 15;

  const zoneBottom = (count: number, pitch: number, nodeHeight: number) =>
    count === 0 ? FIRST_NODE_Y : FIRST_NODE_Y + (count - 1) * pitch + nodeHeight;

  const contentBottom = Math.max(
    zoneBottom(feedsNodes.length, FEED_PITCH, FEED_HEIGHT),
    zoneBottom(coreNodes.length, CORE_PITCH, CORE_HEIGHT),
    zoneBottom(assetNodes.length, ASSET_PITCH, ASSET_HEIGHT),
    350, // never shrink below the original canvas
  );
  const canvasHeight = contentBottom + CANVAS_PADDING;
  const zoneHeight = canvasHeight - ZONE_TOP - CANVAS_PADDING;

  // The drawing keeps its own coordinate space (1020 x canvasHeight) while the
  // viewport stays a constant size on screen. Without this, a tenant with many
  // nodes got a taller drawing squeezed into the same box, shrinking every
  // label until it was unreadable. Now extra nodes make the map navigable
  // rather than smaller.
  const VIEWPORT_WIDTH = 1020;
  const VIEWPORT_HEIGHT = 420;
  const MIN_ZOOM = 0.35;
  const MAX_ZOOM = 3;

  const fitZoom = Math.min(
    1,
    VIEWPORT_HEIGHT / canvasHeight,
    VIEWPORT_WIDTH / VIEWPORT_WIDTH,
  );
  // `null` means "fit everything", the state the map opens in and returns to.
  const [view, setView] = useState<{ zoom: number; x: number; y: number } | null>(null);
  const [isPanning, setIsPanning] = useState(false);

  // A tenant with hundreds of assets fits at well under MIN_ZOOM, so the floor
  // has to follow the fitted scale: otherwise zooming out from the fitted view
  // would clamp upwards and zoom *in*.
  const minZoom = Math.min(MIN_ZOOM, fitZoom);
  const clampZoom = (value: number) => Math.min(MAX_ZOOM, Math.max(minZoom, value));
  const centeredPan = (zoom: number) => ({
    x: (VIEWPORT_WIDTH - VIEWPORT_WIDTH * zoom) / 2,
    y: (VIEWPORT_HEIGHT - canvasHeight * zoom) / 2,
  });
  const currentView = view ?? { zoom: fitZoom, ...centeredPan(fitZoom) };
  const isFitted = view === null;

  const zoomBy = (factor: number) => {
    const nextZoom = clampZoom(currentView.zoom * factor);
    if (nextZoom === currentView.zoom) return;
    // Keep the viewport centre fixed so zooming does not drift the map away.
    const ratio = nextZoom / currentView.zoom;
    setView({
      zoom: nextZoom,
      x: VIEWPORT_WIDTH / 2 - (VIEWPORT_WIDTH / 2 - currentView.x) * ratio,
      y: VIEWPORT_HEIGHT / 2 - (VIEWPORT_HEIGHT / 2 - currentView.y) * ratio,
    });
  };

  const getCategoryLabel = (cat?: string) => {
    if (cat === "SECURITY_FEED") return t("topologyFilterFeeds");
    if (cat === "CYRVANTA_CORE") return t("topologyFilterCore");
    return t("topologyFilterAssets");
  };

  const getCategoryClass = (cat?: string) => {
    if (cat === "SECURITY_FEED") return "feeds";
    if (cat === "CYRVANTA_CORE") return "core";
    return "assets";
  };

  return (
    <article
      className="panel topology-panel"
      style={{ display: "flex", flexDirection: "column", gap: "1rem", width: "100%" }}
    >
      <div className="topology-panel-header">
        <div>
          <p className="eyebrow">{t("monitoredEnvironment")}</p>
          <h2 style={{ margin: "4px 0 0" }}>{t("securityTopology")}</h2>
        </div>

        {nodes.length > 0 && (
          <div className="topology-view-toggle">
            <button
              type="button"
              className={`topology-tab-btn ${viewMode === "graph" ? "active" : ""}`}
              onClick={() => setViewMode("graph")}
            >
              🗺️ {i18n.language.startsWith("es") ? "Mapa Visual" : "Visual Map"}
            </button>
            <button
              type="button"
              className={`topology-tab-btn ${viewMode === "list" ? "active" : ""}`}
              onClick={() => setViewMode("list")}
            >
              📋 {i18n.language.startsWith("es") ? "Tabla Consolidada" : "Node Table"} ({nodes.length})
            </button>
          </div>
        )}
      </div>

      {topology.isLoading && <p className="muted" role="status">{t("loading")}</p>}
      {topology.isError && <p className="error" role="alert">{t("loadError")}</p>}
      {!topology.isLoading && !topology.isError && nodes.length === 0 && (
        <p className="muted">{t("emptyState")}</p>
      )}

      {nodes.length > 0 && (
        <>
          {/* Operational Metrics Strip */}
          <div className="topology-metrics-strip">
            <div className="topology-metric-pill">
              <span style={{ color: "var(--success)" }}>●</span> {i18n.language.startsWith("es") ? "En Línea" : "Online"}:
              <strong style={{ color: "var(--success)" }}>{onlineCount}</strong>
            </div>
            {warningCount > 0 && (
              <div className="topology-metric-pill">
                <span>⚠️</span> {i18n.language.startsWith("es") ? "Con Alertas" : "In Warning"}:
                <strong style={{ color: "var(--warning)" }}>{warningCount}</strong>
              </div>
            )}
            <div className="topology-metric-pill">
              <span>🛡️</span> {i18n.language.startsWith("es") ? "Total Alertas" : "Total Alerts"}:
              <strong style={{ color: totalAlerts > 0 ? "var(--warning)" : "var(--text-soft)" }}>{totalAlerts}</strong>
            </div>
            <div className="topology-metric-pill">
              <span>🏢</span> {i18n.language.startsWith("es") ? "Activos Protegidos" : "Protected Assets"}:
              <strong>{assetNodes.length}</strong>
            </div>
            <div className="topology-metric-pill">
              <span>📡</span> {i18n.language.startsWith("es") ? "Fuentes de Detección" : "Security Feeds"}:
              <strong>{feedsNodes.length}</strong>
            </div>
          </div>

          {/* VISUAL GRAPH VIEW (3 Operational Zones) */}
          {viewMode === "graph" && (
            <div className="topology-graph-container">
              <div className="topology-zoom-controls">
                <button
                  type="button"
                  onClick={() => zoomBy(1 / 1.25)}
                  disabled={currentView.zoom <= minZoom}
                  aria-label={i18n.language.startsWith("es") ? "Alejar" : "Zoom out"}
                  title={i18n.language.startsWith("es") ? "Alejar" : "Zoom out"}
                >
                  −
                </button>
                <span className="topology-zoom-level" aria-live="polite">
                  {Math.round(currentView.zoom * 100)}%
                </span>
                <button
                  type="button"
                  onClick={() => zoomBy(1.25)}
                  disabled={currentView.zoom >= MAX_ZOOM}
                  aria-label={i18n.language.startsWith("es") ? "Acercar" : "Zoom in"}
                  title={i18n.language.startsWith("es") ? "Acercar" : "Zoom in"}
                >
                  +
                </button>
                <button
                  type="button"
                  className="topology-zoom-reset"
                  onClick={() => setView(null)}
                  disabled={isFitted}
                  title={
                    i18n.language.startsWith("es")
                      ? "Ver todo el mapa"
                      : "Fit the whole map"
                  }
                >
                  {i18n.language.startsWith("es") ? "Ajustar" : "Fit"}
                </button>
              </div>
              <svg
                className={`topology-svg-canvas${isPanning ? " panning" : ""}`}
                viewBox={`0 0 ${VIEWPORT_WIDTH} ${VIEWPORT_HEIGHT}`}
                role="application"
                aria-label={
                  i18n.language.startsWith("es")
                    ? "Mapa de topología: arrastra para desplazar, rueda del ratón para acercar"
                    : "Topology map: drag to pan, scroll to zoom"
                }
                onWheel={(event) => {
                  event.preventDefault();
                  zoomBy(event.deltaY < 0 ? 1.15 : 1 / 1.15);
                }}
                onPointerDown={(event) => {
                  // Only a drag on empty canvas pans; clicks on nodes still select.
                  if ((event.target as Element).closest(".topology-node-badge")) return;
                  event.currentTarget.setPointerCapture(event.pointerId);
                  setIsPanning(true);
                }}
                onPointerMove={(event) => {
                  if (!isPanning) return;
                  const scale = VIEWPORT_WIDTH / event.currentTarget.getBoundingClientRect().width;
                  setView({
                    zoom: currentView.zoom,
                    x: currentView.x + event.movementX * scale,
                    y: currentView.y + event.movementY * scale,
                  });
                }}
                onPointerUp={(event) => {
                  event.currentTarget.releasePointerCapture(event.pointerId);
                  setIsPanning(false);
                }}
                onPointerCancel={() => setIsPanning(false)}
              >
                <defs>
                  <linearGradient id="edgeNormal" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.5" />
                    <stop offset="100%" stopColor="var(--cyan)" stopOpacity="0.5" />
                  </linearGradient>
                  <linearGradient id="edgeFeed" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="var(--warning)" stopOpacity="0.6" />
                    <stop offset="100%" stopColor="var(--accent)" stopOpacity="0.6" />
                  </linearGradient>
                  <linearGradient id="edgeWarning" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="var(--warning)" stopOpacity="0.85" />
                    <stop offset="100%" stopColor="var(--danger)" stopOpacity="0.85" />
                  </linearGradient>
                  <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
                    <feGaussianBlur stdDeviation="3" result="blur" />
                    <feComposite in="SourceGraphic" in2="blur" operator="over" />
                  </filter>
                </defs>

                <g transform={`translate(${currentView.x} ${currentView.y}) scale(${currentView.zoom})`}>

                {/* 3 Operational Zones */}
                <g opacity="0.7">
                  {/* Zone 1: Security Feeds & Sensors (Left) */}
                  <rect x="15" y="15" width="280" height={zoneHeight} rx="8" fill="rgba(255, 170, 0, 0.02)" stroke="var(--warning)" strokeDasharray="4 4" strokeOpacity="0.4" />
                  <text x="25" y="36" fill="var(--warning)" fontSize="11" fontWeight="700" letterSpacing="0.06em">
                    📡 {i18n.language.startsWith("es") ? "1. FUENTES DE SEGURIDAD & SENSORES" : "1. SECURITY FEEDS & SENSORS"}
                  </text>
                  <text x="25" y="50" fill="var(--muted)" fontSize="9">
                    {i18n.language.startsWith("es") ? "Ingesta de telemetría (SIEMs, EDRs, Firewalls)" : "Telemetry ingestion (SIEMs, EDRs, Firewalls)"}
                  </text>

                  {/* Zone 2: Cyrvanta SOC Core Platform (Middle) */}
                  <rect x="320" y="15" width="340" height={zoneHeight} rx="8" fill="rgba(85, 230, 193, 0.03)" stroke="var(--accent)" strokeDasharray="4 4" strokeOpacity="0.5" />
                  <text x="330" y="36" fill="var(--accent)" fontSize="11" fontWeight="700" letterSpacing="0.06em">
                    🛡️ {i18n.language.startsWith("es") ? "2. PLATAFORMA CYRVANTA (NÚCLEO SOC)" : "2. CYRVANTA SECOPS PLATFORM"}
                  </text>
                  <text x="330" y="50" fill="var(--muted)" fontSize="9">
                    {i18n.language.startsWith("es") ? "Correlación, RLS, Almacenamiento e IA" : "Correlation, RLS, Storage and AI Engine"}
                  </text>

                  {/* Zone 3: Monitored Tenant Network & Assets (Right) */}
                  <rect x="685" y="15" width="320" height={zoneHeight} rx="8" fill="rgba(96, 201, 255, 0.02)" stroke="var(--cyan)" strokeDasharray="4 4" strokeOpacity="0.4" />
                  <text x="695" y="36" fill="var(--cyan)" fontSize="11" fontWeight="700" letterSpacing="0.06em">
                    🏢 {i18n.language.startsWith("es") ? "3. RED Y ACTIVOS PROTEGIDOS" : "3. PROTECTED TENANT ASSETS"}
                  </text>
                  <text x="695" y="50" fill="var(--muted)" fontSize="9">
                    {i18n.language.startsWith("es") ? "Servidores consolidados, servicios y LAN" : "Consolidated hosts, services and LAN"}
                  </text>
                  {assetNodes.length === 0 && (
                    <text x="695" y="80" fill="var(--muted)" fontSize="9.5">
                      {i18n.language.startsWith("es")
                        ? "Ningún activo monitorizado está reportando."
                        : "No monitored asset is reporting."}
                    </text>
                  )}
                </g>

                {/* Directional Data Flow Lines */}
                <g strokeWidth="2">
                  <path d="M 285 100 L 335 100" stroke="url(#edgeFeed)" strokeDasharray="4 3" />
                  <path d="M 285 180 L 335 180" stroke="url(#edgeFeed)" strokeDasharray="4 3" />
                  <path d="M 685 110 L 645 110" stroke="url(#edgeNormal)" strokeDasharray="4 3" />
                  <path d="M 685 220 L 645 220" stroke={warningCount > 0 ? "url(#edgeWarning)" : "url(#edgeNormal)"} strokeDasharray="4 3" />
                </g>

                {/* ZONE 1: Security Feed Nodes (Left) */}
                {feedsNodes.map((n, i) => (
                  <g
                    key={n.id}
                    className="topology-node-badge"
                    transform={`translate(25, ${65 + i * 72})`}
                    onClick={() => setSelectedNodeId(n.id)}
                  >
                    <rect
                      width="260"
                      height="60"
                      rx="6"
                      fill={selectedNodeId === n.id ? "var(--panel-raised)" : "var(--panel)"}
                      stroke={selectedNodeId === n.id ? "var(--warning)" : "var(--line)"}
                      strokeWidth={selectedNodeId === n.id ? "2" : "1"}
                    />
                    <circle
                      cx="16"
                      cy="22"
                      r="5"
                      fill={n.status === "ONLINE" ? "var(--warning)" : "var(--danger)"}
                      filter="url(#glow)"
                    />
                    <text x="28" y="25" fill="var(--text)" fontSize="11" fontWeight="700">
                      {n.name.length > 28 ? n.name.slice(0, 26) + "..." : n.name}
                    </text>
                    <text x="28" y="42" fill="var(--muted)" fontSize="9.5">
                      📡 {n.type} • {n.ip_address}
                    </text>
                    <text x="28" y="53" fill="var(--text-soft)" fontSize="8.5">
                      {n.services && n.services.length > 0 ? n.services[0].name : "Security Sensor Feed"}
                    </text>
                  </g>
                ))}

                {/* ZONE 2: Cyrvanta Core Nodes (Middle) */}
                {coreNodes.map((n, i) => (
                  <g
                    key={n.id}
                    className="topology-node-badge"
                    transform={`translate(335, ${65 + i * 72})`}
                    onClick={() => setSelectedNodeId(n.id)}
                  >
                    <rect
                      width="310"
                      height="60"
                      rx="6"
                      fill={selectedNodeId === n.id ? "var(--panel-raised)" : "var(--panel)"}
                      stroke={selectedNodeId === n.id ? "var(--accent)" : "var(--line)"}
                      strokeWidth={selectedNodeId === n.id ? "2" : "1"}
                    />
                    <circle
                      cx="16"
                      cy="22"
                      r="5"
                      fill={n.status === "ONLINE" ? "var(--accent)" : "var(--warning)"}
                      filter="url(#glow)"
                    />
                    <text x="28" y="25" fill="var(--text)" fontSize="11" fontWeight="700">
                      {n.name.length > 32 ? n.name.slice(0, 30) + "..." : n.name}
                    </text>
                    <text x="28" y="42" fill="var(--muted)" fontSize="9.5">
                      🛡️ {n.ip_address}
                      {typeof n.latency_ms === "number" ? ` • ⚡ ${n.latency_ms}ms` : ""}
                    </text>
                    <text x="28" y="53" fill="var(--accent)" fontSize="8.5">
                      {n.services && n.services.length > 0 ? `⚙️ ${n.services.map((s) => s.name).join(" | ")}` : "Core Service"}
                    </text>
                  </g>
                ))}

                {/* ZONE 3: Monitored Protected Assets (Right - Consolidated Hosts).
                    Only assets the platform actually sees are drawn; when none
                    report, the zone stays empty rather than showing example hosts. */}
                {assetNodes
                  .map((n: any, i) => {
                    const isWarn = n.status === "WARNING" || (n.active_alerts_count && n.active_alerts_count > 0);
                    const ipsText = n.ip_addresses && n.ip_addresses.length > 1
                      ? n.ip_addresses.join(" | ")
                      : n.ip_address;
                    const servicesText = n.services && n.services.length > 0
                      ? n.services.map((s: any) => s.name).join(", ")
                      : "Host Agent";

                    return (
                      <g
                        key={n.id}
                        className="topology-node-badge"
                        transform={`translate(695, ${65 + i * 95})`}
                        onClick={() => setSelectedNodeId(n.id)}
                      >
                        <rect
                          width="300"
                          height="82"
                          rx="6"
                          fill={selectedNodeId === n.id ? "var(--panel-raised)" : "var(--panel)"}
                          stroke={isWarn ? "var(--warning)" : selectedNodeId === n.id ? "var(--cyan)" : "var(--line)"}
                          strokeWidth={selectedNodeId === n.id || isWarn ? "2" : "1"}
                        />
                        <circle
                          cx="16"
                          cy="22"
                          r="5"
                          fill={isWarn ? "var(--warning)" : "var(--cyan)"}
                          filter="url(#glow)"
                        />
                        <text x="28" y="25" fill="var(--text)" fontSize="11.5" fontWeight="700">
                          {n.name.length > 28 ? n.name.slice(0, 26) + "..." : n.name}
                        </text>
                        {isWarn && (
                          <text x="260" y="25" fill="var(--warning)" fontSize="10" fontWeight="700">
                            ⚠️ {n.active_alerts_count || 1}
                          </text>
                        )}
                        <text x="28" y="44" fill="var(--cyan)" fontSize="9.5" fontFamily="monospace">
                          🌐 {ipsText.length > 34 ? ipsText.slice(0, 32) + "..." : ipsText}
                        </text>
                        <text x="28" y="60" fill="var(--text-soft)" fontSize="9">
                          ⚙️ {i18n.language.startsWith("es") ? "Servicios" : "Services"}: {servicesText.length > 34 ? servicesText.slice(0, 32) + "..." : servicesText}
                        </text>
                        <text x="28" y="74" fill="var(--muted)" fontSize="8.5">
                          🛡️ {n.monitored_by ? n.monitored_by.join(", ") : "Wazuh Agent"}
                        </text>
                      </g>
                    );
                  })}
                </g>
              </svg>

              {/* Visual Map Legend */}
              <div className="topology-legend">
                <div style={{ display: "flex", gap: "16px", alignItems: "center" }}>
                  <span><strong style={{ color: "var(--warning)" }}>🟠 {i18n.language.startsWith("es") ? "Fuentes / Sensores" : "Security Feeds"}</strong> (Wazuh, EDR, FW)</span>
                  <span><strong style={{ color: "var(--accent)" }}>🔵 {i18n.language.startsWith("es") ? "Plataforma Cyrvanta" : "Cyrvanta Platform"}</strong> (SOC Core)</span>
                  <span><strong style={{ color: "var(--cyan)" }}>🟢 {i18n.language.startsWith("es") ? "Activos Protegidos" : "Protected Assets"}</strong> (Hosts & Services)</span>
                </div>
                <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
                  <span><span style={{ color: "var(--success)" }}>●</span> {i18n.language.startsWith("es") ? "En Línea" : "Online"}</span>
                  <span><span style={{ color: "var(--warning)" }}>⚠️</span> {i18n.language.startsWith("es") ? "Con Alertas" : "With Alerts"}</span>
                </div>
              </div>
            </div>
          )}

          {/* TABLE VIEW (Consolidated List View) */}
          {viewMode === "list" && (
            <div>
              {/* Filter Bar */}
              <div className="topology-table-filter-bar">
                <input
                  type="search"
                  className="topology-filter-input"
                  placeholder={i18n.language.startsWith("es") ? "🔍 Filtrar por host, IP, servicio, tipo..." : "🔍 Filter host, IP, service, type..."}
                  value={searchFilter}
                  onChange={(e) => setSearchFilter(e.target.value)}
                />
                <div className="topology-tier-filters">
                  {[
                    { key: "ALL", label: t("topologyFilterAll") },
                    { key: "MONITORED_ASSET", label: t("topologyFilterAssets") },
                    { key: "SECURITY_FEED", label: t("topologyFilterFeeds") },
                    { key: "CYRVANTA_CORE", label: t("topologyFilterCore") },
                  ].map((filter) => (
                    <button
                      key={filter.key}
                      type="button"
                      className={`topology-tier-pill ${categoryFilter === filter.key ? "active" : ""}`}
                      onClick={() => setCategoryFilter(filter.key)}
                    >
                      {filter.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Data Table */}
              <div className="topology-table-container">
                <table className="topology-table">
                  <thead>
                    <tr>
                      <th>{i18n.language.startsWith("es") ? "Estado" : "Status"}</th>
                      <th>{i18n.language.startsWith("es") ? "Grupo / Rol" : "Group / Role"}</th>
                      <th>{i18n.language.startsWith("es") ? "Host / Nombre" : "Host / Name"}</th>
                      <th>{i18n.language.startsWith("es") ? "Tipo" : "Type"}</th>
                      <th>{i18n.language.startsWith("es") ? "Direcciones IP" : "IP Addresses"}</th>
                      <th>{i18n.language.startsWith("es") ? "Servicios Integrados" : "Integrated Services"}</th>
                      <th>{i18n.language.startsWith("es") ? "Alertas" : "Alerts"}</th>
                      <th>{i18n.language.startsWith("es") ? "Acción" : "Action"}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredNodes.length === 0 ? (
                      <tr>
                        <td colSpan={8} style={{ textAlign: "center", padding: "2rem", color: "var(--muted)" }}>
                          {i18n.language.startsWith("es") ? "No se encontraron nodos coincidentes." : "No matching nodes found."}
                        </td>
                      </tr>
                    ) : (
                      filteredNodes.map((node) => (
                        <tr
                          key={node.id}
                          className={selectedNodeId === node.id ? "selected" : ""}
                          onClick={() => setSelectedNodeId(node.id)}
                        >
                          <td>
                            <div className="topology-status-cell">
                              <span className={`topology-status-dot ${node.status === "ONLINE" ? "online" : "warning"}`} />
                              <span className={`status ${node.status === "ONLINE" ? "success" : "warning"}`} style={{ fontSize: "0.75rem" }}>
                                {node.status}
                              </span>
                            </div>
                          </td>
                          <td>
                            <span className={`topology-category-pill ${getCategoryClass(node.category)}`}>
                              {getCategoryLabel(node.category)}
                            </span>
                          </td>
                          <td>
                            <strong>{node.name}</strong>
                            <div style={{ fontSize: "0.75rem", color: "var(--muted)", marginTop: "2px" }}>
                              {i18n.language.startsWith("es") ? node.role_description_es : node.role_description_en}
                            </div>
                          </td>
                          <td>
                            <span className="status" style={{ fontSize: "0.75rem", textTransform: "uppercase" }}>
                              {node.type}
                            </span>
                          </td>
                          <td>
                            <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
                              {node.ip_addresses && node.ip_addresses.length > 0 ? (
                                node.ip_addresses.map((ip) => (
                                  <code key={ip} className="topology-ip-code">{ip}</code>
                                ))
                              ) : (
                                <code className="topology-ip-code">{node.ip_address}</code>
                              )}
                            </div>
                          </td>
                          <td>
                            {node.services && node.services.length > 0 ? (
                              <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
                                {node.services.map((svc, sIdx) => (
                                  <span
                                    key={sIdx}
                                    className={`topology-service-tag ${svc.status === "WARNING" ? "warning" : ""}`}
                                  >
                                    ⚙️ {svc.name} {svc.port ? `(:${svc.port})` : ""}
                                  </span>
                                ))}
                              </div>
                            ) : (
                              <span style={{ color: "var(--muted)", fontSize: "0.8rem" }}>—</span>
                            )}
                          </td>
                          <td>
                            {node.active_alerts_count > 0 ? (
                              <span className="status warning" style={{ fontSize: "0.75rem" }}>
                                ⚠️ {node.active_alerts_count}
                              </span>
                            ) : (
                              <span style={{ color: "var(--muted)", fontSize: "0.8rem" }}>0</span>
                            )}
                          </td>
                          <td>
                            <button
                              type="button"
                              className="ghost"
                              style={{ padding: "4px 10px", minHeight: "28px", fontSize: "0.75rem" }}
                              onClick={(e) => {
                                e.stopPropagation();
                                setSelectedNodeId(node.id);
                              }}
                            >
                              🔍 {i18n.language.startsWith("es") ? "Inspeccionar" : "Inspect"}
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Selected Node Details Drawer */}
          {selectedNode && (
            <div className="topology-detail-card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "10px" }}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                    <strong style={{ fontSize: "1.1rem", color: "var(--text)" }}>{selectedNode.name}</strong>
                    <span className={`status ${selectedNode.status === "ONLINE" ? "success" : "warning"}`}>
                      {selectedNode.status}
                    </span>
                    <span className="status" style={{ fontSize: "0.75rem" }}>{selectedNode.type}</span>
                    <span className={`topology-category-pill ${getCategoryClass(selectedNode.category)}`}>
                      {getCategoryLabel(selectedNode.category)}
                    </span>
                  </div>
                  <p style={{ margin: "4px 0 0", color: "var(--muted)", fontSize: "0.85rem" }}>
                    {i18n.language.startsWith("es") ? selectedNode.role_description_es : selectedNode.role_description_en}
                  </p>
                </div>

                <div style={{ display: "flex", gap: "18px", fontSize: "0.85rem", flexWrap: "wrap" }}>
                  <div>
                    <span className="muted" style={{ display: "block" }}>{t("topologyIpAddresses")}</span>
                    <div style={{ display: "flex", gap: "4px", marginTop: "2px" }}>
                      {selectedNode.ip_addresses && selectedNode.ip_addresses.length > 0 ? (
                        selectedNode.ip_addresses.map((ip) => (
                          <strong key={ip} className="topology-ip-code">{ip}</strong>
                        ))
                      ) : (
                        <strong className="topology-ip-code">{selectedNode.ip_address}</strong>
                      )}
                    </div>
                  </div>
                  <div>
                    <span className="muted" style={{ display: "block" }}>Subnet</span>
                    <strong>{selectedNode.subnet}</strong>
                  </div>
                  <div>
                    <span className="muted" style={{ display: "block" }}>Latency</span>
                    <strong>{selectedNode.latency_ms} ms</strong>
                  </div>
                  {selectedNode.os_info && (
                    <div>
                      <span className="muted" style={{ display: "block" }}>{t("topologyOperatingSystem")}</span>
                      <strong>{selectedNode.os_info}</strong>
                    </div>
                  )}
                  {selectedNode.monitored_by && selectedNode.monitored_by.length > 0 && (
                    <div>
                      <span className="muted" style={{ display: "block" }}>{t("topologyMonitoredBy")}</span>
                      <strong style={{ color: "var(--cyan)" }}>{selectedNode.monitored_by.join(", ")}</strong>
                    </div>
                  )}
                </div>
              </div>

              {/* Host Services Grid */}
              {selectedNode.services && selectedNode.services.length > 0 && (
                <div style={{ marginTop: "14px", paddingTop: "10px", borderTop: "1px solid var(--line)" }}>
                  <strong style={{ fontSize: "0.85rem", color: "var(--text)" }}>
                    ⚙️ {t("topologyHostServices")} ({selectedNode.services.length}):
                  </strong>
                  <div className="topology-host-services-grid">
                    {selectedNode.services.map((svc, idx) => (
                      <div
                        key={idx}
                        style={{
                          background: "var(--surface)",
                          border: "1px solid var(--line)",
                          borderRadius: "4px",
                          padding: "6px 10px",
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          fontSize: "0.8rem",
                        }}
                      >
                        <div>
                          <strong>{svc.name}</strong>
                          <div style={{ fontSize: "0.72rem", color: "var(--muted)" }}>
                            {svc.protocol} {svc.port ? `• Port ${svc.port}` : ""} {svc.ip_address ? `• ${svc.ip_address}` : ""}
                          </div>
                        </div>
                        <span className={`status ${svc.status === "ONLINE" ? "success" : "warning"}`} style={{ fontSize: "0.7rem" }}>
                          {svc.status}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Associated Security Alerts */}
              {selectedNode.active_alerts && selectedNode.active_alerts.length > 0 && (
                <div style={{ marginTop: "12px", paddingTop: "10px", borderTop: "1px solid var(--line)" }}>
                  <strong style={{ fontSize: "0.82rem", color: "var(--warning)" }}>
                    ⚠️ {i18n.language.startsWith("es") ? "Alertas de Seguridad Asociadas" : "Associated Security Alerts"}{" "}
                    {/* The total, not the number of lines: repeated titles are
                        collapsed, so counting lines would understate it. */}
                    ({selectedNode.active_alerts_count}):
                  </strong>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "6px" }}>
                    {selectedNode.active_alerts.map((al) => (
                      <span key={al.id} className="status warning" style={{ fontSize: "0.75rem" }}>
                        {al.title} ({al.severity})
                        {(al.occurrences ?? 1) > 1 && ` ×${al.occurrences}`}
                      </span>
                    ))}
                  </div>
                  {selectedNode.active_alerts_count > selectedNode.active_alerts.length && (
                    <small className="muted" style={{ display: "block", marginTop: "6px" }}>
                      {i18n.language.startsWith("es")
                        ? "Se muestran los tipos más recientes. Descartar una alerta en la lista de alertas la quita de este recuento."
                        : "Showing the most recent types. Discarding an alert in the alert list removes it from this count."}
                    </small>
                  )}
                </div>
              )}
            </div>
          )}
        </>
      )}

      {topology.data?.updated_at && (
        <small className="muted">
          {t("activityUpdated", {
            time: new Date(topology.data.updated_at).toLocaleString(i18n.language),
          })}
        </small>
      )}
    </article>
  );
}

