import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { getNetworkTopology, type TopologyNode } from "./api";

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

const DEFAULT_NODES: TopologyNode[] = [
  {
    id: "fw-01",
    name: "Perimeter Firewall PA-3200",
    type: "FIREWALL",
    ip_address: "192.168.1.1",
    subnet: "192.168.1.0/24 (DMZ Edge)",
    status: "WARNING",
    latency_ms: 2,
    last_ping: new Date().toISOString(),
    active_alerts_count: 2,
    active_alerts: [
      {
        id: "alt-fw-01",
        title: "Intentos de escaneo de puertos (Port Scan) desde IP externa",
        severity: "high",
        category: "Network Security",
        observed_at: new Date().toISOString(),
      },
      {
        id: "alt-fw-02",
        title: "Bloqueo de reglas de filtrado perimetral PaloAlto PA-3200",
        severity: "medium",
        category: "Firewall Rules",
        observed_at: new Date().toISOString(),
      },
    ],
    role_description_es: "Firewall perimetral inspeccionando tráfico de entrada y salida con filtrado de amenazas.",
    role_description_en: "Perimeter firewall inspecting ingress/egress traffic with threat filtering.",
  },
  {
    id: "gtw-01",
    name: "NGINX API Gateway",
    type: "GATEWAY",
    ip_address: "192.168.1.50",
    subnet: "192.168.1.0/24 (DMZ Edge)",
    status: "ONLINE",
    latency_ms: 4,
    last_ping: new Date().toISOString(),
    active_alerts_count: 0,
    active_alerts: [],
    role_description_es: "Gateway seguro terminando SSL/TLS y enrutando peticiones REST a los microservicios.",
    role_description_en: "Secure gateway terminating SSL/TLS and routing REST requests to microservices.",
  },
  {
    id: "app-01",
    name: "Cyrvanta FastAPI Server",
    type: "SERVER",
    ip_address: "10.0.4.10",
    subnet: "10.0.4.0/24 (Internal Core)",
    status: "ONLINE",
    latency_ms: 8,
    last_ping: new Date().toISOString(),
    active_alerts_count: 0,
    active_alerts: [],
    role_description_es: "Servidor de aplicación Clean Architecture procesando lógica de negocio y contexto de seguridad.",
    role_description_en: "Clean Architecture application server processing business logic and security context.",
  },
  {
    id: "db-01",
    name: "PostgreSQL 16 RLS Cluster",
    type: "DATABASE",
    ip_address: "10.0.4.25",
    subnet: "10.0.4.0/24 (Internal Core)",
    status: "ONLINE",
    latency_ms: 3,
    last_ping: new Date().toISOString(),
    active_alerts_count: 0,
    active_alerts: [],
    role_description_es: "Base de datos autoritativa relacional con seguridad por filas (Row Level Security) aislada por tenant.",
    role_description_en: "Authoritative relational database with tenant-isolated Row Level Security (RLS).",
  },
  {
    id: "siem-01",
    name: "Wazuh SIEM Manager",
    type: "SIEM",
    ip_address: "172.16.0.5",
    subnet: "172.16.0.0/16 (SOC Infra)",
    status: "WARNING",
    latency_ms: 12,
    last_ping: new Date().toISOString(),
    active_alerts_count: 1,
    active_alerts: [
      {
        id: "alt-siem-01",
        title: "Regla Wazuh #5710: Múltiples fallos de autenticación SSH",
        severity: "critical",
        category: "Authentication",
        observed_at: new Date().toISOString(),
      },
    ],
    role_description_es: "Motor SIEM recopilando eventos de agentes, correlación de reglas y telemetría Wazuh.",
    role_description_en: "SIEM engine collecting agent events, rule correlation, and Wazuh telemetry.",
  },
  {
    id: "ep-srv02",
    name: "Core AD / LDAP Server",
    type: "ENDPOINT",
    ip_address: "10.0.4.12",
    subnet: "10.0.4.0/24 (Internal Core)",
    status: "WARNING",
    latency_ms: 15,
    last_ping: new Date().toISOString(),
    active_alerts_count: 1,
    active_alerts: [
      {
        id: "alt-ad-01",
        title: "Intento de elevación de privilegios LDAP en controlador de dominio",
        severity: "high",
        category: "Identity Security",
        observed_at: new Date().toISOString(),
      },
    ],
    role_description_es: "Servidor de identidades AD/LDAP monitoreado contra intentos de fuerza bruta.",
    role_description_en: "AD/LDAP identity server monitored against brute force attempts.",
  },
];

export function NetworkTopologyModal({ isOpen, onClose }: Props) {
  const { i18n } = useTranslation();
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>("app-01");

  const topology = useQuery({
    queryKey: ["operations", "topology"],
    queryFn: getNetworkTopology,
    enabled: isOpen,
    refetchInterval: 15_000,
  });

  if (!isOpen) return null;

  const nodes = topology.data?.nodes && topology.data.nodes.length > 0 ? topology.data.nodes : DEFAULT_NODES;
  const selectedNode = nodes.find((node) => node.id === selectedNodeId) ?? nodes[0];

  const getStatusColor = (status: TopologyNode["status"]) => {
    switch (status) {
      case "ONLINE":
        return "var(--accent)";
      case "WARNING":
        return "#ffb703";
      case "OFFLINE":
        return "#e63946";
      default:
        return "var(--muted)";
    }
  };

  const getTypeIcon = (type: TopologyNode["type"]) => {
    switch (type) {
      case "FIREWALL":
        return (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
        );
      case "GATEWAY":
        return (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <line x1="2" y1="12" x2="22" y2="12" />
            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
          </svg>
        );
      case "SERVER":
        return (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="2" y="2" width="20" height="8" rx="2" ry="2" />
            <rect x="2" y="14" width="20" height="8" rx="2" ry="2" />
            <line x1="6" y1="6" x2="6.01" y2="6" />
            <line x1="6" y1="18" x2="6.01" y2="18" />
          </svg>
        );
      case "DATABASE":
        return (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <ellipse cx="12" cy="5" rx="9" ry="3" />
            <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
            <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
          </svg>
        );
      case "SIEM":
        return (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="12 2 2 7 12 12 22 7 12 2" />
            <polyline points="2 17 12 22 22 17" />
            <polyline points="2 12 12 17 22 12" />
          </svg>
        );
      case "ENDPOINT":
      default:
        return (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
            <line x1="8" y1="21" x2="16" y2="21" />
            <line x1="12" y1="17" x2="12" y2="21" />
          </svg>
        );
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        background: "rgba(3, 10, 8, 0.88)",
        backdropFilter: "blur(8px)",
        display: "flex",
        justify: "center",
        alignItems: "center",
        padding: "1.5rem",
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "1280px",
          height: "90vh",
          background: "var(--bg-main, #040c0a)",
          border: "1px solid var(--panel-border, #1a2f29)",
          borderRadius: "12px",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          boxShadow: "0 24px 48px rgba(0, 0, 0, 0.6)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Top Header */}
        <div
          style={{
            padding: "1rem 1.5rem",
            borderBottom: "1px solid var(--line, #13241f)",
            display: "flex",
            justify: "space-between",
            alignItems: "center",
            background: "var(--panel-raised, #081714)",
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <h2 style={{ margin: 0, fontSize: "1.25rem", color: "var(--text)" }}>
                🗺️ Mapa de Topología de Red & Seguridad SOC
              </h2>
              <span
                style={{
                  background: "var(--panel)",
                  border: "1px solid var(--accent)",
                  color: "var(--accent)",
                  fontSize: "0.75rem",
                  padding: "2px 8px",
                  borderRadius: "4px",
                  fontWeight: 600,
                }}
              >
                LIVE MONITORING
              </span>
            </div>
            <p style={{ margin: "4px 0 0", fontSize: "0.85rem", color: "var(--muted)" }}>
              Mapa de infraestructura, estado de conectividad IP y correlación de seguridad multi-tenant.
            </p>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <button
              type="button"
              className="ghost"
              style={{ fontSize: "0.85rem" }}
              onClick={() => topology.refetch()}
            >
              🔄 Refrescar
            </button>
            <button
              type="button"
              className="ghost"
              style={{
                fontSize: "1.2rem",
                padding: "4px 12px",
                borderRadius: "6px",
                border: "1px solid var(--line)",
              }}
              onClick={onClose}
            >
              ✕
            </button>
          </div>
        </div>

        {/* Modal Main Body Grid */}
        <div
          style={{
            flex: 1,
            display: "grid",
            gridTemplateColumns: "1fr 340px",
            overflow: "hidden",
          }}
        >
          {/* Main Visual Topology Diagram Area */}
          <div
            style={{
              padding: "1.5rem",
              overflowY: "auto",
              background: "#020806",
              display: "flex",
              flexDirection: "column",
              gap: "1.5rem",
            }}
          >
            {topology.isLoading && <p style={{ color: "var(--muted)" }}>Cargando topología de red...</p>}

            {nodes.length > 0 && (
              <>
                {/* Subnet Zone 1: DMZ Perimetral */}
                <div
                  style={{
                    border: "1px dashed #1a3c33",
                    borderRadius: "8px",
                    padding: "1.25rem",
                    background: "rgba(13, 209, 155, 0.02)",
                  }}
                >
                  <p style={{ margin: "0 0 12px", fontSize: "0.8rem", color: "var(--accent)", fontWeight: 700, letterSpacing: "0.05em" }}>
                    🌐 ZONA 1: DMZ & EDGE PERIMETRAL (192.168.1.0/24)
                  </p>
                  <div style={{ display: "flex", gap: "1.25rem", flexWrap: "wrap" }}>
                    {nodes
                      .filter((n) => n.subnet.includes("DMZ"))
                      .map((node) => (
                        <div
                          key={node.id}
                          style={{
                            flex: "1 1 260px",
                            padding: "1rem",
                            borderRadius: "8px",
                            background: selectedNodeId === node.id ? "rgba(13, 209, 155, 0.12)" : "var(--panel-raised, #081714)",
                            border: selectedNodeId === node.id ? "1.5px solid var(--accent)" : "1px solid var(--line)",
                            cursor: "pointer",
                            transition: "all 0.2s ease",
                          }}
                          onClick={() => setSelectedNodeId(node.id)}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                            <div style={{ display: "flex", alignItems: "center", gap: "8px", color: getStatusColor(node.status) }}>
                              {getTypeIcon(node.type)}
                              <strong style={{ fontSize: "0.95rem", color: "var(--text)" }}>{node.name}</strong>
                            </div>
                            <span
                              style={{
                                width: "10px",
                                height: "10px",
                                borderRadius: "50%",
                                background: getStatusColor(node.status),
                                boxShadow: `0 0 8px ${getStatusColor(node.status)}`,
                              }}
                            />
                          </div>

                          <div style={{ marginTop: "10px", display: "flex", justifyContent: "space-between", fontSize: "0.85rem" }}>
                            <span style={{ fontFamily: "monospace", color: "var(--accent)" }}>{node.ip_address}</span>
                            <span style={{ color: "var(--muted)" }}>{node.latency_ms} ms</span>
                          </div>
                        </div>
                      ))}
                  </div>
                </div>

                {/* Connection Flow Arrow */}
                <div style={{ textAlign: "center", color: "var(--accent)", opacity: 0.6, fontSize: "1.2rem" }}>
                  ↓ HTTPS / TLS 1.3 Ingestion ↓
                </div>

                {/* Subnet Zone 2: Core Interno */}
                <div
                  style={{
                    border: "1px dashed #1a3c33",
                    borderRadius: "8px",
                    padding: "1.25rem",
                    background: "rgba(13, 209, 155, 0.02)",
                  }}
                >
                  <p style={{ margin: "0 0 12px", fontSize: "0.8rem", color: "var(--accent)", fontWeight: 700, letterSpacing: "0.05em" }}>
                    🏢 ZONA 2: CORE INTERNO & BASE DE DATOS (10.0.4.0/24)
                  </p>
                  <div style={{ display: "flex", gap: "1.25rem", flexWrap: "wrap" }}>
                    {nodes
                      .filter((n) => n.subnet.includes("Internal Core"))
                      .map((node) => (
                        <div
                          key={node.id}
                          style={{
                            flex: "1 1 260px",
                            padding: "1rem",
                            borderRadius: "8px",
                            background: selectedNodeId === node.id ? "rgba(13, 209, 155, 0.12)" : "var(--panel-raised, #081714)",
                            border: selectedNodeId === node.id ? "1.5px solid var(--accent)" : "1px solid var(--line)",
                            cursor: "pointer",
                            transition: "all 0.2s ease",
                          }}
                          onClick={() => setSelectedNodeId(node.id)}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                            <div style={{ display: "flex", alignItems: "center", gap: "8px", color: getStatusColor(node.status) }}>
                              {getTypeIcon(node.type)}
                              <strong style={{ fontSize: "0.95rem", color: "var(--text)" }}>{node.name}</strong>
                            </div>
                            <span
                              style={{
                                width: "10px",
                                height: "10px",
                                borderRadius: "50%",
                                background: getStatusColor(node.status),
                                boxShadow: `0 0 8px ${getStatusColor(node.status)}`,
                              }}
                            />
                          </div>

                          <div style={{ marginTop: "10px", display: "flex", justifyContent: "space-between", fontSize: "0.85rem" }}>
                            <span style={{ fontFamily: "monospace", color: "var(--accent)" }}>{node.ip_address}</span>
                            <span style={{ color: "var(--muted)" }}>{node.latency_ms} ms</span>
                          </div>
                        </div>
                      ))}
                  </div>
                </div>

                {/* Connection Flow Arrow */}
                <div style={{ textAlign: "center", color: "var(--accent)", opacity: 0.6, fontSize: "1.2rem" }}>
                  ↔ Telemetría SIEM & Syslog ↔
                </div>

                {/* Subnet Zone 3: SOC Infraestructura */}
                <div
                  style={{
                    border: "1px dashed #1a3c33",
                    borderRadius: "8px",
                    padding: "1.25rem",
                    background: "rgba(13, 209, 155, 0.02)",
                  }}
                >
                  <p style={{ margin: "0 0 12px", fontSize: "0.8rem", color: "var(--accent)", fontWeight: 700, letterSpacing: "0.05em" }}>
                    🛡️ ZONA 3: SOC SIEM & TELEMETRÍA (172.16.0.0/16)
                  </p>
                  <div style={{ display: "flex", gap: "1.25rem", flexWrap: "wrap" }}>
                    {nodes
                      .filter((n) => n.subnet.includes("SOC Infra"))
                      .map((node) => (
                        <div
                          key={node.id}
                          style={{
                            flex: "1 1 260px",
                            padding: "1rem",
                            borderRadius: "8px",
                            background: selectedNodeId === node.id ? "rgba(13, 209, 155, 0.12)" : "var(--panel-raised, #081714)",
                            border: selectedNodeId === node.id ? "1.5px solid var(--accent)" : "1px solid var(--line)",
                            cursor: "pointer",
                            transition: "all 0.2s ease",
                          }}
                          onClick={() => setSelectedNodeId(node.id)}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                            <div style={{ display: "flex", alignItems: "center", gap: "8px", color: getStatusColor(node.status) }}>
                              {getTypeIcon(node.type)}
                              <strong style={{ fontSize: "0.95rem", color: "var(--text)" }}>{node.name}</strong>
                            </div>
                            <span
                              style={{
                                width: "10px",
                                height: "10px",
                                borderRadius: "50%",
                                background: getStatusColor(node.status),
                                boxShadow: `0 0 8px ${getStatusColor(node.status)}`,
                              }}
                            />
                          </div>

                          <div style={{ marginTop: "10px", display: "flex", justifyContent: "space-between", fontSize: "0.85rem" }}>
                            <span style={{ fontFamily: "monospace", color: "var(--accent)" }}>{node.ip_address}</span>
                            <span style={{ color: "var(--muted)" }}>{node.latency_ms} ms</span>
                          </div>
                        </div>
                      ))}
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Right Inspector Drawer */}
          {selectedNode && (
            <div
              style={{
                borderLeft: "1px solid var(--line, #13241f)",
                padding: "1.25rem",
                background: "var(--panel-raised, #081714)",
                display: "flex",
                flexDirection: "column",
                gap: "1rem",
                overflowY: "auto",
              }}
            >
              <div>
                <span style={{ fontSize: "0.75rem", color: "var(--muted)", textTransform: "uppercase", fontWeight: 700 }}>
                  Inspección de Nodo
                </span>
                <h3 style={{ margin: "4px 0 0", fontSize: "1.1rem" }}>{selectedNode.name}</h3>
              </div>

              <div
                style={{
                  background: "var(--panel)",
                  padding: "10px 12px",
                  borderRadius: "6px",
                  border: "1px solid var(--line)",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                  <span style={{ fontSize: "0.8rem", color: "var(--muted)" }}>Dirección IP</span>
                  <strong style={{ fontFamily: "monospace", color: "var(--accent)", fontSize: "0.9rem" }}>
                    {selectedNode.ip_address}
                  </strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                  <span style={{ fontSize: "0.8rem", color: "var(--muted)" }}>Subred</span>
                  <span style={{ fontSize: "0.8rem", color: "var(--text)" }}>{selectedNode.subnet}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                  <span style={{ fontSize: "0.8rem", color: "var(--muted)" }}>Estado de Red</span>
                  <span style={{ fontSize: "0.8rem", fontWeight: 700, color: getStatusColor(selectedNode.status) }}>
                    {selectedNode.status}
                  </span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ fontSize: "0.8rem", color: "var(--muted)" }}>Latencia ICMP</span>
                  <span style={{ fontSize: "0.8rem", color: "var(--text)" }}>{selectedNode.latency_ms} ms</span>
                </div>
              </div>

              <div>
                <h4 style={{ margin: "0 0 6px", fontSize: "0.85rem", color: "var(--muted)" }}>Rol Operacional</h4>
                <p style={{ fontSize: "0.85rem", lineHeight: 1.5, margin: 0, color: "var(--text)" }}>
                  {i18n.language.startsWith("es")
                    ? selectedNode.role_description_es
                    : selectedNode.role_description_en}
                </p>
              </div>

              <div>
                <h4 style={{ margin: "0 0 6px", fontSize: "0.85rem", color: "var(--muted)" }}>Alarmas de Seguridad Activas</h4>
                <div
                  style={{
                    padding: "10px 12px",
                    borderRadius: "6px",
                    background: selectedNode.active_alerts_count > 0 ? "rgba(230, 57, 70, 0.1)" : "var(--panel)",
                    border: selectedNode.active_alerts_count > 0 ? "1px solid #e63946" : "1px solid var(--line)",
                  }}
                >
                  <span style={{ fontSize: "0.9rem", fontWeight: 700, color: selectedNode.active_alerts_count > 0 ? "#e63946" : "var(--accent)" }}>
                    {selectedNode.active_alerts_count > 0
                      ? `⚠️ ${selectedNode.active_alerts_count} Alarma(s) Detectadas`
                      : "✓ Sin alarmas en este nodo"}
                  </span>
                </div>

                {/* Detailed Active Alarms List */}
                {selectedNode.active_alerts && selectedNode.active_alerts.length > 0 && (
                  <div style={{ marginTop: "10px", display: "flex", flexDirection: "column", gap: "8px" }}>
                    {selectedNode.active_alerts.map((alert) => (
                      <div
                        key={alert.id}
                        style={{
                          background: "#0b1a16",
                          border: "1px solid rgba(230, 57, 70, 0.35)",
                          borderLeft: `4px solid ${
                            alert.severity === "critical"
                              ? "#e63946"
                              : alert.severity === "high"
                              ? "#ffb703"
                              : "var(--accent)"
                          }`,
                          borderRadius: "6px",
                          padding: "8px 10px",
                          fontSize: "0.8rem",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                          <span
                            style={{
                              fontSize: "0.68rem",
                              fontWeight: 700,
                              textTransform: "uppercase",
                              padding: "1px 6px",
                              borderRadius: "3px",
                              background:
                                alert.severity === "critical"
                                  ? "rgba(230, 57, 70, 0.2)"
                                  : "rgba(255, 183, 3, 0.2)",
                              color: alert.severity === "critical" ? "#e63946" : "#ffb703",
                            }}
                          >
                            {alert.severity}
                          </span>
                          <span style={{ fontSize: "0.7rem", color: "var(--muted)" }}>{alert.category}</span>
                        </div>
                        <p style={{ margin: 0, fontWeight: 600, color: "var(--text)", lineHeight: 1.35 }}>
                          {alert.title}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div style={{ marginTop: "auto", paddingTop: "1rem" }}>
                <button
                  type="button"
                  style={{ width: "100%", padding: "10px" }}
                  onClick={() => {
                    navigator.clipboard.writeText(selectedNode.ip_address);
                  }}
                >
                  📋 Copiar Dirección IP
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
