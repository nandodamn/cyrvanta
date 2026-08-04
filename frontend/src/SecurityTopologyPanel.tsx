import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { getNetworkTopology, type TopologyNode } from "./api";
import { NetworkTopologyModal } from "./NetworkTopologyModal";

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

export function SecurityTopologyPanel() {
  const { t } = useTranslation();
  const [isModalOpen, setIsModalOpen] = useState(false);

  const topology = useQuery({
    queryKey: ["operations", "topology"],
    queryFn: getNetworkTopology,
    refetchInterval: 30_000,
  });

  const nodes = topology.data?.nodes && topology.data.nodes.length > 0 ? topology.data.nodes : DEFAULT_NODES;
  const onlineCount = nodes.filter((n) => n.status === "ONLINE").length;

  return (
    <>
      <article className="panel topology-panel" style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
        <div className="panel-heading" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "12px" }}>
          <div>
            <p className="eyebrow">{t("monitoredEnvironment")}</p>
            <h2 style={{ margin: "4px 0 0" }}>{t("securityTopology")}</h2>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span
              style={{
                background: "rgba(13, 209, 155, 0.1)",
                border: "1px solid var(--accent)",
                color: "var(--accent)",
                fontSize: "0.75rem",
                padding: "3px 10px",
                borderRadius: "4px",
                fontWeight: 700,
                letterSpacing: "0.03em",
              }}
            >
              LIVE · {onlineCount}/{nodes.length} NODES
            </span>

            <button
              type="button"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "6px 14px",
                fontSize: "0.85rem",
                fontWeight: 600,
                borderRadius: "6px",
                background: "var(--panel-raised)",
                border: "1px solid var(--accent)",
                color: "var(--accent)",
                cursor: "pointer",
                transition: "all 0.2s ease",
              }}
              onClick={() => setIsModalOpen(true)}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
                <line x1="11" y1="8" x2="11" y2="14" />
                <line x1="8" y1="11" x2="14" y2="11" />
              </svg>
              {t("expandTopology", { defaultValue: "Ampliar Topología de Red" })}
            </button>
          </div>
        </div>

        {/* Live Interactive Network Map Strip */}
        <div
          style={{
            background: "var(--panel-raised, #081714)",
            border: "1px solid var(--line, #13241f)",
            borderRadius: "8px",
            padding: "1.25rem",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px" }}>
            <span style={{ fontSize: "0.8rem", fontWeight: 700, color: "var(--accent)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              🌐 Infraestructura SOC & Direcciones IP Conectadas
            </span>
            <span style={{ fontSize: "0.75rem", color: "var(--muted)" }}>
              Haz clic en cualquier nodo o en ampliar para inspeccionar
            </span>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: "12px",
              width: "100%",
            }}
          >
            {nodes.map((node) => (
              <div
                key={node.id}
                style={{
                  background: "var(--panel)",
                  border: "1px solid var(--line)",
                  borderRadius: "6px",
                  padding: "10px 12px",
                  display: "flex",
                  flexDirection: "column",
                  gap: "6px",
                  cursor: "pointer",
                  transition: "all 0.2s ease",
                }}
                onClick={() => setIsModalOpen(true)}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <strong style={{ fontSize: "0.85rem", color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {node.name}
                  </strong>
                  <span
                    style={{
                      width: "8px",
                      height: "8px",
                      borderRadius: "50%",
                      flexShrink: 0,
                      background: node.status === "ONLINE" ? "var(--accent)" : "#ffb703",
                      boxShadow: `0 0 8px ${node.status === "ONLINE" ? "var(--accent)" : "#ffb703"}`,
                    }}
                  />
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.8rem" }}>
                  <span style={{ fontFamily: "monospace", color: "var(--accent)", fontWeight: 600 }}>{node.ip_address}</span>
                  <span style={{ color: "var(--muted)", fontSize: "0.75rem" }}>{node.latency_ms} ms</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Managed Core Stack Integration Badges */}
        <div className="topology-services" style={{ marginTop: "4px" }}>
          <div>
            <strong>Ollama · Gemma 4</strong>
            <small>{t("assistedAnalysis")}</small>
          </div>
          <div>
            <strong>Wazuh SIEM Manager</strong>
            <small>{t("detectionEngine")}</small>
          </div>
          <div>
            <strong>n8n Workflows</strong>
            <small>{t("approvedAutomation")}</small>
          </div>
          <div>
            <strong>PostgreSQL 16 RLS</strong>
            <small>{t("traceableHistory")}</small>
          </div>
        </div>
      </article>

      <NetworkTopologyModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} />
    </>
  );
}
