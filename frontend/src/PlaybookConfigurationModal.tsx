import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  configureNativeActionBinding,
  getIntegrationConnections,
  PlaybookDefinition,
  verifyNativeActionBinding,
} from "./api";

const SMTP_ACTIONS = new Set(["notification.send", "incident.report.generate"]);
const HTTP_ACTIONS = new Set(["ticket.create", "webhook.invoke_allowlisted"]);

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
  const connectorType = action === "incident.status.transition"
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
      }}
      onClick={onClose}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="playbook-config-title"
        className="panel"
        style={{ width: "min(620px, 100%)", maxHeight: "90vh", overflow: "auto" }}
        onClick={(event) => event.stopPropagation()}
      >
        <h2 id="playbook-config-title">Configurar playbook NATIVE</h2>
        <p className="muted">
          El playbook seguirá deshabilitado hasta que cada acción tenga una conexión real
          verificada, la versión esté publicada y el binding quede sincronizado.
        </p>
        <form onSubmit={submit} className="form-grid">
          <label>
            Acción requerida
            <select value={action} onChange={(event) => {
              setAction(event.target.value);
              setConnectionId("");
              setValue("");
            }}>
              {playbook.required_actions.map((item) => <option key={item}>{item}</option>)}
            </select>
          </label>
          {!connectorType && (
            <p className="error" role="alert">
              Esta acción permanece visible pero deshabilitada: todavía no existe un adaptador
              real aprobado.
            </p>
          )}
          {connectorType && connectorType !== "INTERNAL" && (
            <>
              <label>
                Conexión real verificada
                <select
                  required
                  value={connectionId}
                  onChange={(event) => setConnectionId(event.target.value)}
                >
                  <option value="">Seleccionar…</option>
                  {candidates.map((item) => (
                    <option value={item.id} key={item.id}>{item.name}</option>
                  ))}
                </select>
              </label>
              <label>
                {connectorType === "SMTP" ? "Destinatario" : "Ruta permitida"}
                <input
                  required
                  type={connectorType === "SMTP" ? "email" : "text"}
                  placeholder={connectorType === "SMTP" ? "soc@empresa.com" : "/api/tickets"}
                  value={value}
                  onChange={(event) => setValue(event.target.value)}
                />
              </label>
              {candidates.length === 0 && (
                <p className="muted">
                  Primero configure y pruebe una conexión {connectorType} en Integraciones.
                </p>
              )}
            </>
          )}
          <div style={{ display: "flex", gap: ".75rem", flexWrap: "wrap" }}>
            <button
              type="submit"
              disabled={
                !connectorType
                || (connectorType !== "INTERNAL" && (!connectionId || !value))
                || save.isPending
              }
            >
              Guardar y verificar binding
            </button>
            <button type="button" className="ghost" onClick={onClose}>Cancelar</button>
          </div>
          {save.isError && <p className="error" role="alert">No se pudo verificar el binding.</p>}
        </form>
      </section>
    </div>
  );
}
