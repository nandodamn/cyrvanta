import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  configureNativeActionBinding,
  getIntegrationConnections,
  PlaybookDefinition,
  verifyNativeActionBinding,
} from "./api";

const INTERNAL_ACTIONS = new Set(["incident.status.transition", "endpoint.isolate"]);
const SMTP_ACTIONS = new Set(["notification.send", "incident.report.generate"]);
const HTTP_ACTIONS = new Set(["ticket.create", "webhook.invoke_allowlisted"]);

const ACTION_METADATA: Record<string, { title: string; desc: string; icon: string }> = {
  "incident.status.transition": {
    title: "Transición de Estado del Incidente",
    desc: "Actualiza de forma auditada e inmutable el ciclo de vida del incidente.",
    icon: "🔄",
  },
  "endpoint.isolate": {
    title: "Aislamiento de Host / Endpoint",
    desc: "Aísla el nodo infectado de la red corporativa mediante el agente EDR/Wazuh.",
    icon: "🔒",
  },
  "notification.send": {
    title: "Envío de Alerta y Notificación",
    desc: "Notifica por correo seguro al guardia del SOC y responsables de seguridad.",
    icon: "📧",
  },
  "ticket.create": {
    title: "Creación de Ticket en Mesa de Ayuda / ITSM",
    desc: "Abre automáticamente una solicitud en Jira / ServiceNow / GLPI.",
    icon: "🎫",
  },
  "incident.report.generate": {
    title: "Generación y Entrega de Informe Ejecutivo",
    desc: "Compila el reporte consolidado del incidente y lo remite a la dirección.",
    icon: "📊",
  },
  "webhook.invoke_allowlisted": {
    title: "Invocación de Webhook Seguro",
    desc: "Dispara un endpoint HTTPS autorizado para orquestaciones externas.",
    icon: "🌐",
  },
};

export function PlaybookConfigurationModal({
  playbook,
  onClose,
}: {
  playbook: PlaybookDefinition;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [action, setAction] = useState(playbook.required_actions[0] ?? "");
  const [value, setValue] = useState("");
  const [connectionId, setConnectionId] = useState("");

  const connectorType = INTERNAL_ACTIONS.has(action)
    ? "INTERNAL"
    : SMTP_ACTIONS.has(action)
      ? "SMTP"
      : HTTP_ACTIONS.has(action)
        ? "HTTP_ALLOWLISTED"
        : null;

  const connections = useQuery({
    queryKey: ["integration-connections"],
    queryFn: getIntegrationConnections,
  });

  const candidates = useMemo(
    () => (connections.data ?? []).filter(
      (item) => item.status === "active" && item.connector_type === connectorType,
    ),
    [connections.data, connectorType],
  );

  const save = useMutation({
    mutationFn: async () => {
      if (!connectorType) throw new Error("PLAYBOOK_ACTION_UNAVAILABLE");
      const binding = await configureNativeActionBinding({
        action_code: action,
        action_version: "1.0.0",
        connector_type: connectorType,
        credential_key_id: connectorType === "INTERNAL" ? undefined : connectionId,
        configuration: connectorType === "INTERNAL"
          ? { target_status: "contained" }
          : connectorType === "SMTP"
            ? { to: value }
            : { path: value, method: "POST" },
      });
      return verifyNativeActionBinding(binding.id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["playbook-definitions"] });
      onClose();
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    save.mutate();
  }

  const actionMeta = ACTION_METADATA[action] ?? {
    title: action,
    desc: "Acción estándar de respuesta",
    icon: "⚡",
  };

  return (
    <div
      role="presentation"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 10000,
        display: "grid",
        placeItems: "center",
        padding: "1rem",
        background: "rgba(0,0,0,.75)",
        backdropFilter: "blur(4px)",
      }}
      onClick={onClose}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="playbook-config-title"
        className="panel"
        style={{
          width: "min(580px, 100%)",
          maxHeight: "90vh",
          overflow: "auto",
          borderRadius: "10px",
          border: "1px solid var(--line)",
          padding: "1.5rem",
        }}
        onClick={(event) => event.stopPropagation()}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "1rem" }}>
          <div>
            <p className="eyebrow" style={{ margin: 0 }}>Parámetros de Ejecución</p>
            <h2 id="playbook-config-title" style={{ margin: "4px 0 0", fontSize: "1.3rem" }}>
              ⚙️ Configuración del Playbook
            </h2>
            <p className="muted" style={{ margin: "4px 0 0", fontSize: "0.85rem" }}>
              {playbook.title_i18n.es || playbook.code}
            </p>
          </div>
          <button
            type="button"
            className="ghost"
            style={{ padding: "4px 8px", fontSize: "1rem" }}
            onClick={onClose}
          >
            ✕
          </button>
        </div>

        <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          {/* Action Selector */}
          <div>
            <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, marginBottom: "6px" }}>
              Paso de Acción a Configurar
            </label>
            <select
              value={action}
              style={{ width: "100%", padding: "8px 12px", borderRadius: "6px" }}
              onChange={(event) => {
                setAction(event.target.value);
                setConnectionId("");
                setValue("");
              }}
            >
              {playbook.required_actions.map((item) => {
                const meta = ACTION_METADATA[item];
                return (
                  <option key={item} value={item}>
                    {meta ? `${meta.icon} ${meta.title} (${item})` : item}
                  </option>
                );
              })}
            </select>
          </div>

          {/* Action Info Box */}
          <div
            style={{
              padding: "12px 14px",
              borderRadius: "8px",
              background: "var(--panel-raised)",
              border: "1px solid var(--line)",
              display: "flex",
              alignItems: "flex-start",
              gap: "10px",
            }}
          >
            <span style={{ fontSize: "1.4rem", lineHeight: 1 }}>{actionMeta.icon}</span>
            <div>
              <strong style={{ display: "block", fontSize: "0.9rem", color: "var(--text)" }}>
                {actionMeta.title}
              </strong>
              <p style={{ margin: "2px 0 0", fontSize: "0.8rem", color: "var(--text-soft)" }}>
                {actionMeta.desc}
              </p>
            </div>
          </div>

          {/* Internal Connector Info */}
          {connectorType === "INTERNAL" && (
            <div
              style={{
                background: "rgba(13, 209, 155, 0.08)",
                border: "1px solid rgba(13, 209, 155, 0.25)",
                borderRadius: "8px",
                padding: "12px 14px",
                fontSize: "0.85rem",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "var(--accent)", fontWeight: 600 }}>
                <span>✓</span>
                <span>Acción Nativa Interna de Cyrvanta</span>
              </div>
              <p style={{ margin: "6px 0 0", color: "var(--text-soft)", fontSize: "0.8rem" }}>
                Esta acción se ejecuta de forma segura y directa por el motor nativo del SOC. No requiere credenciales externas de terceros.
              </p>
            </div>
          )}

          {/* External Connector Form */}
          {connectorType && connectorType !== "INTERNAL" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              <label style={{ fontSize: "0.85rem", fontWeight: 600 }}>
                Conexión de Seguridad Asociada
                <select
                  required
                  value={connectionId}
                  style={{ width: "100%", marginTop: "4px", padding: "8px 12px" }}
                  onChange={(event) => setConnectionId(event.target.value)}
                >
                  <option value="">Seleccionar conexión configurada…</option>
                  {candidates.map((item) => (
                    <option value={item.id} key={item.id}>
                      {item.name} ({item.connector_type})
                    </option>
                  ))}
                </select>
              </label>

              <label style={{ fontSize: "0.85rem", fontWeight: 600 }}>
                {connectorType === "SMTP" ? "Destinatario de Correo" : "Ruta / Endpoint URL"}
                <input
                  required
                  type={connectorType === "SMTP" ? "email" : "text"}
                  placeholder={connectorType === "SMTP" ? "soc-guardia@empresa.com" : "/api/v1/tickets"}
                  style={{ width: "100%", marginTop: "4px", padding: "8px 12px" }}
                  value={value}
                  onChange={(event) => setValue(event.target.value)}
                />
              </label>

              {candidates.length === 0 && (
                <p style={{ margin: 0, fontSize: "0.8rem", color: "var(--warning)" }}>
                  ⚠️ No hay ninguna conexión {connectorType} activa registrada en el menú de Integraciones.
                </p>
              )}
            </div>
          )}

          {/* Form Actions */}
          <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end", marginTop: "0.5rem" }}>
            <button type="button" className="ghost" onClick={onClose} style={{ padding: "8px 16px" }}>
              Cancelar
            </button>
            <button
              type="submit"
              className="primary"
              style={{ padding: "8px 18px", fontWeight: 600 }}
              disabled={
                !connectorType
                || (connectorType !== "INTERNAL" && (!connectionId || !value))
                || save.isPending
              }
            >
              {save.isPending ? "Guardando..." : "Guardar Configuración"}
            </button>
          </div>

          {save.isError && (
            <p className="error" role="alert" style={{ margin: 0, fontSize: "0.85rem" }}>
              No se pudo guardar la configuración de la acción. Verifique la conexión asociada.
            </p>
          )}
        </form>
      </section>
    </div>
  );
}
