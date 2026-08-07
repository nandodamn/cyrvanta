import React from "react";
import { useTranslation } from "react-i18next";
import { PlaybookDefinition } from "./api";

interface PlaybookDetailsModalProps {
  playbook: PlaybookDefinition;
  requiredIntegration?: { connectorName: string; navTab: string };
  onClose: () => void;
}

const PLAYBOOK_ACTION_DETAILS: Record<
  string,
  {
    parameters: Array<{ name: string; type: string; required: boolean; description: string }>;
    executionSteps: string[];
    mitreTactics: string;
  }
> = {
  "simulate-user-block": {
    parameters: [
      { name: "username", type: "string (email)", required: true, description: "Identificador/email de la cuenta objetivo a bloquear." },
      { name: "reason", type: "string", required: true, description: "Causa justificada o vector de ataque correlacionado." },
      { name: "duration_minutes", type: "integer", required: false, description: "Duración del bloqueo temporal (opcional, por defecto indeterminado)." },
      { name: "revoke_active_sessions", type: "boolean", required: false, description: "Si es true, inyecta revocación de tokens JWT en Redis." },
    ],
    executionSteps: [
      "Paso 1: Valida firma de gobernanza (Principio de 4-Ojos si requiere aprobación).",
      "Paso 2: Actualiza la cuenta a is_active = false en la base de datos de usuarios.",
      "Paso 3: Si LDAP está configurado, modifica userAccountControl = 514 en el Active Directory.",
      "Paso 4: Invalida las sesiones JWT activas en Redis.",
      "Paso 5: Emite evento inmutable en Auditoría y habilita el botón de Rollback.",
    ],
    mitreTactics: "Credential Access (T1110), Defense Evasion / Valid Accounts (T1078), Account Manipulation (T1098)",
  },
  "simulate-host-isolation": {
    parameters: [
      { name: "device_id", type: "string (hostname/IP)", required: true, description: "Identificador único o IP del servidor/workstation a aislar." },
      { name: "isolation_type", type: "enum (FULL | SELECTIVE)", required: false, description: "Nivel de contención de red." },
      { name: "reason", type: "string", required: true, description: "Justificación forense de contención." },
    ],
    executionSteps: [
      "Paso 1: Involucra el conector Microsoft Defender / EDR configurado.",
      "Paso 2: Corta todo el tráfico IP saliente/entrante del host excepto el canal TLS de gestión.",
      "Paso 3: Registra el hash de snapshot de evidencia en OpenSearch.",
      "Paso 4: Habilita el procedimiento de Rollback de reconexión de red.",
    ],
    mitreTactics: "Execution (T1059), Lateral Movement (T1021), Command and Control (T1071)",
  },
  "simulate-critical-incident-notification": {
    parameters: [
      { name: "incident_id", type: "UUID", required: true, description: "Identificador del incidente de alta prioridad." },
      { name: "channels", type: "array[string]", required: true, description: "Canales de despacho (EMAIL, TEAMS, SLACK, ITSM)." },
      { name: "recipients", type: "array[email]", required: true, description: "Lista de correos de guardia del SOC/CISO." },
    ],
    executionSteps: [
      "Paso 1: Compone el reporte ejecutivo bilingüe (i18n es/en) con la causa raíz.",
      "Paso 2: Despacha la notificación por SMTP Mailer y Webhooks corporativos.",
      "Paso 3: Almacena el recibo de entrega inmutable con status = DELIVERED.",
    ],
    mitreTactics: "Impact / Incident Escalation & Response (T1486)",
  },
  "simulate-itsm-ticket-creation": {
    parameters: [
      { name: "system", type: "enum (servicenow | jira)", required: true, description: "Plataforma ITSM destino." },
      { name: "priority", type: "string (HIGH | CRITICAL)", required: true, description: "Prioridad del ticket en SecOps." },
      { name: "description", type: "string", required: true, description: "Resumen de hallazgos y evidencias adjuntas." },
    ],
    executionSteps: [
      "Paso 1: Consulta la API REST del conector ServiceNow o Jira.",
      "Paso 2: Apertura el ticket de incidente retornando la clave autoritativa (INC0094812 / SOC-1042).",
      "Paso 3: Vincula el número de ticket al incidente en la base de datos de Cyrvanta.",
    ],
    mitreTactics: "Command and Control / Application Protocol (T1071)",
  },
  "lateral-movement": {
    parameters: [
      { name: "source_ip", type: "string (IP)", required: true, description: "IP del host origen del salto lateral." },
      { name: "target_ip", type: "string (IP)", required: true, description: "IP del host destino bajo amenaza." },
      { name: "revoke_tokens", type: "boolean", required: false, description: "Invalida tokens de sesión entre ambos nodos." },
    ],
    executionSteps: [
      "Paso 1: Interrumpe la regla de comunicación SMB/WinRM entre la IP origen y destino.",
      "Paso 2: Revoca los tokens de sesión de red compartida.",
      "Paso 3: Genera la transacción compensatoria para el Rollback.",
    ],
    mitreTactics: "Lateral Movement / Remote Services (T1021), Valid Accounts (T1078)",
  },
};

export function PlaybookDetailsModal({ playbook, requiredIntegration, onClose }: PlaybookDetailsModalProps) {
  const { i18n } = useTranslation();
  const details = PLAYBOOK_ACTION_DETAILS[playbook.code] || {
    parameters: [{ name: "incident_id", type: "UUID", required: true, description: "Identificador del incidente objetivo." }],
    executionSteps: [
      "Paso 1: Valida las firmas de gobernanza de disparo.",
      "Paso 2: Ejecuta la acción de contención nativa de Cyrvanta.",
      "Paso 3: Registra auditoría inmutable y habilita el Rollback.",
    ],
    mitreTactics: "Defense Evasion / Valid Accounts (T1078)",
  };

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: "rgba(0, 0, 0, 0.75)",
        backdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 9999,
        padding: "1rem",
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: "var(--panel)",
          border: "1px solid var(--panel-border)",
          borderRadius: "12px",
          width: "100%",
          maxWidth: "750px",
          maxHeight: "90vh",
          overflowY: "auto",
          padding: "1.75rem",
          boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.5)",
          color: "var(--text)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "1.25rem", borderBottom: "1px solid var(--line)", paddingBottom: "1rem" }}>
          <div>
            <div style={{ display: "flex", gap: "8px", alignItems: "center", marginBottom: "6px" }}>
              <span className="demo-badge active" style={{ fontSize: "0.75rem" }}>
                {playbook.engine_type || "Cyrvanta Native"}
              </span>
              {requiredIntegration ? (
                <span
                  style={{
                    background: "rgba(245, 158, 11, 0.18)",
                    color: "#f59e0b",
                    border: "1px solid #f59e0b",
                    padding: "2px 8px",
                    borderRadius: "4px",
                    fontSize: "0.75rem",
                    fontWeight: 700,
                  }}
                >
                  🔒 REQUIERE CONFIGURACIÓN
                </span>
              ) : (
                <span style={{ background: "rgba(13, 209, 155, 0.15)", color: "var(--accent)", border: "1px solid var(--accent)", padding: "2px 8px", borderRadius: "4px", fontSize: "0.75rem", fontWeight: 700 }}>
                  ✓ LISTO PARA PRODUCCIÓN
                </span>
              )}
            </div>
            <h2 style={{ margin: 0, fontSize: "1.35rem" }}>
              {i18n.language.startsWith("en") ? playbook.title_i18n.en : playbook.title_i18n.es}
            </h2>
            <code style={{ fontSize: "0.85rem", color: "var(--accent)", background: "var(--panel-raised)", padding: "2px 6px", borderRadius: "4px" }}>
              {playbook.code}
            </code>
          </div>
          <button
            type="button"
            className="ghost"
            onClick={onClose}
            style={{ fontSize: "1.2rem", padding: "4px 8px", minWidth: "unset", width: "auto", height: "auto" }}
          >
            ✕
          </button>
        </div>

        {/* Integration Warning Banner if missing connector */}
        {requiredIntegration && (
          <div style={{ background: "rgba(245, 158, 11, 0.1)", border: "1px solid rgba(245, 158, 11, 0.4)", borderRadius: "8px", padding: "10px 14px", marginBottom: "1.25rem" }}>
            <strong style={{ color: "#f59e0b", display: "block", fontSize: "0.875rem", marginBottom: "2px" }}>
              🔒 Requerimiento de Integración Pendiente
            </strong>
            <p style={{ margin: 0, fontSize: "0.825rem", color: "var(--text-soft)" }}>
              Para ejecutar este playbook en vivo se requiere configurar la URL y llaves API para <strong>{requiredIntegration.connectorName}</strong> en el menú <strong>{requiredIntegration.navTab}</strong>.
            </p>
          </div>
        )}

        {/* Section 1: MITRE ATT&CK Mapping */}
        <div style={{ marginBottom: "1.25rem", background: "var(--panel-raised)", padding: "12px 16px", borderRadius: "8px", border: "1px solid var(--line)" }}>
          <h3 style={{ margin: "0 0 6px", fontSize: "0.95rem", color: "var(--accent)", display: "flex", alignItems: "center", gap: "6px" }}>
            <span>🛡️</span> Mapeo MITRE ATT&CK & Tácticas Mitigadas
          </h3>
          <p style={{ margin: "0 0 6px", fontSize: "0.85rem", color: "var(--text)" }}>
            <strong>Técnicas Oficiales:</strong>{" "}
            <span style={{ color: "#38bdf8", fontFamily: "monospace" }}>
              {playbook.mitre_codes?.length ? playbook.mitre_codes.join(", ") : details.mitreTactics}
            </span>
          </p>
          <p style={{ margin: 0, fontSize: "0.8rem", color: "var(--muted)" }}>
            <strong>Tácticas Cubiertas:</strong> {details.mitreTactics}
          </p>
        </div>

        {/* Section 2: Input Parameters */}
        <div style={{ marginBottom: "1.25rem" }}>
          <h3 style={{ margin: "0 0 8px", fontSize: "0.95rem", color: "var(--text)", display: "flex", alignItems: "center", gap: "6px" }}>
            <span>📋</span> Parámetros de Entrada que Toma el Playbook
          </h3>
          <div style={{ border: "1px solid var(--line)", borderRadius: "6px", overflow: "hidden" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.825rem" }}>
              <thead>
                <tr style={{ background: "var(--panel-raised)", borderBottom: "1px solid var(--line)", textAlign: "left" }}>
                  <th style={{ padding: "8px 12px", color: "var(--muted)" }}>Parámetro</th>
                  <th style={{ padding: "8px 12px", color: "var(--muted)" }}>Tipo</th>
                  <th style={{ padding: "8px 12px", color: "var(--muted)" }}>Requerido</th>
                  <th style={{ padding: "8px 12px", color: "var(--muted)" }}>Descripción</th>
                </tr>
              </thead>
              <tbody>
                {details.parameters.map((param, i) => (
                  <tr key={param.name} style={{ borderBottom: i < details.parameters.length - 1 ? "1px solid var(--line)" : "none" }}>
                    <td style={{ padding: "8px 12px", fontFamily: "monospace", color: "var(--accent)", fontWeight: 700 }}>{param.name}</td>
                    <td style={{ padding: "8px 12px", color: "var(--text-soft)" }}>{param.type}</td>
                    <td style={{ padding: "8px 12px" }}>
                      <span style={{ fontSize: "0.7rem", padding: "2px 6px", borderRadius: "4px", background: param.required ? "rgba(239, 68, 68, 0.15)" : "rgba(255,255,255,0.05)", color: param.required ? "#f87171" : "var(--muted)" }}>
                        {param.required ? "SÍ" : "Opcional"}
                      </span>
                    </td>
                    <td style={{ padding: "8px 12px", color: "var(--muted)" }}>{param.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Section 3: Execution Steps */}
        <div style={{ marginBottom: "1.25rem" }}>
          <h3 style={{ margin: "0 0 8px", fontSize: "0.95rem", color: "var(--text)", display: "flex", alignItems: "center", gap: "6px" }}>
            <span>⚡</span> Secuencia de Ejecución & Acciones Nativas
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            {details.executionSteps.map((step) => (
              <div key={step} style={{ background: "var(--panel-raised)", padding: "8px 12px", borderRadius: "6px", fontSize: "0.825rem", borderLeft: "3px solid var(--accent)", color: "var(--text-soft)" }}>
                {step}
              </div>
            ))}
          </div>
        </div>

        {/* Section 4: Rollback & Recovery */}
        <div style={{ background: "rgba(13, 209, 155, 0.05)", border: "1px solid rgba(13, 209, 155, 0.2)", padding: "12px 16px", borderRadius: "8px", marginBottom: "1.25rem" }}>
          <h3 style={{ margin: "0 0 4px", fontSize: "0.95rem", color: "var(--accent)", display: "flex", alignItems: "center", gap: "6px" }}>
            <span>🔄</span> Procedimiento de Reversión / Rollback
          </h3>
          <p style={{ margin: "0 0 4px", fontSize: "0.85rem", color: "var(--text)" }}>
            <strong>Soporte de Rollback:</strong> <span style={{ color: "var(--accent)", fontWeight: 700 }}>✓ HABILITADO Y OPERATIVO</span>
          </p>
          <p style={{ margin: 0, fontSize: "0.8rem", color: "var(--muted)" }}>
            {playbook.rollback_guidance_i18n
              ? i18n.language.startsWith("en")
                ? playbook.rollback_guidance_i18n.en
                : playbook.rollback_guidance_i18n.es
              : "Ejecuta una transacción compensatoria para restaurar la conectividad, estado de cuenta y permisos previos."}
          </p>
        </div>

        {/* Modal Footer */}
        <div style={{ display: "flex", justifyContent: "flex-end", paddingTop: "1rem", borderTop: "1px solid var(--line)" }}>
          <button type="button" className="primary" onClick={onClose} style={{ padding: "6px 18px", fontSize: "0.85rem" }}>
            Cerrar Ventana
          </button>
        </div>
      </div>
    </div>
  );
}
