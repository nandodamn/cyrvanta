import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

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

const PRESETS: Record<
  string,
  { type: ConnectorType; name: string; fields: Record<string, string> }
> = {
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
  // Left unnamed on purpose: a tenant configures one of these per external
  // system (mail security, firewall, EDR, evidence vault, threat intel), and
  // each playbook step picks the one it uses, so a shared default name would
  // push every step at the same destination.
  http_allowlisted: {
    type: "HTTP_ALLOWLISTED",
    name: "",
    fields: { base_url: "https://" },
  },
};

export function VerifiedIntegrationsPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [connectorType, setConnectorType] = useState<ConnectorType>("SMTP");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});
  // Encrypted unless the operator turns it off deliberately.
  const [startTls, setStartTls] = useState(true);
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedType = searchParams.get("nuevo") as ConnectorType | null;
  const suggestedName = searchParams.get("nombre");
  const prefillApplied = useRef(false);

  // Arriving from a playbook step that has no connection to use: open the form
  // on the connector that step needs, with a name naming the system, so the
  // jump between menus carries its context instead of restarting the task.
  useEffect(() => {
    if (prefillApplied.current || !requestedType) return;
    if (!CONNECTORS.includes(requestedType)) return;
    prefillApplied.current = true;
    setEditingId(null);
    setConnectorType(requestedType);
    setName(suggestedName ?? "");
    setFields({});
    setStartTls(true);
    setSearchParams({}, { replace: true });
    window.setTimeout(() => {
      // Scrolling is a nicety, and not every environment implements it.
      document.getElementById("integration-form-section")?.scrollIntoView?.({ behavior: "smooth" });
    }, 0);
  }, [requestedType, suggestedName, setSearchParams]);

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
      setStartTls(true);
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
    // Reflect what is stored: defaulting to on would silently re-enable
    // STARTTLS on a plaintext relay the next time it is saved.
    setStartTls(
      String(item.sanitized_parameters?.use_starttls ?? "true").toLowerCase() !== "false",
    );
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
    if (connectorType === "SMTP") configuration.use_starttls = startTls;
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
          <p className="muted">{t("integrationConnections.writeOnlyHelp")}</p>
        </div>
      </div>

      {/* TOP SECTION: CONFIGURED INTEGRATIONS */}
      <section style={{ marginBottom: "2rem" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "1rem",
          }}
        >
          <div>
            <h2 style={{ margin: 0, fontSize: "1.25rem" }}>
              🔌{" "}
              {i18n.language.startsWith("es")
                ? "Conexiones de Seguridad Configuradas"
                : "Configured Security Connections"}
              <span className="status" style={{ marginLeft: "8px", fontSize: "0.8rem" }}>
                {items.length}
              </span>
            </h2>
          </div>
        </div>

        {connections.isLoading && (
          <p className="muted" role="status">
            {t("loading")}
          </p>
        )}
        {connections.isError && (
          <p className="error" role="alert">
            {t("loadError")}
          </p>
        )}

        {!connections.isLoading && !connections.isError && items.length === 0 && (
          <div className="integration-empty-box">
            <span style={{ fontSize: "2.5rem", display: "block", marginBottom: "0.5rem" }}>📡</span>
            <strong style={{ fontSize: "1.1rem", display: "block", color: "var(--text)" }}>
              {t("integrationConnections.none")}
            </strong>
            <p
              className="muted"
              style={{ maxWidth: "600px", margin: "0.5rem auto 1rem auto", fontSize: "0.85rem" }}
            >
              {i18n.language.startsWith("es")
                ? "Para que Cyrvanta ingeste alertas SIEM, ejecute playbooks SOAR o sincronice telemetría, configure los conectores disponibles en el formulario inferior o cargue una plantilla rápida."
                : "To ingest SIEM alerts, execute SOAR playbooks, or sync telemetry, configure connectors below or load a quick preset."}
            </p>
            <div className="integration-templates-row">
              <button
                type="button"
                className="integration-template-btn"
                onClick={() => applyPreset("wazuh")}
              >
                🛡️ {i18n.language.startsWith("es") ? "Plantilla Wazuh SIEM" : "Wazuh SIEM Preset"}
              </button>
              <button
                type="button"
                className="integration-template-btn"
                onClick={() => applyPreset("n8n")}
              >
                ⚡ {i18n.language.startsWith("es") ? "Plantilla n8n SOAR" : "n8n SOAR Preset"}
              </button>
              <button
                type="button"
                className="integration-template-btn"
                onClick={() => applyPreset("opensearch")}
              >
                🔍 {i18n.language.startsWith("es") ? "Plantilla OpenSearch" : "OpenSearch Preset"}
              </button>
              <button
                type="button"
                className="integration-template-btn"
                onClick={() => applyPreset("ollama")}
              >
                🧠 {i18n.language.startsWith("es") ? "Plantilla Ollama LLM" : "Ollama LLM Preset"}
              </button>
              <button
                type="button"
                className="integration-template-btn"
                onClick={() => applyPreset("http_allowlisted")}
              >
                🌐{" "}
                {i18n.language.startsWith("es")
                  ? "Plantilla Sistema Externo (HTTPS)"
                  : "External System Preset (HTTPS)"}
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
                      <strong style={{ fontSize: "1.05rem", color: "var(--text)" }}>
                        {item.name}
                      </strong>
                      <div style={{ marginTop: "2px" }}>
                        <span
                          className="status"
                          style={{ fontSize: "0.72rem", textTransform: "uppercase" }}
                        >
                          {item.connector_type}
                        </span>
                      </div>
                    </div>
                    <span
                      className={
                        item.status === "active"
                          ? "status success"
                          : item.status === "disabled"
                            ? "status"
                            : "status warning"
                      }
                    >
                      {item.status === "active"
                        ? "● ACTIVO"
                        : item.status === "disabled"
                          ? "⊘ INACTIVO"
                          : "⚠️ ERROR"}
                    </span>
                  </div>

                  {/* Capabilities Tags */}
                  {item.capabilities && item.capabilities.length > 0 && (
                    <div className="integration-caps-row">
                      {item.capabilities.map((cap) => (
                        <span key={cap} className="integration-cap-badge">
                          {cap}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Configured Parameters Viewer */}
                  <div className="integration-params-box">
                    <strong
                      style={{
                        fontSize: "0.75rem",
                        color: "var(--text-soft)",
                        textTransform: "uppercase",
                        display: "block",
                        marginBottom: "4px",
                      }}
                    >
                      ⚙️{" "}
                      {i18n.language.startsWith("es")
                        ? "Parámetros de Conexión"
                        : "Connection Parameters"}
                      :
                    </strong>
                    {item.sanitized_parameters &&
                    Object.keys(item.sanitized_parameters).length > 0 ? (
                      Object.entries(item.sanitized_parameters).map(([k, v]) => (
                        <div key={k} className="integration-param-row">
                          <span className="integration-param-key">{k}:</span>
                          <span className="integration-param-val">{v}</span>
                        </div>
                      ))
                    ) : (
                      <div style={{ color: "var(--muted)", fontSize: "0.78rem" }}>
                        {item.configured
                          ? `🔒 ${t("integrationConnections.stored")}`
                          : `⚠️ ${t("integrationConnections.pending")}`}
                      </div>
                    )}
                  </div>

                  <dl className="integration-meta-list">
                    <dt>{t("integrationConnections.credentials")}:</dt>
                    <dd>
                      {item.configured
                        ? `🔒 ${t("integrationConnections.stored")}`
                        : `⚠️ ${t("integrationConnections.pending")}`}
                    </dd>
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
                  <button type="button" className="ghost" onClick={() => startEditing(item)}>
                    ✏️ {t("integrationConnections.replaceConfiguration")}
                  </button>
                  <button
                    type="button"
                    className="ghost"
                    disabled={configure.isPending}
                    onClick={() =>
                      configure.mutate({
                        connectionId: item.id,
                        payload: {
                          connector_type: item.connector_type,
                          name: item.name,
                          configuration: {},
                          enabled: item.status === "disabled",
                        },
                      })
                    }
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
                ✏️{" "}
                {i18n.language.startsWith("es") ? "Modificando Conexión:" : "Editing Connection:"}{" "}
                {name}
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
                setStartTls(true);
              }}
            >
              ✕ {t("integrationConnections.cancelReplace")}
            </button>
          </div>
        )}

        <h2 style={{ margin: "0 0 0.5rem", fontSize: "1.2rem" }}>
          {editingId
            ? `✏️ ${t("integrationConnections.replaceConfiguration")}`
            : `➕ ${t("integrationConnections.configureReal")}`}
        </h2>

        <form onSubmit={submit} className="integrations-form-grid">
          <label>
            <span>{t("integrationConnections.type")}</span>
            <select
              value={connectorType}
              onChange={(event) => {
                setConnectorType(event.target.value as ConnectorType);
                setFields({});
                setStartTls(true);
              }}
            >
              {CONNECTORS.map((item) => (
                <option key={item}>{item}</option>
              ))}
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
                      ? i18n.language.startsWith("es")
                        ? "•••••••• (Sin cambios)"
                        : "•••••••• (Unchanged)"
                      : field === "base_url"
                        ? "https://..."
                        : field
                  }
                  value={fields[field] ?? ""}
                  onChange={(event) =>
                    setFields((current) => ({ ...current, [field]: event.target.value }))
                  }
                />
              </label>
            );
          })}
          {/* STARTTLS is a property of the server, not of every SMTP server.
              Forcing it on made any relay without it impossible to configure,
              so it stays on by default and turning it off is deliberate. */}
          {connectorType === "SMTP" && (
            <label>
              {/* Same casing as the generated field labels above. */}
              <span>USE STARTTLS</span>
              <span style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "4px" }}>
                <input
                  type="checkbox"
                  style={{ width: "auto" }}
                  checked={startTls}
                  onChange={(event) => setStartTls(event.target.checked)}
                />
                <span style={{ fontSize: "0.85rem" }}>
                  {i18n.language.startsWith("es")
                    ? "Cifrar la conexión con STARTTLS"
                    : "Encrypt the connection with STARTTLS"}
                </span>
              </span>
              {!startTls && (
                <span
                  style={{
                    display: "block",
                    marginTop: "6px",
                    fontSize: "0.78rem",
                    color: "var(--warning)",
                  }}
                >
                  ⚠️{" "}
                  {i18n.language.startsWith("es")
                    ? "El correo y las credenciales viajarán sin cifrar. Usalo sólo con un servidor de laboratorio o un relay interno de confianza."
                    : "Mail and credentials will travel unencrypted. Use only with a lab server or a trusted internal relay."}
                </span>
              )}
            </label>
          )}
          <div className="integrations-form-actions">
            {editingId && (
              <button
                type="button"
                className="ghost"
                onClick={() => {
                  setEditingId(null);
                  setName("");
                  setFields({});
                  setStartTls(true);
                }}
              >
                {t("integrationConnections.cancelReplace")}
              </button>
            )}
            <button type="submit" disabled={configure.isPending || !name.trim()}>
              {editingId
                ? `✓ ${t("integrationConnections.replaceSave")}`
                : `✓ ${t("integrationConnections.saveWriteOnly")}`}
            </button>
          </div>
        </form>
        {configure.isError && (
          <p className="error" role="alert" style={{ marginTop: "0.75rem" }}>
            {t("integrationConnections.saveError")}
          </p>
        )}
      </section>
    </>
  );
}
