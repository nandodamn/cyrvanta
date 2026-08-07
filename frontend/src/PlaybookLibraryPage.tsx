import React, { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import {
  getPlaybookDefinitions,
  getPlaybookManagement,
  getPlaybooks,
  PlaybookDefinition,
  togglePlaybookBinding,
  updatePlaybookApprovalGovernance,
} from "./api";
import "./playbook-library.css";
import { PlaybookDetailsModal } from "./PlaybookDetailsModal";

const PLAYBOOK_REQUIRED_INTEGRATIONS: Record<string, { connectorName: string; navTab: string }> = {
  "simulate-host-isolation": { connectorName: "Microsoft Defender / EDR", navTab: "Integraciones" },
  "simulate-itsm-ticket-creation": { connectorName: "ServiceNow / Jira ITSM", navTab: "Integraciones" },
  "malicious-indicator": { connectorName: "Palo Alto / Fortinet Firewall", navTab: "Integraciones" },
  "lateral-movement": { connectorName: "Microsoft Defender / Firewall Local", navTab: "Integraciones" },
};

export function PlaybookLibraryPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [selectedDetails, setSelectedDetails] = useState<{
    playbook: PlaybookDefinition;
    req?: { connectorName: string; navTab: string };
  } | null>(null);

  const nativeLibrary = useQuery({
    queryKey: ["playbook-definitions"],
    queryFn: getPlaybookDefinitions,
  });
  const n8nCatalog = useQuery({
    queryKey: ["playbooks", "optional-n8n"],
    queryFn: () => getPlaybooks({ page: 0, pageSize: 100 }),
  });
  const management = useQuery({
    queryKey: ["playbook-management"],
    queryFn: getPlaybookManagement,
    retry: false,
  });

  const toggleMutation = useMutation({
    mutationFn: ({
      id,
      input,
    }: {
      id: string;
      input: { active?: boolean; engine_type?: "NATIVE" | "N8N" };
    }) => togglePlaybookBinding(id, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["playbook-definitions"] });
    },
  });

  const approvalMutation = useMutation({
    mutationFn: ({
      id,
      mode,
    }: {
      id: string;
      mode: "AUTOMATIC" | "SINGLE" | "FOUR_EYES";
    }) => updatePlaybookApprovalGovernance(id, mode),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["playbook-definitions"] });
    },
  });

  return (
    <>
      <div className="page-title">
        <div>
          <p className="eyebrow">{t("approvedAutomation")}</p>
          <h1>{t("playbooks")}</h1>
          <p className="muted">{t("playbooksNativeIntro")}</p>
        </div>
        {management.data && (
          <a
            className="button-link"
            href={management.data.editor_url}
            target="_blank"
            rel="noreferrer"
          >
            {t("openN8n")}
          </a>
        )}
      </div>

      <section className="playbook-status" aria-label={t("synchronizationStatus")}>
        <div>
          <span>{t("automationEngine")}</span>
          <strong>Cyrvanta Native</strong>
          <small>{t("defaultEngine")}</small>
        </div>
        <div>
          <span>{t("nativeLibrary")}</span>
          <strong>{nativeLibrary.data?.total ?? 0}</strong>
          <small>{t("bindingStatus")}</small>
        </div>
        <div>
          <span>n8n</span>
          <strong>{t("optionalN8n")}</strong>
          <small>{t(`integrationModes.${n8nCatalog.data?.mode ?? "disabled"}`)}</small>
        </div>
      </section>

      <section className="panel table-panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Cyrvanta Native</p>
            <h2>{t("nativeLibrary")}</h2>
          </div>
        </div>
        {nativeLibrary.isLoading && <p>{t("loading")}</p>}
        {nativeLibrary.isError && <p role="alert">{t("error")}</p>}
        {nativeLibrary.data?.items.length === 0 && <p>{t("emptyState")}</p>}
        <div className="playbook-list">
          {nativeLibrary.data?.items.map((playbook) => {
            const currentMode = playbook.approval_mode ?? "AUTOMATIC";
            const requiredIntegration = PLAYBOOK_REQUIRED_INTEGRATIONS[playbook.code];
            const isMissingIntegration = Boolean(requiredIntegration);

            return (
              <article key={playbook.id} style={isMissingIntegration ? { opacity: 0.9, border: "1px dashed #f59e0b" } : {}}>
                <div className="playbook-heading">
                  <div>
                    {isMissingIntegration ? (
                      <span
                        style={{
                          background: "rgba(245, 158, 11, 0.22)",
                          color: "#fbbf24",
                          border: "1px solid #f59e0b",
                          padding: "3px 8px",
                          borderRadius: "4px",
                          fontSize: "0.75rem",
                          fontWeight: 700,
                          letterSpacing: "0.02em",
                        }}
                      >
                        🔒 REQUIERE CONFIGURACIÓN
                      </span>
                    ) : (
                      <span className={`demo-badge ${playbook.binding_active ? "active" : ""}`}>
                        {playbook.binding_active ? t("active") : t("inactive")}
                      </span>
                    )}
                    <span
                      className="demo-badge"
                      style={{
                        marginLeft: "6px",
                        background:
                          currentMode === "SINGLE"
                            ? "rgba(59, 130, 246, 0.15)"
                            : currentMode === "FOUR_EYES"
                              ? "rgba(245, 158, 11, 0.15)"
                              : "rgba(13, 209, 155, 0.15)",
                        color:
                          currentMode === "SINGLE"
                            ? "#60a5fa"
                            : currentMode === "FOUR_EYES"
                              ? "#fbbf24"
                              : "var(--accent)",
                        border: `1px solid ${
                          currentMode === "SINGLE"
                            ? "#3b82f6"
                            : currentMode === "FOUR_EYES"
                              ? "#f59e0b"
                              : "var(--accent)"
                        }`,
                      }}
                    >
                      {currentMode === "SINGLE"
                        ? "👤 Aprobación Simple"
                        : currentMode === "FOUR_EYES"
                          ? "👥 Principio 4 Ojos"
                          : "⚡ Automático"}
                    </span>
                    <h2>
                      {i18n.language.startsWith("en")
                        ? playbook.title_i18n.en
                        : playbook.title_i18n.es}
                    </h2>
                    <code>{playbook.code}</code>
                  </div>
                  <div className="playbook-version" style={{ display: "flex", flexDirection: "column", gap: "6px", alignItems: "flex-end" }}>
                    <button
                      type="button"
                      className={playbook.binding_active && !isMissingIntegration ? "ghost" : "primary"}
                      style={{
                        padding: "4px 10px",
                        fontSize: "0.775rem",
                        height: "auto",
                        minHeight: "unset",
                        minWidth: "unset",
                        width: "auto",
                        whiteSpace: "nowrap",
                        opacity: isMissingIntegration ? 0.6 : 1,
                        cursor: isMissingIntegration ? "not-allowed" : "pointer",
                      }}
                      disabled={toggleMutation.isPending || isMissingIntegration}
                      title={isMissingIntegration ? `🔒 Requiere configurar credenciales API para ${requiredIntegration.connectorName} en el menú ${requiredIntegration.navTab}` : undefined}
                      onClick={() =>
                        toggleMutation.mutate({
                          id: playbook.id,
                          input: { active: !playbook.binding_active },
                        })
                      }
                    >
                      {isMissingIntegration ? "🔒 Sin Credenciales API" : playbook.binding_active ? t("deactivatePlaybook") : t("activatePlaybook")}
                    </button>
                    <button
                      type="button"
                      className="ghost"
                      style={{
                        padding: "4px 10px",
                        fontSize: "0.775rem",
                        height: "auto",
                        minHeight: "unset",
                        minWidth: "unset",
                        width: "auto",
                        whiteSpace: "nowrap",
                      }}
                      disabled={toggleMutation.isPending || isMissingIntegration}
                      onClick={() =>
                        toggleMutation.mutate({
                          id: playbook.id,
                          input: {
                            engine_type: playbook.engine_type === "N8N" ? "NATIVE" : "N8N",
                            active: true,
                          },
                        })
                      }
                    >
                      {playbook.engine_type === "N8N" ? t("switchEngineNative") : t("switchEngineN8n")}
                    </button>
                  </div>
                </div>

                {isMissingIntegration && (
                  <div style={{ background: "rgba(245, 158, 11, 0.1)", border: "1px solid rgba(245, 158, 11, 0.4)", color: "#fbbf24", padding: "8px 12px", borderRadius: "6px", fontSize: "0.8rem", margin: "8px 0", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <span>
                      🔒 <strong>Conector de Integración Pendiente:</strong> Requiere configurar la URL y llaves de acceso para <strong>{requiredIntegration.connectorName}</strong> en el menú <strong>{requiredIntegration.navTab}</strong> antes de activarse.
                    </span>
                  </div>
                )}

                <div className="playbook-facts">
                  <div>
                    <span>{t("automationEngine")}</span>
                    <strong>{playbook.engine_type ?? "Cyrvanta Native"}</strong>
                  </div>
                  <div>
                    <span>{t("mode")}</span>
                    <strong>{playbook.execution_mode ?? t("notAvailableVersion")}</strong>
                  </div>
                  <div>
                    <span>{t("impact")}</span>
                    <strong>{playbook.impact ?? t("notAvailableVersion")}</strong>
                  </div>
                  <div>
                    <span>{t("publicationStatus")}</span>
                    <strong>{playbook.publication_status ?? t("notAvailableVersion")}</strong>
                  </div>
                  <div>
                    <span>{t("bindingStatus")}</span>
                    <strong>{playbook.binding_status ?? t("syncPending")}</strong>
                  </div>
                  <div>
                    <span>{t("lastExecution")}</span>
                    <strong>{playbook.last_execution_status ?? t("neverExecuted")}</strong>
                  </div>
                </div>

                {/* Gobernanza Bar */}
                <div className="connector-grid" style={{ marginBottom: "1rem" }}>
                  <div style={{ gridColumn: "span 2", background: "rgba(255,255,255,0.02)", padding: "10px 14px", borderRadius: "6px", border: "1px solid var(--line)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
                      <div>
                        <strong style={{ display: "block", fontSize: "0.85rem", color: "var(--text)" }}>
                          🛡️ Gobernanza de Disparo & Aprobación
                        </strong>
                        <small style={{ color: "var(--muted)", fontSize: "0.75rem" }}>
                          {currentMode === "AUTOMATIC" && "⚡ Disparo automático inmediato sin retención."}
                          {currentMode === "SINGLE" && "👤 Requiere la firma de 1 analista autorizador antes de ejecutar."}
                          {currentMode === "FOUR_EYES" && "👥 Requiere la firma independiente de 2 analistas (Principio de 4 Ojos)."}
                        </small>
                      </div>
                      <div style={{ display: "flex", gap: "6px" }}>
                        <button
                          type="button"
                          className={currentMode === "AUTOMATIC" ? "primary" : "ghost"}
                          style={{ padding: "4px 10px", fontSize: "0.75rem", minWidth: "unset", width: "auto" }}
                          disabled={approvalMutation.isPending}
                          onClick={() => approvalMutation.mutate({ id: playbook.id, mode: "AUTOMATIC" })}
                        >
                          ⚡ Automático
                        </button>
                        <button
                          type="button"
                          className={currentMode === "SINGLE" ? "primary" : "ghost"}
                          style={{ padding: "4px 10px", fontSize: "0.75rem", minWidth: "unset", width: "auto" }}
                          disabled={approvalMutation.isPending}
                          onClick={() => approvalMutation.mutate({ id: playbook.id, mode: "SINGLE" })}
                        >
                          👤 Simple (1 Ojo)
                        </button>
                        <button
                          type="button"
                          className={currentMode === "FOUR_EYES" ? "primary" : "ghost"}
                          style={{ padding: "4px 10px", fontSize: "0.75rem", minWidth: "unset", width: "auto" }}
                          disabled={approvalMutation.isPending}
                          onClick={() => approvalMutation.mutate({ id: playbook.id, mode: "FOUR_EYES" })}
                        >
                          👥 Doble (4 Ojos)
                        </button>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Card Action Footer: Clean button to open PlaybookDetailsModal */}
                <div style={{ borderTop: "1px solid var(--line)", paddingTop: "10px", marginTop: "10px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                    <span style={{ fontSize: "0.75rem", background: "rgba(13, 209, 155, 0.1)", color: "var(--accent)", padding: "2px 8px", borderRadius: "4px", fontWeight: 600 }}>
                      ✓ Rollback Habilitado
                    </span>
                    <span style={{ fontSize: "0.75rem", color: "var(--muted)" }}>
                      MITRE: {playbook.mitre_codes?.length ? playbook.mitre_codes.join(", ") : "T1078"}
                    </span>
                  </div>
                  <button
                    type="button"
                    className="ghost"
                    style={{ fontSize: "0.8rem", padding: "6px 14px", border: "1px solid var(--accent)", color: "var(--accent)", fontWeight: 600 }}
                    onClick={() => setSelectedDetails({ playbook, req: requiredIntegration })}
                  >
                    🔍 Ampliar Información, Parámetros & MITRE
                  </button>
                </div>
            </article>
          );
        })}
        </div>
      </section>

      {/* Render PlaybookDetailsModal when selectedDetails is active */}
      {selectedDetails && (
        <PlaybookDetailsModal
          playbook={selectedDetails.playbook}
          requiredIntegration={selectedDetails.req}
          onClose={() => setSelectedDetails(null)}
        />
      )}

      <details className="panel optional-engine">
        <summary>{t("optionalN8n")}</summary>
        <p className="muted">{t("optionalN8nHelp")}</p>
        <div className="playbook-list">
          {n8nCatalog.data?.items.map((playbook) => (
            <article key={playbook.workflow_id}>
              <div className="playbook-heading">
                <div>
                  <span className="demo-badge">n8n</span>
                  <h2>{playbook.name}</h2>
                  <code>{playbook.workflow_id}</code>
                </div>
                <div className="playbook-version">
                  <span>{t("version")}</span>
                  <strong>{playbook.version_id ?? t("notSynchronized")}</strong>
                </div>
              </div>
            </article>
          ))}
        </div>
      </details>

      <p className="security-note">{t("playbookCredentialBoundary")}</p>
    </>
  );
}
