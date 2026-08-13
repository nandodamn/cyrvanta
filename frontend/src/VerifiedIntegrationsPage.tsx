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

const PRESETS: Record<string, { type: ConnectorType; name: string; fields: Record<string, string> }> = {
  wazuh: {
    type: "WAZUH",
    name: "Wazuh SIEM Manager",
    fields: { base_url: "https://wazuh-manager:55000", username: "wazuh-api" },
  },
  n8n: {
    type: "N8N",
    name: "n8n Automation Engine",
    fields: { base_url: "http://n8n:5678" },
  },
  opensearch: {
    type: "OPENSEARCH",
    name: "OpenSearch Cluster",
    fields: { base_url: "http://opensearch:9200" },
  },
  ollama: {
    type: "OLLAMA",
    name: "Ollama LLM Engine",
    fields: { base_url: "http://host.docker.internal:11434" },
  },
};

export function VerifiedIntegrationsPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [connectorType, setConnectorType] = useState<ConnectorType>("SMTP");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});

  const connections = useQuery({
    queryKey: ["integration-connections"],
    queryFn: getIntegrationConnections,
  });

  const configure = useMutation({
    mutationFn: ({
      connectionId,
      payload,
    }: {
      connectionId: string;
      payload: {
        connector_type: ConnectorType;
        name: string;
        configuration: Record<string, string | number | boolean>;
        enabled: boolean;
      };
    }) => configureIntegrationConnection(connectionId, payload),
    onSuccess: () => {
      setName("");
      setFields({});
      setEditingId(null);
      queryClient.invalidateQueries({ queryKey: ["integration-connections"] });
      queryClient.invalidateQueries({ queryKey: ["playbook-definitions"] });
      queryClient.invalidateQueries({ queryKey: ["operations", "topology"] });
    },
  });

  const probe = useMutation({
    mutationFn: probeIntegrationConnection,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["integration-connections"] });
      queryClient.invalidateQueries({ queryKey: ["playbook-definitions"] });
      queryClient.invalidateQueries({ queryKey: ["operations", "topology"] });
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

  function applyPreset(presetKey: string) {
    const preset = PRESETS[presetKey];
    if (!preset) return;
    setEditingId(null);
    setConnectorType(preset.type);
    setName(preset.name);
    setFields(preset.fields);
    const formEl = document.getElementById("integration-form-section");
    formEl?.scrollIntoView({ behavior: "smooth" });
  }

  function startEditing(item: IntegrationConnection) {
    setEditingId(item.id);
    setConnectorType(item.connector_type);
    setName(item.name);
    // Prefill non-secret parameters
    const prefilled: Record<string, string> = {};
    if (item.sanitized_parameters) {
      for (const [k, v] of Object.entries(item.sanitized_parameters)) {
        if (v !== "••••••••") {
          prefilled[k] = v;
        }
      }
    }
    setFields(prefilled);
    const formEl = document.getElementById("integration-form-section");
    formEl?.scrollIntoView({ behavior: "smooth" });
  }

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
      connectionId: editingId ?? "new",
      payload: {
        connector_type: connectorType,
        name: name.trim(),
        configuration,
        enabled: true,
      },
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
            {t("integrationConnections.writeOnlyHelp")}
          </p>
        </div>
      </div>

      {/* TOP SECTION: CONFIGURED INTEGRATIONS */}
      <section style={{ marginBottom: "2rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
          <div>
            <h2 style={{ margin: 0, fontSize: "1.25rem" }}>
              🔌 {i18n.language.startsWith("es") ? "Conexiones de Seguridad Configuradas" : "Configured Security Connections"}
              <span className="status" style={{ marginLeft: "8px", fontSize: "0.8rem" }}>{items.length}</span>
            </h2>
          </div>
        </div>

        {connections.isLoading && <p className="muted" role="status">{t("loading")}</p>}
        {connections.isError && <p className="error" role="alert">{t("loadError")}</p>}

        {!connections.isLoading && !connections.isError && items.length === 0 && (
          <div className="integration-empty-box">
            <span style={{ fontSize: "2.5rem", display: "block", marginBottom: "0.5rem" }}>📡</span>
            <strong style={{ fontSize: "1.1rem", display: "block", color: "var(--text)" }}>
              {t("integrationConnections.none")}
            </strong>
            <p className="muted" style={{ maxWidth: "600px", margin: "0.5rem auto 1rem auto", fontSize: "0.85rem" }}>
              {i18n.language.startsWith("es")
                ? "Para que Cyrvanta ingeste alertas SIEM, ejecute playbooks SOAR o sincronice telemetría, configure los conectores disponibles en el formulario inferior o cargue una plantilla rápida."
                : "To ingest SIEM alerts, execute SOAR playbooks, or sync telemetry, configure connectors below or load a quick preset."}
            </p>
            <div className="integration-templates-row">
              <button type="button" className="integration-template-btn" onClick={() => applyPreset("wazuh")}>
                🛡️ {i18n.language.startsWith("es") ? "Plantilla Wazuh SIEM" : "Wazuh SIEM Preset"}
              </button>
              <button type="button" className="integration-template-btn" onClick={() => applyPreset("n8n")}>
                ⚡ {i18n.language.startsWith("es") ? "Plantilla n8n SOAR" : "n8n SOAR Preset"}
              </button>
              <button type="button" className="integration-template-btn" onClick={() => applyPreset("opensearch")}>
                🔍 {i18n.language.startsWith("es") ? "Plantilla OpenSearch" : "OpenSearch Preset"}
              </button>
              <button type="button" className="integration-template-btn" onClick={() => applyPreset("ollama")}>
                🧠 {i18n.language.startsWith("es") ? "Plantilla Ollama LLM" : "Ollama LLM Preset"}
              </button>
            </div>
          </div>
        )}

        {items.length > 0 && (
          <div className="integrations-cards-grid">
            {items.map((item) => (
              <article className="integration-card" key={item.id}>
                <div>
                  <div className="integration-card-header">
                    <div>
                      <strong style={{ fontSize: "1.05rem", color: "var(--text)" }}>{item.name}</strong>
                      <div style={{ marginTop: "2px" }}>
                        <span className="status" style={{ fontSize: "0.72rem", textTransform: "uppercase" }}>
                          {item.connector_type}
                        </span>
                      </div>
                    </div>
                    <span className={item.status === "active" ? "status success" : item.status === "disabled" ? "status" : "status warning"}>
                      {item.status === "active" ? "● ACTIVO" : item.status === "disabled" ? "⊘ INACTIVO" : "⚠️ ERROR"}
                    </span>
                  </div>

                  {/* Capabilities Tags */}
                  {item.capabilities && item.capabilities.length > 0 && (
                    <div className="integration-caps-row">
                      {item.capabilities.map((cap) => (
                        <span key={cap} className="integration-cap-badge">{cap}</span>
                      ))}
                    </div>
                  )}

                  {/* Configured Parameters Viewer */}
                  <div className="integration-params-box">
                    <strong style={{ fontSize: "0.75rem", color: "var(--text-soft)", textTransform: "uppercase", display: "block", marginBottom: "4px" }}>
                      ⚙️ {i18n.language.startsWith("es") ? "Parámetros de Conexión" : "Connection Parameters"}:
                    </strong>
                    {item.sanitized_parameters && Object.keys(item.sanitized_parameters).length > 0 ? (
                      Object.entries(item.sanitized_parameters).map(([k, v]) => (
                        <div key={k} className="integration-param-row">
                          <span className="integration-param-key">{k}:</span>
                          <span className="integration-param-val">{v}</span>
                        </div>
                      ))
                    ) : (
                      <div style={{ color: "var(--muted)", fontSize: "0.78rem" }}>
                        {item.configured ? `🔒 ${t("integrationConnections.stored")}` : `⚠️ ${t("integrationConnections.pending")}`}
                      </div>
                    )}
                  </div>

                  <dl className="integration-meta-list">
                    <dt>{t("integrationConnections.credentials")}:</dt>
                    <dd>{item.configured ? `🔒 ${t("integrationConnections.stored")}` : `⚠️ ${t("integrationConnections.pending")}`}</dd>
                    <dt>{t("integrationConnections.lastVerification")}:</dt>
                    <dd>
                      {item.last_health_check_at
                        ? new Date(item.last_health_check_at).toLocaleString(i18n.language)
                        : t("integrationConnections.never")}
                    </dd>
                  </dl>

                  {item.last_error_code && (
                    <p className="error" style={{ fontSize: "0.8rem", marginBottom: "0.75rem" }}>
                      ⚠️ {item.last_error_code}
                    </p>
                  )}
                </div>

                <div className="integration-actions-row">
                  <button
                    type="button"
                    className="ghost"
                    disabled={probe.isPending || item.status === "disabled"}
                    onClick={() => probe.mutate(item.id)}
                  >
                    ⚡ {t("integrationConnections.testReal")}
                  </button>
                  <button
                    type="button"
                    className="ghost"
                    onClick={() => startEditing(item)}
                  >
                    ✏️ {t("integrationConnections.replaceConfiguration")}
                  </button>
                  <button
                    type="button"
                    className="ghost"
                    disabled={configure.isPending}
                    onClick={() => configure.mutate({
                      connectionId: item.id,
                      payload: {
                        connector_type: item.connector_type,
                        name: item.name,
                        configuration: {},
                        enabled: item.status === "disabled",
                      },
                    })}
                  >
                    {item.status === "disabled"
                      ? `✓ ${t("integrationConnections.enableConnection")}`
                      : `⊘ ${t("integrationConnections.disableConnection")}`}
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      {/* FORM SECTION: CONFIGURE OR MODIFY */}
      <section id="integration-form-section" className="integrations-form-panel">
        {editingId && (
          <div className="integration-editing-banner">
            <div>
              <strong style={{ color: "var(--accent)" }}>
                ✏️ {i18n.language.startsWith("es") ? "Modificando Conexión:" : "Editing Connection:"} {name}
              </strong>
              <p style={{ margin: "2px 0 0", fontSize: "0.8rem", color: "var(--text-soft)" }}>
                {i18n.language.startsWith("es")
                  ? "Puede actualizar parámetros. Si no desea modificar contraseñas o tokens existentes, deje los campos de credencial en blanco."
                  : "You can update parameters. To keep existing passwords or tokens, leave credential fields blank."}
              </p>
            </div>
            <button
              type="button"
              className="ghost"
              onClick={() => {
                setEditingId(null);
                setName("");
                setFields({});
              }}
            >
              ✕ {t("integrationConnections.cancelReplace")}
            </button>
          </div>
        )}

        <h2 style={{ margin: "0 0 0.5rem", fontSize: "1.2rem" }}>
          {editingId ? `✏️ ${t("integrationConnections.replaceConfiguration")}` : `➕ ${t("integrationConnections.configureReal")}`}
        </h2>

        <form onSubmit={submit} className="integrations-form-grid">
          <label>
            <span>{t("integrationConnections.type")}</span>
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
            <span>{t("integrationConnections.name")}</span>
            <input
              required
              maxLength={200}
              placeholder="e.g. Wazuh SIEM Production"
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          {visibleFields.map((field) => {
            const secret = ["password", "api_key", "bearer_token"].includes(field);
            return (
              <label key={field}>
                <span>{field.replace(/_/g, " ").toUpperCase()}</span>
                <input
                  required={
                    !editingId &&
                    (["host", "port", "from_address", "base_url"].includes(field) ||
                      (connectorType === "N8N" && field === "api_key") ||
                      (connectorType === "WAZUH" && ["username", "password"].includes(field)))
                  }
                  type={secret ? "password" : field === "port" ? "number" : "text"}
                  autoComplete={secret ? "new-password" : "off"}
                  placeholder={
                    secret && editingId
                      ? (i18n.language.startsWith("es") ? "•••••••• (Sin cambios)" : "•••••••• (Unchanged)")
                      : field === "base_url"
                        ? "https://..."
                        : field
                  }
                  value={fields[field] ?? ""}
                  onChange={(event) =>
                    setFields((current) => ({ ...current, [field]: event.target.value }))}
                />
              </label>
            );
          })}
          <div className="integrations-form-actions">
            {editingId && (
              <button
                type="button"
                className="ghost"
                onClick={() => {
                  setEditingId(null);
                  setName("");
                  setFields({});
                }}
              >
                {t("integrationConnections.cancelReplace")}
              </button>
            )}
            <button type="submit" disabled={configure.isPending || !name.trim()}>
              {editingId ? `✓ ${t("integrationConnections.replaceSave")}` : `✓ ${t("integrationConnections.saveWriteOnly")}`}
            </button>
          </div>
        </form>
        {configure.isError && <p className="error" role="alert" style={{ marginTop: "0.75rem" }}>{t("integrationConnections.saveError")}</p>}
      </section>
    </>
  );
}
