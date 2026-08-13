import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { getNetworkTopology, TopologyNode } from "./api";


export function SecurityTopologyPanel() {
  const { t, i18n } = useTranslation();
  const [viewMode, setViewMode] = useState<"graph" | "list">("graph");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [searchFilter, setSearchFilter] = useState<string>("");
  const [tierFilter, setTierFilter] = useState<string>("ALL");

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

  // Group nodes by architectural tier for SVG graph layout
  const gatewayNodes = nodes.filter((n) => n.type === "GATEWAY");
  const coreNodes = nodes.filter((n) => ["SIEM", "SERVER"].includes(n.type) && !n.id.startsWith("asset-"));
  const dataNodes = nodes.filter((n) => n.type === "DATABASE" || n.type === "FIREWALL" || n.id.startsWith("integ-"));
  const endpointNodes = nodes.filter((n) => n.type === "ENDPOINT" || n.id.startsWith("asset-"));

  // Filtered nodes for Table view
  const filteredNodes = nodes.filter((n) => {
    const matchesSearch =
      searchFilter.trim() === "" ||
      n.name.toLowerCase().includes(searchFilter.toLowerCase()) ||
      n.ip_address.includes(searchFilter) ||
      n.subnet.includes(searchFilter) ||
      n.type.toLowerCase().includes(searchFilter.toLowerCase());

    const matchesTier =
      tierFilter === "ALL" ||
      (tierFilter === "GATEWAY" && n.type === "GATEWAY") ||
      (tierFilter === "CORE" && ["SIEM", "SERVER"].includes(n.type) && !n.id.startsWith("asset-")) ||
      (tierFilter === "DATA" && (n.type === "DATABASE" || n.id.startsWith("integ-"))) ||
      (tierFilter === "ENDPOINTS" && (n.type === "ENDPOINT" || n.id.startsWith("asset-")));

    return matchesSearch && matchesTier;
  });

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
              📋 {i18n.language.startsWith("es") ? "Tabla de Nodos" : "Node Table"} ({nodes.length})
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
              <span>🔗</span> {i18n.language.startsWith("es") ? "Enlaces Activos" : "Active Edges"}:
              <strong>{edges.length}</strong>
            </div>
          </div>

          {/* VISUAL GRAPH VIEW */}
          {viewMode === "graph" && (
            <div className="topology-graph-container">
              <svg className="topology-svg-canvas" viewBox="0 0 980 340">
                <defs>
                  <linearGradient id="edgeNormal" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.45" />
                    <stop offset="100%" stopColor="var(--cyan)" stopOpacity="0.45" />
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

                {/* Zone Background Rectangles */}
                <g opacity="0.6">
                  {/* Zone 1: Perimeter */}
                  <rect x="20" y="20" width="200" height="300" rx="8" fill="rgba(255,255,255,0.015)" stroke="var(--line)" strokeDasharray="4 4" />
                  <text x="30" y="42" fill="var(--muted)" fontSize="11" fontWeight="700" letterSpacing="0.08em">DMZ / PERÍMETRO</text>

                  {/* Zone 2: Core SecOps */}
                  <rect x="245" y="20" width="245" height="300" rx="8" fill="rgba(85, 230, 193, 0.02)" stroke="var(--line)" strokeDasharray="4 4" />
                  <text x="255" y="42" fill="var(--accent)" fontSize="11" fontWeight="700" letterSpacing="0.08em">NÚCLEO SECOPS & SIEM</text>

                  {/* Zone 3: Data & Integrations */}
                  <rect x="515" y="20" width="220" height="300" rx="8" fill="rgba(96, 201, 255, 0.02)" stroke="var(--line)" strokeDasharray="4 4" />
                  <text x="525" y="42" fill="var(--cyan)" fontSize="11" fontWeight="700" letterSpacing="0.08em">DATOS & CONECTORES</text>

                  {/* Zone 4: Endpoints */}
                  <rect x="760" y="20" width="200" height="300" rx="8" fill="rgba(255,255,255,0.015)" stroke="var(--line)" strokeDasharray="4 4" />
                  <text x="770" y="42" fill="var(--muted)" fontSize="11" fontWeight="700" letterSpacing="0.08em">ENDPOINTS / LAN</text>
                </g>

                {/* Inter-zone connection lines */}
                <g strokeWidth="2">
                  <line x1="200" y1="120" x2="265" y2="100" stroke="url(#edgeNormal)" strokeDasharray="6 3" />
                  <line x1="200" y1="120" x2="265" y2="180" stroke="url(#edgeNormal)" strokeDasharray="6 3" />
                  <line x1="475" y1="100" x2="535" y2="100" stroke="url(#edgeNormal)" />
                  <line x1="475" y1="180" x2="535" y2="180" stroke="url(#edgeNormal)" />
                  <line x1="475" y1="240" x2="535" y2="240" stroke="url(#edgeNormal)" />
                  <line x1="720" y1="120" x2="780" y2="100" stroke="url(#edgeNormal)" strokeDasharray="4 4" />
                  <line x1="720" y1="180" x2="780" y2="180" stroke={warningCount > 0 ? "url(#edgeWarning)" : "url(#edgeNormal)"} strokeDasharray="4 4" />
                </g>

                {/* Zone 1 Nodes: Gateway */}
                {gatewayNodes.map((n, i) => (
                  <g
                    key={n.id}
                    className="topology-node-badge"
                    transform={`translate(35, ${70 + i * 80})`}
                    onClick={() => setSelectedNodeId(n.id)}
                  >
                    <rect
                      width="170"
                      height="58"
                      rx="6"
                      fill={selectedNodeId === n.id ? "var(--panel-raised)" : "var(--panel)"}
                      stroke={selectedNodeId === n.id ? "var(--accent)" : "var(--line)"}
                      strokeWidth={selectedNodeId === n.id ? "2" : "1"}
                    />
                    <circle cx="16" cy="22" r="5" fill="var(--success)" filter="url(#glow)" />
                    <text x="28" y="25" fill="var(--text)" fontSize="11" fontWeight="700">Gateway Ingress</text>
                    <text x="28" y="44" fill="var(--muted)" fontSize="9.5">{n.ip_address}</text>
                  </g>
                ))}

                {/* Zone 2 Nodes: Core SIEM, Broker, SOAR */}
                {coreNodes.slice(0, 3).map((n, i) => (
                  <g
                    key={n.id}
                    className="topology-node-badge"
                    transform={`translate(260, ${65 + i * 75})`}
                    onClick={() => setSelectedNodeId(n.id)}
                  >
                    <rect
                      width="215"
                      height="58"
                      rx="6"
                      fill={selectedNodeId === n.id ? "var(--panel-raised)" : "var(--panel)"}
                      stroke={selectedNodeId === n.id ? "var(--accent)" : "var(--line)"}
                      strokeWidth={selectedNodeId === n.id ? "2" : "1"}
                    />
                    <circle
                      cx="16"
                      cy="22"
                      r="5"
                      fill={n.status === "ONLINE" ? "var(--success)" : "var(--warning)"}
                      filter="url(#glow)"
                    />
                    <text x="28" y="25" fill="var(--text)" fontSize="11" fontWeight="700">
                      {n.name.length > 24 ? n.name.slice(0, 22) + "..." : n.name}
                    </text>
                    <text x="28" y="44" fill="var(--muted)" fontSize="9.5">{n.ip_address} • {n.latency_ms}ms</text>
                  </g>
                ))}

                {/* Zone 3 Nodes: DB, OpenSearch, Connectors */}
                {dataNodes.concat(coreNodes.slice(3)).slice(0, 3).map((n, i) => (
                  <g
                    key={n.id}
                    className="topology-node-badge"
                    transform={`translate(530, ${65 + i * 75})`}
                    onClick={() => setSelectedNodeId(n.id)}
                  >
                    <rect
                      width="190"
                      height="58"
                      rx="6"
                      fill={selectedNodeId === n.id ? "var(--panel-raised)" : "var(--panel)"}
                      stroke={selectedNodeId === n.id ? "var(--accent)" : "var(--line)"}
                      strokeWidth={selectedNodeId === n.id ? "2" : "1"}
                    />
                    <circle
                      cx="16"
                      cy="22"
                      r="5"
                      fill={n.status === "ONLINE" ? "var(--cyan)" : "var(--warning)"}
                      filter="url(#glow)"
                    />
                    <text x="28" y="25" fill="var(--text)" fontSize="11" fontWeight="700">
                      {n.name.length > 20 ? n.name.slice(0, 18) + "..." : n.name}
                    </text>
                    <text x="28" y="44" fill="var(--muted)" fontSize="9.5">{n.ip_address}</text>
                  </g>
                ))}

                {/* Zone 4 Nodes: Monitored Endpoints / Assets */}
                {(endpointNodes.length > 0 ? endpointNodes : [
                  { id: "wkstn-demo-01", name: "WKSTN-ADMIN-01", ip_address: "10.0.2.55", status: "ONLINE", latency_ms: 12 },
                  { id: "srv-demo-dc", name: "SRV-DC01", ip_address: "10.0.2.10", status: warningCount > 0 ? "WARNING" : "ONLINE", latency_ms: 8 },
                  { id: "wkstn-demo-02", name: "WKSTN-FIN-03", ip_address: "10.0.2.88", status: "ONLINE", latency_ms: 14 }
                ]).slice(0, 3).map((n: any, i) => (
                  <g
                    key={n.id}
                    className="topology-node-badge"
                    transform={`translate(775, ${65 + i * 75})`}
                    onClick={() => setSelectedNodeId(n.id)}
                  >
                    <rect
                      width="170"
                      height="58"
                      rx="6"
                      fill={selectedNodeId === n.id ? "var(--panel-raised)" : "var(--panel)"}
                      stroke={n.status === "WARNING" ? "var(--warning)" : selectedNodeId === n.id ? "var(--accent)" : "var(--line)"}
                      strokeWidth={selectedNodeId === n.id || n.status === "WARNING" ? "2" : "1"}
                    />
                    <circle
                      cx="16"
                      cy="22"
                      r="5"
                      fill={n.status === "WARNING" ? "var(--warning)" : "var(--success)"}
                      filter="url(#glow)"
                    />
                    <text x="28" y="25" fill="var(--text)" fontSize="11" fontWeight="700">
                      {n.name.length > 18 ? n.name.slice(0, 16) + "..." : n.name}
                    </text>
                    <text x="28" y="44" fill="var(--muted)" fontSize="9.5">{n.ip_address}</text>
                  </g>
                ))}
              </svg>
            </div>
          )}

          {/* TABLE VIEW */}
          {viewMode === "list" && (
            <div>
              {/* Filter Bar */}
              <div className="topology-table-filter-bar">
                <input
                  type="search"
                  className="topology-filter-input"
                  placeholder={i18n.language.startsWith("es") ? "🔍 Filtrar nodo, IP, tipo..." : "🔍 Filter node, IP, type..."}
                  value={searchFilter}
                  onChange={(e) => setSearchFilter(e.target.value)}
                />
                <div className="topology-tier-filters">
                  {[
                    { key: "ALL", label: i18n.language.startsWith("es") ? "Todos" : "All" },
                    { key: "GATEWAY", label: "DMZ" },
                    { key: "CORE", label: "SecOps / SIEM" },
                    { key: "DATA", label: i18n.language.startsWith("es") ? "Datos / Conectores" : "Data / Connectors" },
                    { key: "ENDPOINTS", label: "Endpoints" },
                  ].map((filter) => (
                    <button
                      key={filter.key}
                      type="button"
                      className={`topology-tier-pill ${tierFilter === filter.key ? "active" : ""}`}
                      onClick={() => setTierFilter(filter.key)}
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
                      <th>{i18n.language.startsWith("es") ? "Nodo / Activo" : "Node / Asset"}</th>
                      <th>{i18n.language.startsWith("es") ? "Capa / Tipo" : "Layer / Type"}</th>
                      <th>{i18n.language.startsWith("es") ? "Dirección IP" : "IP Address"}</th>
                      <th>{i18n.language.startsWith("es") ? "Subred" : "Subnet"}</th>
                      <th>{i18n.language.startsWith("es") ? "Latencia" : "Latency"}</th>
                      <th>{i18n.language.startsWith("es") ? "Alertas Activas" : "Active Alerts"}</th>
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
                            <code className="topology-ip-code">{node.ip_address}</code>
                          </td>
                          <td style={{ color: "var(--text-soft)", fontSize: "0.8rem" }}>
                            {node.subnet}
                          </td>
                          <td>
                            <span style={{ fontSize: "0.8rem", color: "var(--text-soft)" }}>
                              ⚡ {node.latency_ms} ms
                            </span>
                          </td>
                          <td>
                            {node.active_alerts_count > 0 ? (
                              <span className="status warning" style={{ fontSize: "0.75rem" }}>
                                ⚠️ {node.active_alerts_count} {i18n.language.startsWith("es") ? "alerta(s)" : "alert(s)"}
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
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <strong style={{ fontSize: "1.05rem", color: "var(--text)" }}>{selectedNode.name}</strong>
                    <span className={`status ${selectedNode.status === "ONLINE" ? "success" : "warning"}`}>
                      {selectedNode.status}
                    </span>
                    <span className="status" style={{ fontSize: "0.75rem" }}>{selectedNode.type}</span>
                  </div>
                  <p style={{ margin: "4px 0 0", color: "var(--muted)", fontSize: "0.85rem" }}>
                    {i18n.language.startsWith("es") ? selectedNode.role_description_es : selectedNode.role_description_en}
                  </p>
                </div>

                <div style={{ display: "flex", gap: "18px", fontSize: "0.85rem" }}>
                  <div>
                    <span className="muted" style={{ display: "block" }}>IP Address</span>
                    <strong className="topology-ip-code">{selectedNode.ip_address}</strong>
                  </div>
                  <div>
                    <span className="muted" style={{ display: "block" }}>Subnet</span>
                    <strong>{selectedNode.subnet}</strong>
                  </div>
                  <div>
                    <span className="muted" style={{ display: "block" }}>Latency</span>
                    <strong>{selectedNode.latency_ms} ms</strong>
                  </div>
                </div>
              </div>

              {selectedNode.active_alerts && selectedNode.active_alerts.length > 0 && (
                <div style={{ marginTop: "12px", paddingTop: "10px", borderTop: "1px solid var(--line)" }}>
                  <strong style={{ fontSize: "0.82rem", color: "var(--warning)" }}>
                    ⚠️ {i18n.language.startsWith("es") ? "Alertas de Seguridad Asociadas" : "Associated Security Alerts"} ({selectedNode.active_alerts.length}):
                  </strong>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "6px" }}>
                    {selectedNode.active_alerts.map((al) => (
                      <span key={al.id} className="status warning" style={{ fontSize: "0.75rem" }}>
                        {al.title} ({al.severity})
                      </span>
                    ))}
                  </div>
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

