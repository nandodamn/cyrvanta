import { useTranslation } from "react-i18next";

import { PlaybookDefinition } from "./api";

interface PlaybookDetailsModalProps {
  playbook: PlaybookDefinition;
  onClose: () => void;
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        minWidth: 0,
        padding: "10px 12px",
        border: "1px solid var(--line)",
        borderRadius: "8px",
        background: "var(--panel-raised)",
      }}
    >
      <div style={{ color: "var(--muted)", fontSize: "0.75rem", marginBottom: "3px" }}>{label}</div>
      <div style={{ overflowWrap: "anywhere", fontWeight: 650 }}>{value}</div>
    </div>
  );
}

function TagList({ values, emptyLabel }: { values: string[]; emptyLabel: string }) {
  if (values.length === 0) {
    return <p style={{ margin: 0, color: "var(--muted)" }}>{emptyLabel}</p>;
  }
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
      {values.map((value) => (
        <code key={value} style={{ overflowWrap: "anywhere" }}>
          {value}
        </code>
      ))}
    </div>
  );
}

export function PlaybookDetailsModal({ playbook, onClose }: PlaybookDetailsModalProps) {
  const { t, i18n } = useTranslation();
  const english = i18n.language.startsWith("en");
  const title = english ? playbook.title_i18n.en : playbook.title_i18n.es;
  const description =
    playbook.publication_status === "PUBLISHED"
      ? english
        ? playbook.description_i18n.en
        : playbook.description_i18n.es
      : t("draftDescriptionUnavailable");
  const engine =
    playbook.engine_type === "NATIVE"
      ? "Cyrvanta Native"
      : playbook.engine_type === "N8N"
        ? "n8n"
        : t("engineNotBound");
  const runtimeReady = playbook.readiness_status === "READY";
  const policy = playbook.automation_policy_i18n
    ? english
      ? playbook.automation_policy_i18n.en
      : playbook.automation_policy_i18n.es
    : t("policyNotSpecified");
  const rollbackGuidance = playbook.rollback_guidance_i18n
    ? english
      ? playbook.rollback_guidance_i18n.en
      : playbook.rollback_guidance_i18n.es
    : t("rollbackGuidanceUnavailable");
  const lastExecutedAt = playbook.last_executed_at
    ? new Intl.DateTimeFormat(i18n.language, {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(new Date(playbook.last_executed_at))
    : t("neverExecuted");

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
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
        role="dialog"
        aria-modal="true"
        aria-labelledby="playbook-details-title"
        style={{
          background: "var(--panel)",
          border: "1px solid var(--panel-border)",
          borderRadius: "12px",
          width: "min(750px, 100%)",
          maxHeight: "90vh",
          overflowY: "auto",
          padding: "clamp(1rem, 3vw, 1.75rem)",
          boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.5)",
          color: "var(--text)",
        }}
        onClick={(event) => event.stopPropagation()}
      >
        <header
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            gap: "12px",
            marginBottom: "1.25rem",
            borderBottom: "1px solid var(--line)",
            paddingBottom: "1rem",
          }}
        >
          <div style={{ minWidth: 0 }}>
            <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginBottom: "6px" }}>
              <span className="demo-badge active">{engine}</span>
              <span className={runtimeReady ? "demo-badge active" : "demo-badge"}>
                {runtimeReady ? "LIVE READY" : t("configurationPending")}
              </span>
            </div>
            <h2 id="playbook-details-title" style={{ margin: 0, fontSize: "1.35rem" }}>
              {title}
            </h2>
            <code style={{ overflowWrap: "anywhere" }}>{playbook.code}</code>
          </div>
          <button type="button" className="ghost" onClick={onClose} aria-label={t("close")}>
            ×
          </button>
        </header>

        <p style={{ color: "var(--text-soft)" }}>{description}</p>

        <section
          aria-label={t("controlPlane")}
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(min(180px, 100%), 1fr))",
            gap: "8px",
            marginBottom: "1.25rem",
          }}
        >
          <DetailRow
            label={t("publicationStatus")}
            value={playbook.publication_status ?? t("notAvailable")}
          />
          <DetailRow label={t("version")} value={playbook.latest_version ?? t("notAvailable")} />
          <DetailRow
            label={t("bindingStatus")}
            value={playbook.binding_status ?? t("notAvailable")}
          />
          <DetailRow label={t("mode")} value={playbook.execution_mode ?? t("notAvailable")} />
          <DetailRow label={t("impact")} value={playbook.impact ?? t("notAvailable")} />
          <DetailRow label={t("approvalMode")} value={playbook.approval_mode} />
          <DetailRow
            label={t("lastExecution")}
            value={playbook.last_execution_status ?? t("neverExecuted")}
          />
          <DetailRow label={t("lastExecutionAt")} value={lastExecutedAt} />
        </section>

        <section style={{ marginBottom: "1.25rem" }}>
          <h3>{t("parameters")}</h3>
          <TagList values={playbook.required_parameters} emptyLabel={t("noParameters")} />
        </section>

        <section style={{ marginBottom: "1.25rem" }}>
          <h3>{t("credentialAliases")}</h3>
          <TagList values={playbook.credential_aliases} emptyLabel={t("noCredentialAliases")} />
          <p style={{ color: "var(--muted)", fontSize: "0.8rem" }}>
            {t("playbookCredentialBoundary")}
          </p>
        </section>

        <section style={{ marginBottom: "1.25rem" }}>
          <h3>{t("mitreTechniques")}</h3>
          <TagList values={playbook.mitre_codes} emptyLabel={t("noMitreMappings")} />
        </section>

        <section style={{ marginBottom: "1.25rem" }}>
          <h3>{t("mitigatedIncidentTypes")}</h3>
          <TagList values={playbook.target_incident_types} emptyLabel={t("scopeNotSpecified")} />
        </section>

        <section style={{ marginBottom: "1.25rem" }}>
          <h3>{t("automationPolicy")}</h3>
          <p style={{ margin: 0, color: "var(--text-soft)" }}>{policy}</p>
        </section>

        <section style={{ marginBottom: "1.25rem" }}>
          <h3>{t("rollback")}</h3>
          {playbook.rollback_supported ? (
            <>
              <span className="demo-badge active">{t("rollbackSupported")}</span>
              <p style={{ color: "var(--text-soft)" }}>{rollbackGuidance}</p>
            </>
          ) : (
            <p style={{ margin: 0, color: "var(--muted)" }}>{t("rollbackUnavailable")}</p>
          )}
        </section>

        <footer
          style={{
            display: "flex",
            justifyContent: "flex-end",
            paddingTop: "1rem",
            borderTop: "1px solid var(--line)",
          }}
        >
          <button type="button" className="primary" onClick={onClose}>
            {t("close")}
          </button>
        </footer>
      </div>
    </div>
  );
}
