import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import {
  configureNativeActionBinding,
  getIntegrationConnections,
  getPlaybookActions,
  PlaybookDefinition,
  verifyNativeActionBinding,
} from "./api";

// Wazuh-backed actions report HTTPS egress like any other outbound call, but
// their binding is created from the verified Wazuh connection rather than here.
const WAZUH_ACTIONS = new Set(["host.isolate", "host.restore"]);

const BLOCKING_REASON_TEXT: Record<string, string> = {
  ACTION_BINDING_MISSING: "sin configurar",
  ACTION_UNAVAILABLE: "no disponible en el motor",
  ACTION_CONFIGURATION_TAMPERED: "configuración alterada",
  ACTION_CREDENTIAL_MISSING: "sin conexión asociada",
  ACTION_CREDENTIAL_UNVERIFIED: "conexión sin verificar",
  ACTION_CREDENTIAL_DISABLED: "conexión deshabilitada",
  ACTION_CREDENTIAL_FAILING: "conexión con errores",
  ACTION_CREDENTIAL_OUTDATED: "conexión desactualizada",
};

function reasonText(reason: string | undefined): string {
  return reason ? (BLOCKING_REASON_TEXT[reason] ?? "requiere atención") : "requiere atención";
}

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
  "host.isolate": {
    title: "Aislamiento de Host vía Wazuh",
    desc: "Aísla el endpoint de la red mediante Active Response de Wazuh.",
    icon: "🔒",
  },
  "host.restore": {
    title: "Restauración de Conectividad del Host",
    desc: "Revierte el aislamiento de red aplicado previamente.",
    icon: "🔓",
  },
  "account.disable": {
    title: "Bloqueo de Cuenta",
    desc: "Deshabilita la cuenta comprometida en el directorio de Cyrvanta.",
    icon: "🚫",
  },
  "account.enable": {
    title: "Rehabilitación de Cuenta",
    desc: "Revierte el bloqueo aplicado previamente sobre la cuenta.",
    icon: "✅",
  },
  // Cada sistema externo tiene su propio destino: la acción entrega el
  // incidente aprobado y el sistema configurado es el que ejecuta el efecto.
  "mail_security.invoke_allowlisted": {
    title: "Sistema de Seguridad de Correo",
    desc: "Entrega el incidente al sistema que purga los mensajes y bloquea URLs y dominios.",
    icon: "📨",
  },
  "firewall.invoke_allowlisted": {
    title: "Firewall / Proxy Perimetral",
    desc: "Entrega los indicadores al firewall o proxy que aplica las reglas de bloqueo.",
    icon: "🧱",
  },
  "edr.invoke_allowlisted": {
    title: "Plataforma EDR / Antivirus",
    desc: "Entrega el incidente al EDR que fuerza la reactivación del agente de seguridad.",
    icon: "🛡️",
  },
  "evidence_vault.invoke_allowlisted": {
    title: "Almacén de Evidencia Inmutable",
    desc: "Entrega el snapshot aprobado al almacén que realiza el sellado de la evidencia.",
    icon: "🗄️",
  },
  "threat_intel.lookup": {
    title: "Fuente de Threat Intelligence",
    desc: "Consulta la reputación del incidente y registra el veredicto devuelto como contexto.",
    icon: "🔎",
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

  // Derived from the registry instead of a local list: the modal used to keep
  // its own copy of which actions are internal, SMTP or HTTP, so every action
  // added to the backend silently rendered no fields and a disabled form.
  const actions = useQuery({ queryKey: ["playbook-actions"], queryFn: getPlaybookActions });
  const descriptor = useMemo(
    () => (actions.data ?? []).find((item) => item.code === action),
    [actions.data, action],
  );
  const isWazuhManaged = WAZUH_ACTIONS.has(action);
  const connectorType =
    !descriptor || isWazuhManaged
      ? null
      : descriptor.egress === "NONE"
        ? "INTERNAL"
        : descriptor.egress === "SMTP"
          ? "SMTP"
          : "HTTP_ALLOWLISTED";

  const connections = useQuery({
    queryKey: ["integration-connections"],
    queryFn: getIntegrationConnections,
  });

  const candidates = useMemo(
    () =>
      (connections.data ?? []).filter(
        (item) => item.status === "active" && item.connector_type === connectorType,
      ),
    [connections.data, connectorType],
  );

  // The backend already reports which step blocks the playbook and why, so the
  // modal can say whether the selected step is the one that needs attention
  // instead of describing every step as if it were pending.
  //
  // Any ACTION_*:<code> reason counts as blocking rather than a list of the
  // ones known today: a reason this file had not heard of would otherwise mark
  // a blocked step as ready, which is the failure being fixed here.
  const blockedActions = useMemo(() => {
    const blocked = new Map<string, string>();
    for (const reason of playbook.blocking_reasons) {
      const separator = reason.indexOf(":");
      if (separator < 0 || !reason.startsWith("ACTION_")) continue;
      const target = reason.slice(separator + 1);
      if (target) blocked.set(target, reason.slice(0, separator));
    }
    return blocked;
  }, [playbook.blocking_reasons]);
  const actionIsBlocked = blockedActions.has(action);

  // Internal actions need no connection; external ones cannot be wired until at
  // least one usable connection exists.
  const canSave = connectorType === "INTERNAL" || (!!connectorType && candidates.length > 0);

  const save = useMutation({
    mutationFn: async () => {
      if (!connectorType) throw new Error("PLAYBOOK_ACTION_UNAVAILABLE");
      const binding = await configureNativeActionBinding({
        action_code: action,
        action_version: "1.0.0",
        connector_type: connectorType,
        credential_key_id: connectorType === "INTERNAL" ? undefined : connectionId,
        configuration:
          connectorType === "INTERNAL"
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
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            marginBottom: "1rem",
          }}
        >
          <div>
            <p className="eyebrow" style={{ margin: 0 }}>
              Parámetros de Ejecución
            </p>
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
          {/* Which step is holding the playbook back, before the selector: a
              multi-step playbook otherwise has to be opened step by step to
              find the one that is not ready. */}
          {blockedActions.size > 0 && (
            <p
              style={{
                margin: 0,
                padding: "10px 12px",
                borderRadius: "8px",
                background: "var(--panel-raised)",
                border: "1px solid var(--line)",
                fontSize: "0.8rem",
                color: "var(--text-soft)",
              }}
            >
              {blockedActions.size === 1 ? "Falta un paso" : `Faltan ${blockedActions.size} pasos`}:{" "}
              <strong style={{ color: "var(--text)" }}>
                {[...blockedActions.entries()]
                  .map(
                    ([code, reason]) =>
                      `${ACTION_METADATA[code]?.title ?? code} (${reasonText(reason)})`,
                  )
                  .join(" · ")}
              </strong>
              . Los demás ya están operativos.
            </p>
          )}

          {/* Action Selector */}
          <div>
            <label
              style={{
                display: "block",
                fontSize: "0.85rem",
                fontWeight: 600,
                marginBottom: "6px",
              }}
            >
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
                // Marked per step so the one holding the playbook back is
                // visible without opening each in turn. No icon: the box below
                // repeats the same one, and the selected option sits above it.
                const mark = blockedActions.has(item) ? "⚠" : "✓";
                return (
                  <option key={item} value={item}>
                    {`${mark} ${meta ? `${meta.title} (${item})` : item}`}
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
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  fontWeight: 600,
                  color: actionIsBlocked ? "var(--warning)" : "var(--accent)",
                }}
              >
                <span>{actionIsBlocked ? "⚠️" : "✓"}</span>
                <span>Acción Nativa Interna de Cyrvanta</span>
              </div>
              <p style={{ margin: "6px 0 0", color: "var(--text-soft)", fontSize: "0.8rem" }}>
                {actionIsBlocked
                  ? "Esta acción la ejecuta el motor nativo y no requiere credenciales externas, pero todavía no está habilitada para este tenant."
                  : "Esta acción ya está operativa: la ejecuta de forma directa el motor nativo del SOC y no requiere credenciales externas de terceros."}
              </p>
            </div>
          )}

          {/* Wazuh-managed actions: bound from the verified Wazuh connection */}
          {isWazuhManaged && (
            <div
              style={{
                background: "rgba(13, 209, 155, 0.08)",
                border: "1px solid rgba(13, 209, 155, 0.25)",
                borderRadius: "8px",
                padding: "12px 14px",
                fontSize: "0.85rem",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  fontWeight: 600,
                  color: actionIsBlocked ? "var(--warning)" : "var(--accent)",
                }}
              >
                <span>{actionIsBlocked ? "⚠️" : "✓"}</span>
                <span>
                  {actionIsBlocked ? "Falta la conexión Wazuh" : "Listo mediante la conexión Wazuh"}
                </span>
              </div>
              <p style={{ margin: "6px 0 0", color: "var(--text-soft)", fontSize: "0.8rem" }}>
                {actionIsBlocked
                  ? "Este paso no se configura aquí: se habilita solo cuando la conexión Wazuh está activa y verificada en el menú de Integraciones."
                  : "Este paso no se configura aquí y ya está operativo: la conexión Wazuh está activa y verificada."}
              </p>
            </div>
          )}

          {/* Unknown action: never present an empty form as if it were configurable */}
          {!isWazuhManaged && !connectorType && !actions.isLoading && (
            <p style={{ margin: 0, fontSize: "0.8rem", color: "var(--warning)" }}>
              ⚠️ Esta acción no está registrada en el motor nativo, por lo que no puede configurarse
              ni ejecutarse.
            </p>
          )}

          {/* External Connector Form */}
          {connectorType && connectorType !== "INTERNAL" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              {/* What this step needs, and how to get it, in one block: the
                  selector is useless on its own until a connection exists. */}
              {candidates.length === 0 ? (
                <div
                  style={{
                    borderRadius: "8px",
                    border: "1px solid var(--line)",
                    background: "var(--panel-raised)",
                    padding: "12px 14px",
                  }}
                >
                  <p style={{ margin: 0, fontSize: "0.85rem", fontWeight: 600 }}>
                    Conexión de Seguridad Asociada
                  </p>
                  <p style={{ margin: "6px 0 0", fontSize: "0.8rem", color: "var(--warning)" }}>
                    ⚠️ Este paso necesita una conexión {connectorType} activa y verificada, y
                    todavía no hay ninguna.
                  </p>
                  <p
                    style={{ margin: "6px 0 10px", fontSize: "0.78rem", color: "var(--text-soft)" }}
                  >
                    La URL base y la credencial se cargan una sola vez en Integraciones; aquí sólo
                    se elige cuál de esas conexiones usa este paso.
                  </p>
                  <Link
                    to={`/integrations?nuevo=${connectorType}&nombre=${encodeURIComponent(actionMeta.title)}`}
                    className="ghost"
                    style={{
                      display: "inline-block",
                      padding: "6px 12px",
                      fontSize: "0.8rem",
                      textDecoration: "none",
                    }}
                    onClick={onClose}
                  >
                    Crear conexión en Integraciones →
                  </Link>
                </div>
              ) : (
                <>
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
                    {connectorType === "SMTP"
                      ? "Destinatario de Correo"
                      : "Ruta relativa del endpoint"}
                    <input
                      required
                      type={connectorType === "SMTP" ? "email" : "text"}
                      placeholder={
                        connectorType === "SMTP" ? "soc-guardia@empresa.com" : "/api/v1/tickets"
                      }
                      style={{ width: "100%", marginTop: "4px", padding: "8px 12px" }}
                      value={value}
                      onChange={(event) => setValue(event.target.value)}
                    />
                    {connectorType !== "SMTP" && (
                      <span
                        style={{
                          display: "block",
                          marginTop: "4px",
                          fontWeight: 400,
                          fontSize: "0.75rem",
                          color: "var(--text-soft)",
                        }}
                      >
                        Ruta POST relativa a la URL base de la conexión elegida (debe empezar con
                        “/”).
                      </span>
                    )}
                  </label>
                </>
              )}
            </div>
          )}

          {/* Form Actions */}
          <div
            style={{
              display: "flex",
              gap: "10px",
              justifyContent: "flex-end",
              marginTop: "0.5rem",
            }}
          >
            <button
              type="button"
              className="ghost"
              onClick={onClose}
              style={{ padding: "8px 16px" }}
            >
              {canSave ? "Cancelar" : "Cerrar"}
            </button>
            {/* Hidden, not just disabled: with nothing to fill in there is
                nothing to save, and the next step is the link above. */}
            {canSave && (
              <button
                type="submit"
                className="primary"
                style={{ padding: "8px 18px", fontWeight: 600 }}
                disabled={
                  (connectorType !== "INTERNAL" && (!connectionId || !value)) || save.isPending
                }
              >
                {save.isPending ? "Guardando..." : "Guardar Configuración"}
              </button>
            )}
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
