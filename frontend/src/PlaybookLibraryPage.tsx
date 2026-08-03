import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import {
  getPlaybookDefinitions,
  getPlaybookManagement,
  getPlaybooks,
  togglePlaybookBinding,
} from "./api";
import "./playbook-library.css";

export function PlaybookLibraryPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();

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
          {nativeLibrary.data?.items.map((playbook) => (
            <article key={playbook.id}>
              <div className="playbook-heading">
                <div>
                  <span className={`demo-badge ${playbook.binding_active ? "active" : ""}`}>
                    {playbook.binding_active ? t("active") : t("inactive")}
                  </span>
                  <h2>
                    {i18n.language.startsWith("en")
                      ? playbook.title_i18n.en
                      : playbook.title_i18n.es}
                  </h2>
                  <code>{playbook.code}</code>
                </div>
                <div className="playbook-version">
                  <button
                    type="button"
                    className="button-link"
                    style={{ marginRight: "0.5rem" }}
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
                    className="button-link"
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

              <div className="connector-grid">
                <div>
                  <strong>{t("mitreTechniques")}</strong>
                  <small>
                    {playbook.mitre_codes && playbook.mitre_codes.length
                      ? playbook.mitre_codes.join(", ")
                      : "T1078"}
                  </small>
                </div>
                <div>
                  <strong>{t("mitigatedIncidentTypes")}</strong>
                  <small>
                    {playbook.target_incident_types && playbook.target_incident_types.length
                      ? playbook.target_incident_types.join(", ")
                      : "all-incidents"}
                  </small>
                </div>
                <div>
                  <strong>{t("rollback")}</strong>
                  <small>
                    <span
                      className="demo-badge active"
                      style={{ fontSize: "0.7rem", padding: "2px 6px", marginRight: "4px" }}
                    >
                      {t("rollbackSupported")}
                    </span>
                    {playbook.rollback_guidance_i18n
                      ? i18n.language.startsWith("en")
                        ? playbook.rollback_guidance_i18n.en
                        : playbook.rollback_guidance_i18n.es
                      : playbook.rollback_target_code
                        ? `(${playbook.rollback_target_code})`
                        : ""}
                  </small>
                </div>
                <div>
                  <strong>{t("automationPolicy")}</strong>
                  <small>
                    {playbook.automation_policy_i18n
                      ? i18n.language.startsWith("en")
                        ? playbook.automation_policy_i18n.en
                        : playbook.automation_policy_i18n.es
                      : t("noParameters")}
                  </small>
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>

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
