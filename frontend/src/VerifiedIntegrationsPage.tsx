import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import {
  configureIntegrationConnection,
  getIntegrationConnections,
  IntegrationConnection,
  probeIntegrationConnection,
} from "./api";

type ConnectorType = IntegrationConnection["connector_type"];

const CONNECTORS: ConnectorType[] = [
  "SMTP",
  "HTTP_ALLOWLISTED",
  "N8N",
  "OPENSEARCH",
  "OLLAMA",
  "WAZUH",
];

export function VerifiedIntegrationsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [connectorType, setConnectorType] = useState<ConnectorType>("SMTP");
  const [name, setName] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});

  const connections = useQuery({
    queryKey: ["integration-connections"],
    queryFn: getIntegrationConnections,
  });
  const configure = useMutation({
    mutationFn: (payload: {
      connector_type: ConnectorType;
      name: string;
      configuration: Record<string, string | number | boolean>;
      enabled: boolean;
    }) => configureIntegrationConnection("new", payload),
    onSuccess: () => {
      setName("");
      setFields({});
      queryClient.invalidateQueries({ queryKey: ["integration-connections"] });
      queryClient.invalidateQueries({ queryKey: ["playbook-definitions"] });
    },
  });
  const probe = useMutation({
    mutationFn: probeIntegrationConnection,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["integration-connections"] });
      queryClient.invalidateQueries({ queryKey: ["playbook-definitions"] });
    },
  });

  const visibleFields = useMemo(
    () =>
      connectorType === "SMTP"
        ? ["host", "port", "from_address", "username", "password"]
        : connectorType === "HTTP_ALLOWLISTED"
          ? ["base_url", "bearer_token"]
          : connectorType === "N8N"
            ? ["base_url", "api_key"]
            : connectorType === "WAZUH"
              ? ["base_url", "username", "password"]
              : ["base_url"],
    [connectorType],
  );

  function submit(event: FormEvent) {
    event.preventDefault();
    const configuration: Record<string, string | number | boolean> = {};
    for (const key of visibleFields) {
      const value = fields[key]?.trim();
      if (!value) continue;
      configuration[key] = key === "port" ? Number(value) : value;
    }
    if (connectorType === "SMTP") configuration.use_starttls = true;
    configure.mutate({
      connector_type: connectorType,
      name: name.trim(),
      configuration,
      enabled: true,
    });
  }

  const items = connections.data ?? [];

  return (
    <>
      <div className="page-title">
        <div>
          <p className="eyebrow">{t("securityDataSources")}</p>
          <h1>{t("integrations")}</h1>
          <p className="muted">
            Las credenciales son write-only: después de guardar solo pueden reemplazarse.
          </p>
        </div>
      </div>

      <section className="panel" style={{ marginBottom: "1rem" }}>
        <h2>Configurar conexión real</h2>
        <form onSubmit={submit} className="form-grid">
          <label>
            Tipo
            <select
              value={connectorType}
              onChange={(event) => {
                setConnectorType(event.target.value as ConnectorType);
                setFields({});
              }}
            >
              {CONNECTORS.map((item) => <option key={item}>{item}</option>)}
            </select>
          </label>
          <label>
            Nombre
            <input
              required
              maxLength={200}
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          {visibleFields.map((field) => {
            const secret = ["password", "api_key", "bearer_token"].includes(field);
            return (
              <label key={field}>
                {field}
                <input
                  required={["host", "port", "from_address", "base_url"].includes(field)
                    || (connectorType === "N8N" && field === "api_key")
                    || (connectorType === "WAZUH" && ["username", "password"].includes(field))}
                  type={secret ? "password" : field === "port" ? "number" : "text"}
                  autoComplete={secret ? "new-password" : "off"}
                  value={fields[field] ?? ""}
                  onChange={(event) =>
                    setFields((current) => ({ ...current, [field]: event.target.value }))}
                />
              </label>
            );
          })}
          <div>
            <button type="submit" disabled={configure.isPending || !name.trim()}>
              Guardar sin mostrar secretos
            </button>
          </div>
        </form>
        {configure.isError && <p className="error" role="alert">No se pudo guardar la conexión.</p>}
      </section>

      {connections.isLoading && <p className="muted" role="status">{t("loading")}</p>}
      {connections.isError && <p className="error" role="alert">{t("loadError")}</p>}
      {!connections.isLoading && !connections.isError && items.length === 0 && (
        <p className="muted">No hay conexiones configuradas.</p>
      )}

      <section
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 280px), 1fr))",
          gap: "1rem",
        }}
      >
        {items.map((item) => (
          <article className="panel" key={item.id}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem" }}>
              <strong>{item.name}</strong>
              <span className={item.status === "active" ? "status success" : "status warning"}>
                {item.status}
              </span>
            </div>
            <dl>
              <dt className="muted">Tipo</dt>
              <dd>{item.connector_type}</dd>
              <dt className="muted">Credenciales</dt>
              <dd>{item.configured ? "Guardadas (write-only)" : "Pendientes"}</dd>
              <dt className="muted">Última verificación</dt>
              <dd>{item.last_health_check_at
                ? new Date(item.last_health_check_at).toLocaleString()
                : "Nunca"}</dd>
            </dl>
            <button
              type="button"
              className="ghost"
              disabled={probe.isPending}
              onClick={() => probe.mutate(item.id)}
            >
              Probar conexión real
            </button>
            {item.last_error_code && <p className="error">{item.last_error_code}</p>}
          </article>
        ))}
      </section>
    </>
  );
}
