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
  validateAndPublishPlaybookVersion,
} from "./api";
import "./playbook-library.css";
import { PlaybookDetailsModal } from "./PlaybookDetailsModal";
import { PlaybookConfigurationModal } from "./PlaybookConfigurationModal";

/**
 * Blocking reasons arrive either as a bare code ("PLAYBOOK_NOT_PUBLISHED") or
 * scoped to the action that needs setting up ("ACTION_CREDENTIAL_MISSING:ticket.create").
 * Show the operator what to fix, falling back to the raw code so a new backend
 * reason is never silently swallowed.
 */
function describeBlockingReason(
  reason: string,
  t: ReturnType<typeof useTranslation>["t"],
): string {
  const [code, action] = reason.split(":");
  return t(`blockingReasons.${code}`, { defaultValue: reason, action: action ?? "" });
}

export function PlaybookLibraryPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [selectedDetails, setSelectedDetails] = useState<PlaybookDefinition | null>(null);
  const [selectedConfiguration, setSelectedConfiguration] = useState<PlaybookDefinition | null>(null);

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

  const publishMutation = useMutation({
    mutationFn: ({ versionId, digest }: { versionId: string; digest: string }) =>
      validateAndPublishPlaybookVersion(versionId, digest),
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

  const [categoryFilter, setCategoryFilter] = useState<"ALL" | "SOAR_SOPS" | "TRANSVERSAL">("ALL");

  const items = nativeLibrary.data?.items ?? [];
  const filteredItems = items.filter((pb) => {
    const isSop = pb.mitre_codes.length > 0 || [
      "compromised-account",
      "compromised-endpoint",
      "phishing-malicious-email",
      "ransomware-destructive",
      "lateral-movement",
      "malicious-indicator",
      "privilege-escalation",
      "security-control-disabled",
      "contain-and-document-incident",
    ].includes(pb.code);

    if (categoryFilter === "SOAR_SOPS") return isSop;
    if (categoryFilter === "TRANSVERSAL") return !isSop;
    return true;
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

        {/* Category Tabs */}
        <div style={{ display: "flex", gap: "8px", margin: "1rem 0", flexWrap: "wrap", alignItems: "center" }}>
          <span style={{ fontSize: "0.85rem", color: "var(--muted)", fontWeight: 600, marginRight: "4px" }}>
            Filtrar por categoría:
          </span>
          <button
            type="button"
            className="ghost"
            style={{
              padding: "5px 14px",
              fontSize: "0.8rem",
              borderRadius: "6px",
              background: categoryFilter === "ALL" ? "var(--panel-raised)" : "transparent",
              border: categoryFilter === "ALL" ? "1px solid var(--accent)" : "1px solid transparent",
              color: categoryFilter === "ALL" ? "var(--accent)" : "var(--text-soft)",
              fontWeight: categoryFilter === "ALL" ? 700 : 400,
            }}
            onClick={() => setCategoryFilter("ALL")}
          >
            📋 Todos ({items.length})
          </button>
          <button
            type="button"
            className="ghost"
            style={{
              padding: "5px 14px",
              fontSize: "0.8rem",
              borderRadius: "6px",
              background: categoryFilter === "SOAR_SOPS" ? "var(--panel-raised)" : "transparent",
              border: categoryFilter === "SOAR_SOPS" ? "1px solid var(--accent)" : "1px solid transparent",
              color: categoryFilter === "SOAR_SOPS" ? "var(--accent)" : "var(--text-soft)",
              fontWeight: categoryFilter === "SOAR_SOPS" ? 700 : 400,
            }}
            onClick={() => setCategoryFilter("SOAR_SOPS")}
          >
            🛡️ Procedimientos de Respuesta / SOPs ({items.filter(pb => pb.mitre_codes.length > 0 || ["compromised-account", "compromised-endpoint", "phishing-malicious-email", "ransomware-destructive", "lateral-movement", "malicious-indicator", "privilege-escalation", "security-control-disabled", "contain-and-document-incident"].includes(pb.code)).length})
          </button>
          <button
            type="button"
            className="ghost"
            style={{
              padding: "5px 14px",
              fontSize: "0.8rem",
              borderRadius: "6px",
              background: categoryFilter === "TRANSVERSAL" ? "var(--panel-raised)" : "transparent",
              border: categoryFilter === "TRANSVERSAL" ? "1px solid var(--accent)" : "1px solid transparent",
              color: categoryFilter === "TRANSVERSAL" ? "var(--accent)" : "var(--text-soft)",
              fontWeight: categoryFilter === "TRANSVERSAL" ? 700 : 400,
            }}
            onClick={() => setCategoryFilter("TRANSVERSAL")}
          >
            ⚙️ Tareas Operativas Transversales ({items.filter(pb => pb.mitre_codes.length === 0 && !["compromised-account", "compromised-endpoint", "phishing-malicious-email", "ransomware-destructive", "lateral-movement", "malicious-indicator", "privilege-escalation", "security-control-disabled", "contain-and-document-incident"].includes(pb.code)).length})
          </button>
        </div>

        {nativeLibrary.isLoading && <p>{t("loading")}</p>}
        {nativeLibrary.isError && <p role="alert">{t("error")}</p>}
        {filteredItems.length === 0 && <p>{t("emptyState")}</p>}
        <div className="playbook-list">
          {filteredItems.map((playbook) => {
            const currentMode = playbook.approval_mode ?? "AUTOMATIC";
            const isPublished = playbook.publication_status === "PUBLISHED";
            // An incompletely configured playbook is not an available capability:
            // it cannot be activated (nor engine-switched, which also activates),
            // and the card is muted so the state is obvious in the listing.
            const isReady = playbook.readiness_status === "READY";
            const needsConfiguration = !isReady;
            return (
              <article
                key={playbook.id}
                className={needsConfiguration ? "playbook-card-disabled" : undefined}
                aria-disabled={needsConfiguration || undefined}
              >
                <div className="playbook-heading" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "12px", flexWrap: "wrap", marginBottom: "0.75rem" }}>
                  <div>
                    <div style={{ display: "flex", gap: "6px", alignItems: "center", flexWrap: "wrap", marginBottom: "6px" }}>
                      {needsConfiguration ? (
                        <span className="playbook-disabled-badge">🚫 {t("playbookDisabled")}</span>
                      ) : (
                        <span className="demo-badge active">{playbook.readiness_status}</span>
                      )}
                      <span
                        className="demo-badge"
                        style={{
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
                    </div>
                    <h2 style={{ margin: "4px 0 2px", fontSize: "1.25rem" }}>
                      {i18n.language.startsWith("en")
                        ? playbook.title_i18n.en
                        : playbook.title_i18n.es}
                    </h2>
                    <code>{playbook.code}</code>
                  </div>

                  {/* Top Right Action Button Row */}
                  <div style={{ display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" }}>
                    <button
                      type="button"
                      className="ghost"
                      style={{
                        padding: "6px 12px",
                        fontSize: "0.775rem",
                        height: "auto",
                        minHeight: "unset",
                        minWidth: "unset",
                        width: "auto",
                        whiteSpace: "nowrap",
                        border: "1px solid var(--line)",
                        fontWeight: 600,
                      }}
                      onClick={() => setSelectedConfiguration(playbook)}
                    >
                      ⚙️ Configurar
                    </button>
                    {playbook.publication_status === "DRAFT"
                      && playbook.latest_version_id
                      && playbook.latest_artifact_sha256 && (
                      <button
                        type="button"
                        className="ghost"
                        style={{
                          padding: "6px 12px",
                          fontSize: "0.775rem",
                          height: "auto",
                          minHeight: "unset",
                          minWidth: "unset",
                          width: "auto",
                          whiteSpace: "nowrap",
                        }}
                        disabled={publishMutation.isPending}
                        onClick={() => publishMutation.mutate({
                          versionId: playbook.latest_version_id!,
                          digest: playbook.latest_artifact_sha256!,
                        })}
                      >
                        Validar y publicar
                      </button>
                    )}
                    <button
                      type="button"
                      className="ghost"
                      style={{
                        padding: "6px 12px",
                        fontSize: "0.775rem",
                        height: "auto",
                        minHeight: "unset",
                        minWidth: "unset",
                        width: "auto",
                        whiteSpace: "nowrap",
                        border: "1px solid var(--accent)",
                        color: "var(--accent)",
                        fontWeight: 600,
                      }}
                      onClick={() => setSelectedDetails(playbook)}
                    >
                      ℹ️ {t("viewPlaybookDetails")}
                    </button>
                    <button
                      type="button"
                      className={playbook.binding_active ? "ghost" : "primary"}
                      style={{
                        padding: "6px 12px",
                        fontSize: "0.775rem",
                        height: "auto",
                        minHeight: "unset",
                        minWidth: "unset",
                        width: "auto",
                        whiteSpace: "nowrap",
                      }}
                      disabled={
                        toggleMutation.isPending
                        || !isPublished
                        // Never allow turning ON a playbook that cannot actually run.
                        || (!playbook.binding_active && needsConfiguration)
                      }
                      title={
                        !playbook.binding_active && needsConfiguration
                          ? t("cannotActivateIncomplete")
                          : undefined
                      }
                      onClick={() =>
                        toggleMutation.mutate({
                          id: playbook.id,
                          input: { active: !playbook.binding_active },
                        })
                      }
                    >
                      {playbook.binding_active ? t("deactivatePlaybook") : t("activatePlaybook")}
                    </button>
                    <button
                      type="button"
                      className="ghost"
                      style={{
                        padding: "6px 12px",
                        fontSize: "0.775rem",
                        height: "auto",
                        minHeight: "unset",
                        minWidth: "unset",
                        width: "auto",
                        whiteSpace: "nowrap",
                      }}
                      disabled={
                        toggleMutation.isPending
                        || !isPublished
                        // Switching engines activates the playbook, so it is
                        // blocked for the same reason as activation.
                        || needsConfiguration
                      }
                      title={needsConfiguration ? t("cannotActivateIncomplete") : undefined}
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

                <div className="playbook-facts">
                  <div>
                    <span>{t("automationEngine")}</span>
                    <strong>
                      {playbook.engine_type === "NATIVE"
                        ? "Cyrvanta Native"
                        : playbook.engine_type ?? t("engineNotBound")}
                    </strong>
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
                {playbook.blocking_reasons.length > 0 && (
                  <div className="security-note" role="status">
                    <strong>{t("blockingReasonsTitle")}</strong>
                    <ul>
                      {playbook.blocking_reasons.map((reason) => (
                        <li key={reason}>{describeBlockingReason(reason, t)}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Gobernanza Bar */}
                <div className="connector-grid" style={{ marginBottom: "0.5rem" }}>
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
                          👤 Simple
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

                {/* Card Action Footer */}
                <div style={{ borderTop: "1px solid var(--line)", paddingTop: "8px", marginTop: "8px", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
                  <div style={{ display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap" }}>
                    {playbook.rollback_supported && (
                      <span className="demo-badge active">{t("rollbackSupported")}</span>
                    )}
                    {playbook.mitre_codes.length > 0 ? (
                      <div style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                        <span style={{ fontSize: "0.75rem", color: "var(--muted)", fontWeight: 600 }}>🛡️ Mitiga:</span>
                        {playbook.mitre_codes.map((code) => (
                          <span
                            key={code}
                            style={{
                              padding: "2px 6px",
                              borderRadius: "4px",
                              fontSize: "0.7rem",
                              background: "rgba(59, 130, 246, 0.12)",
                              color: "#60a5fa",
                              border: "1px solid rgba(59, 130, 246, 0.3)",
                              fontWeight: 600,
                            }}
                          >
                            {code}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span style={{ fontSize: "0.75rem", color: "var(--muted)" }}>
                        {t("mitreTechniques")}: {t("noMitreMappings")}
                      </span>
                    )}
                  </div>
                </div>
            </article>
          );
        })}
        </div>
      </section>

      {/* Render PlaybookDetailsModal when selectedDetails is active */}
      {selectedDetails && (
        <PlaybookDetailsModal
          playbook={selectedDetails}
          onClose={() => setSelectedDetails(null)}
        />
      )}

      {selectedConfiguration && (
        <PlaybookConfigurationModal
          playbook={selectedConfiguration}
          onClose={() => setSelectedConfiguration(null)}
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
