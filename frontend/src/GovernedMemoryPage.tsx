import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  createFeedback,
  createMemoryCandidate,
  getActiveMemory,
  getMemoryCandidates,
  getMemoryMetrics,
  reviewMemoryVersion,
  transitionMemoryVersion,
  type MemoryCandidate,
} from "./api";

const OUTCOMES = [
  "TRUE_POSITIVE",
  "FALSE_POSITIVE",
  "BENIGN_TRUE_POSITIVE",
  "INCONCLUSIVE",
  "ACTION_EFFECTIVE",
  "ACTION_INEFFECTIVE",
  "ACTION_PARTIAL",
  "NOT_ASSESSED",
] as const;

function isoDaysFromNow(days: number): string {
  const date = new Date(Date.now() + days * 86_400_000);
  return date.toISOString().slice(0, 16);
}

function MemoryCard({ item }: { item: MemoryCandidate }) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");
  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["memory-candidates"] }),
      queryClient.invalidateQueries({ queryKey: ["memory-active"] }),
    ]);
  };
  const transition = useMutation({
    mutationFn: (action: "review-request" | "activate" | "disable") =>
      transitionMemoryVersion(item.version_id, action, reason),
    onSuccess: refresh,
  });
  const review = useMutation({
    mutationFn: (decision: "APPROVE" | "REJECT" | "REQUEST_CHANGES") =>
      reviewMemoryVersion(item.version_id, decision, reason),
    onSuccess: refresh,
  });

  const title = i18n.language.startsWith("es") ? item.title_es : item.title_en;
  const statement = i18n.language.startsWith("es") ? item.statement_es : item.statement_en;
  const busy = transition.isPending || review.isPending;
  const failed = transition.isError || review.isError;

  return (
    <article
      className="panel memory-card"
      style={{
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        border: "1px solid var(--panel-border)",
        borderRadius: "8px",
        padding: "1.25rem",
      }}
    >
      <div>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            gap: "10px",
            marginBottom: "12px",
          }}
        >
          <div>
            <p className="eyebrow" style={{ margin: 0 }}>
              {item.kind} · v{item.version}
            </p>
            <h3 style={{ margin: "4px 0 0", fontSize: "1.1rem" }}>{title}</h3>
          </div>
          <span
            className={`memory-state state-${item.status.toLowerCase()}`}
            style={{
              padding: "4px 10px",
              borderRadius: "4px",
              fontSize: "0.75rem",
              fontWeight: 700,
              letterSpacing: "0.03em",
              textTransform: "uppercase",
              background:
                item.status === "ACTIVE"
                  ? "var(--accent)"
                  : item.status === "DRAFT"
                  ? "var(--panel-raised)"
                  : "var(--line)",
              color: item.status === "ACTIVE" ? "#041512" : "var(--text)",
            }}
          >
            {item.status}
          </span>
        </div>

        <p style={{ fontSize: "0.9rem", lineHeight: 1.5, margin: "8px 0 14px", color: "var(--text)" }}>
          {statement}
        </p>

        <dl
          className="memory-facts"
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "10px",
            background: "var(--panel-raised)",
            padding: "10px 12px",
            borderRadius: "6px",
            fontSize: "0.85rem",
            margin: "10px 0",
          }}
        >
          <div>
            <dt style={{ color: "var(--muted)", fontSize: "0.75rem" }}>{t("memory.source")}</dt>
            <dd style={{ margin: 0, fontWeight: 600 }}>{item.source_type}</dd>
          </div>
          <div>
            <dt style={{ color: "var(--muted)", fontSize: "0.75rem" }}>{t("memory.evidenceCount")}</dt>
            <dd style={{ margin: 0, fontWeight: 600 }}>{item.evidence_refs.length}</dd>
          </div>
          <div>
            <dt style={{ color: "var(--muted)", fontSize: "0.75rem" }}>{t("memory.validity")}</dt>
            <dd style={{ margin: 0, fontSize: "0.8rem" }}>
              {new Date(item.valid_from).toLocaleDateString(i18n.language)} –{" "}
              {new Date(item.valid_until).toLocaleDateString(i18n.language)}
            </dd>
          </div>
          <div>
            <dt style={{ color: "var(--muted)", fontSize: "0.75rem" }}>{t("memory.author")}</dt>
            <dd style={{ margin: 0, fontSize: "0.8rem" }}>{item.created_by_user_id.slice(0, 8)}</dd>
          </div>
        </dl>

        <div style={{ marginTop: "12px", display: "flex", flexDirection: "column", gap: "6px" }}>
          <details style={{ fontSize: "0.85rem", color: "var(--text-soft)" }}>
            <summary style={{ cursor: "pointer", fontWeight: 600, padding: "4px 0" }}>
              {t("memory.history")} ({item.state_history.length})
            </summary>
            <ol className="memory-history" style={{ margin: "8px 0 0", paddingLeft: "1.2rem" }}>
              {item.state_history.map((event) => (
                <li key={event.id} style={{ margin: "4px 0" }}>
                  <strong>{event.to_status}</strong> · {event.reason} ·{" "}
                  <time dateTime={event.occurred_at}>
                    {new Date(event.occurred_at).toLocaleString(i18n.language)}
                  </time>
                </li>
              ))}
            </ol>
          </details>

          <details style={{ fontSize: "0.85rem", color: "var(--text-soft)" }}>
            <summary style={{ cursor: "pointer", fontWeight: 600, padding: "4px 0" }}>
              {t("memory.reviews", { count: item.reviews.length })}
            </summary>
            {item.reviews.length === 0 ? (
              <p className="muted" style={{ margin: "6px 0", fontSize: "0.8rem" }}>
                {t("memory.noReviews")}
              </p>
            ) : (
              <ul className="memory-history" style={{ margin: "8px 0 0", paddingLeft: "1.2rem" }}>
                {item.reviews.map((entry) => (
                  <li key={entry.id} style={{ margin: "4px 0" }}>
                    <strong>{entry.decision}</strong> · {entry.reason}
                  </li>
                ))}
              </ul>
            )}
          </details>
        </div>
      </div>

      {!item.is_synthetic &&
        !["REJECTED", "EXPIRED", "DISABLED", "SUPERSEDED"].includes(item.status) && (
          <div
            className="memory-actions"
            style={{
              marginTop: "16px",
              paddingTop: "12px",
              borderTop: "1px solid var(--line)",
              display: "flex",
              flexDirection: "column",
              gap: "8px",
            }}
          >
            <label style={{ fontSize: "0.85rem" }}>
              <span>{t("memory.actionReason")}</span>
              <input
                style={{ width: "100%", marginTop: "4px", padding: "6px 10px" }}
                value={reason}
                placeholder={t("memory.actionReasonPlaceholder", { defaultValue: "Justificación de la acción..." })}
                maxLength={1000}
                onChange={(event) => setReason(event.target.value)}
              />
            </label>
            <div className="form-actions" style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginTop: "4px" }}>
              {item.status === "DRAFT" && (
                <button
                  type="button"
                  style={{ flex: 1 }}
                  disabled={busy || !reason.trim()}
                  onClick={() => transition.mutate("review-request")}
                >
                  {t("memory.requestReview")}
                </button>
              )}
              {item.status === "IN_REVIEW" && (
                <>
                  <button
                    type="button"
                    style={{ flex: 1 }}
                    disabled={busy || !reason.trim()}
                    onClick={() => review.mutate("APPROVE")}
                  >
                    ✓ {t("memory.approve")}
                  </button>
                  <button
                    type="button"
                    className="ghost"
                    style={{ flex: 1 }}
                    disabled={busy || !reason.trim()}
                    onClick={() => review.mutate("REQUEST_CHANGES")}
                  >
                    {t("memory.requestChanges")}
                  </button>
                  <button
                    type="button"
                    className="ghost"
                    style={{ flex: 1 }}
                    disabled={busy || !reason.trim()}
                    onClick={() => review.mutate("REJECT")}
                  >
                    ✕ {t("memory.reject")}
                  </button>
                </>
              )}
              {item.status === "APPROVED" && (
                <button
                  type="button"
                  style={{ flex: 1 }}
                  disabled={busy || !reason.trim()}
                  onClick={() => transition.mutate("activate")}
                >
                  ▶ {t("memory.activate")}
                </button>
              )}
              {["APPROVED", "ACTIVE"].includes(item.status) && (
                <button
                  type="button"
                  className="ghost"
                  style={{ flex: 1 }}
                  disabled={busy || !reason.trim()}
                  onClick={() => transition.mutate("disable")}
                >
                  {t("memory.disable")}
                </button>
              )}
            </div>
            {failed && <p className="form-error" style={{ margin: "4px 0 0" }}>{t("memory.separationError")}</p>}
          </div>
        )}
    </article>
  );
}

export function GovernedMemoryPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<"base" | "capture" | "governance">("base");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  const candidates = useQuery({ queryKey: ["memory-candidates"], queryFn: getMemoryCandidates });
  const active = useQuery({ queryKey: ["memory-active"], queryFn: getActiveMemory });
  const metrics = useQuery({ queryKey: ["memory-metrics"], queryFn: getMemoryMetrics });

  const [feedback, setFeedback] = useState({
    resource_type: "INCIDENT",
    resource_id: "",
    outcome: "TRUE_POSITIVE",
    reason: "",
  });

  const [candidate, setCandidate] = useState({
    kind: "CASE_NOTE",
    title: "",
    statement: "",
    evidence_refs: "",
    valid_until: isoDaysFromNow(30),
  });

  const feedbackMutation = useMutation({
    mutationFn: () => createFeedback({ ...feedback, occurred_at: new Date().toISOString() }),
    onSuccess: () => setFeedback((current) => ({ ...current, resource_id: "", reason: "" })),
  });

  const candidateMutation = useMutation({
    mutationFn: () =>
      createMemoryCandidate({
        kind: candidate.kind,
        source_type: "HUMAN",
        title_es: candidate.title,
        title_en: candidate.title,
        statement_es: candidate.statement,
        statement_en: candidate.statement,
        conditions: {},
        evidence_refs: candidate.evidence_refs
          .split(",")
          .map((value) => value.trim())
          .filter(Boolean),
        valid_from: new Date().toISOString(),
        valid_until: new Date(candidate.valid_until).toISOString(),
      }),
    onSuccess: async () => {
      setCandidate((current) => ({
        ...current,
        title: "",
        statement: "",
        evidence_refs: "",
      }));
      await queryClient.invalidateQueries({ queryKey: ["memory-candidates"] });
    },
  });

  const submitFeedback = (event: FormEvent) => {
    event.preventDefault();
    feedbackMutation.mutate();
  };

  const submitCandidate = (event: FormEvent) => {
    event.preventDefault();
    candidateMutation.mutate();
  };

  const filteredCandidates = candidates.data?.filter((item) => {
    if (statusFilter === "ALL") return true;
    return item.status === statusFilter;
  }) ?? [];

  return (
    <>
      <div
        className="page-title"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-end",
          flexWrap: "wrap",
          gap: "1rem",
          marginBottom: "1.25rem",
        }}
      >
        <div>
          <p className="eyebrow">OBSERVATIONAL_ONLY</p>
          <h1 style={{ margin: "4px 0" }}>{t("memory.title")}</h1>
          <p className="muted" style={{ margin: 0 }}>{t("memory.intro")}</p>
        </div>

        {/* Enterprise Tab Bar Segmented Control directly in header */}
        <nav
          aria-label="Governed Memory Tabs"
          style={{
            display: "inline-flex",
            gap: "4px",
            background: "var(--panel-raised)",
            border: "1px solid var(--line)",
            borderRadius: "8px",
            padding: "4px",
            maxWidth: "100%",
            overflowX: "auto",
          }}
        >
          <button
            type="button"
            style={{
              border: "none",
              borderRadius: "6px",
              padding: "8px 16px",
              fontSize: "0.875rem",
              fontWeight: activeTab === "base" ? 600 : 400,
              cursor: "pointer",
              background: activeTab === "base" ? "var(--accent)" : "transparent",
              color: activeTab === "base" ? "#041512" : "var(--text)",
              transition: "all 0.2s ease",
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
            }}
            onClick={() => setActiveTab("base")}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <ellipse cx="12" cy="5" rx="9" ry="3" />
              <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
              <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
            </svg>
            {t("memory.tabBase", { defaultValue: "Base de Memoria Operacional" })} ({candidates.data?.length ?? 0})
          </button>
          <button
            type="button"
            style={{
              border: "none",
              borderRadius: "6px",
              padding: "8px 16px",
              fontSize: "0.875rem",
              fontWeight: activeTab === "capture" ? 600 : 400,
              cursor: "pointer",
              background: activeTab === "capture" ? "var(--accent)" : "transparent",
              color: activeTab === "capture" ? "#041512" : "var(--text)",
              transition: "all 0.2s ease",
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
            }}
            onClick={() => setActiveTab("capture")}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 5v14M5 12h14" />
            </svg>
            {t("memory.tabCapture", { defaultValue: "Registrar Feedback & Candidato" })}
          </button>
          <button
            type="button"
            style={{
              border: "none",
              borderRadius: "6px",
              padding: "8px 16px",
              fontSize: "0.875rem",
              fontWeight: activeTab === "governance" ? 600 : 400,
              cursor: "pointer",
              background: activeTab === "governance" ? "var(--accent)" : "transparent",
              color: activeTab === "governance" ? "#041512" : "var(--text)",
              transition: "all 0.2s ease",
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
            }}
            onClick={() => setActiveTab("governance")}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            {t("memory.tabGovernance", { defaultValue: "Gobernanza & Métricas" })}
          </button>
        </nav>
      </div>

      {/* Clean Compact Safety Rule Strip (Single instance, no duplication) */}
      <div
        className="panel memory-boundary"
        style={{
          padding: "10px 14px",
          marginBottom: "1.25rem",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "12px",
          fontSize: "0.85rem",
        }}
      >
        <div>
          <strong style={{ color: "var(--accent)" }}>{t("memory.safetyTitle")}</strong>: {t("memory.safetyBody")}
        </div>
        <div style={{ display: "flex", gap: "16px", fontSize: "0.8rem", color: "var(--text-soft)" }}>
          <span>{t("memory.candidates")}: <strong style={{ color: "var(--text)" }}>{candidates.data?.length ?? 0}</strong></span>
          <span>{t("memory.active")}: <strong style={{ color: "var(--text)" }}>{active.data?.length ?? 0}</strong></span>
          <span>{t("memory.metrics")}: <strong style={{ color: "var(--text)" }}>{metrics.data?.length ?? 0}</strong></span>
        </div>
      </div>

      {activeTab === "base" && (
        <>
          {/* Status Quick Filters */}
          <div
            style={{
              display: "flex",
              gap: "8px",
              marginBottom: "1.25rem",
              flexWrap: "wrap",
              alignItems: "center",
            }}
          >
            <span style={{ fontSize: "0.85rem", color: "var(--muted)", fontWeight: 600, marginRight: "4px" }}>
              {t("filter", { defaultValue: "Filtrar por estado:" })}
            </span>
            {["ALL", "ACTIVE", "IN_REVIEW", "DRAFT", "APPROVED", "DISABLED"].map((statusKey) => (
              <button
                key={statusKey}
                type="button"
                className="ghost"
                style={{
                  padding: "4px 12px",
                  fontSize: "0.8rem",
                  minHeight: "32px",
                  background: statusFilter === statusKey ? "var(--panel-raised)" : "transparent",
                  border: statusFilter === statusKey ? "1px solid var(--accent)" : "1px solid transparent",
                  color: statusFilter === statusKey ? "var(--accent)" : "var(--text-soft)",
                }}
                onClick={() => setStatusFilter(statusKey)}
              >
                {statusKey === "ALL" ? t("all", { defaultValue: "Todas" }) : statusKey}
              </button>
            ))}
          </div>

          <section className="memory-list" aria-live="polite">
            {candidates.isLoading && <p>{t("loading")}</p>}
            {candidates.isError && <p className="form-error">{t("loadError")}</p>}
            {!candidates.isLoading && !candidates.isError && filteredCandidates.length === 0 && (
              <div className="panel" style={{ textAlign: "center", padding: "2rem" }}>
                <p className="muted">{t("memory.noCandidates", { defaultValue: "No hay patrones de memoria registrados en este estado." })}</p>
              </div>
            )}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))",
                gap: "14px",
                width: "100%",
              }}
            >
              {filteredCandidates.map((item) => (
                <MemoryCard key={item.id} item={item} />
              ))}
            </div>
          </section>
        </>
      )}

      {activeTab === "capture" && (
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "1.25rem",
            width: "100%",
            boxSizing: "border-box",
          }}
        >
          <form
            onSubmit={submitFeedback}
            style={{
              display: "flex",
              flexDirection: "column",
              flex: "1 1 380px",
              minWidth: "300px",
              width: "100%",
              boxSizing: "border-box",
              padding: "1.5rem",
              background: "var(--panel)",
              border: "1px solid var(--panel-border)",
              borderRadius: "8px",
              boxShadow: "0 4px 12px rgba(0,0,0,0.2)",
            }}
          >
            <h2 style={{ margin: 0 }}>{t("memory.recordFeedback")}</h2>
            <p className="muted" style={{ fontSize: "0.85rem", margin: "4px 0 1rem" }}>
              {t("memory.feedbackIntro", { defaultValue: "Registra observaciones de campo inmutables sobre recursos autoritativos existentes." })}
            </p>
            <label style={{ display: "flex", flexDirection: "column", gap: "4px", marginBottom: "12px", width: "100%", boxSizing: "border-box" }}>
              <span>{t("memory.resourceType")}</span>
              <select
                style={{ width: "100%", boxSizing: "border-box", padding: "8px 10px" }}
                value={feedback.resource_type}
                onChange={(e) => setFeedback({ ...feedback, resource_type: e.target.value })}
              >
                {["INCIDENT", "FINDING", "CLAIM", "ACTION_PROPOSAL", "PLAYBOOK_EXECUTION"].map(
                  (value) => (
                    <option key={value}>{value}</option>
                  ),
                )}
              </select>
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: "4px", marginBottom: "12px", width: "100%", boxSizing: "border-box" }}>
              <span>{t("memory.resourceId")}</span>
              <input
                required
                style={{ width: "100%", boxSizing: "border-box", padding: "8px 10px" }}
                value={feedback.resource_id}
                placeholder="UUID del recurso..."
                onChange={(e) => setFeedback({ ...feedback, resource_id: e.target.value })}
              />
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: "4px", marginBottom: "12px", width: "100%", boxSizing: "border-box" }}>
              <span>{t("memory.outcome")}</span>
              <select
                style={{ width: "100%", boxSizing: "border-box", padding: "8px 10px" }}
                value={feedback.outcome}
                onChange={(e) => setFeedback({ ...feedback, outcome: e.target.value })}
              >
                {OUTCOMES.map((value) => (
                  <option key={value}>{value}</option>
                ))}
              </select>
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: "4px", marginBottom: "12px", width: "100%", boxSizing: "border-box" }}>
              <span>{t("memory.reason")}</span>
              <textarea
                required
                rows={3}
                maxLength={1000}
                style={{ width: "100%", boxSizing: "border-box", padding: "8px 10px" }}
                value={feedback.reason}
                placeholder="Justificación u observación..."
                onChange={(e) => setFeedback({ ...feedback, reason: e.target.value })}
              />
            </label>
            <button type="submit" disabled={feedbackMutation.isPending} style={{ width: "100%", minHeight: "40px" }}>
              {t("memory.saveFeedback")}
            </button>
            {feedbackMutation.isError && <p className="form-error" style={{ marginTop: "8px" }}>{t("actionError")}</p>}
          </form>

          <form
            onSubmit={submitCandidate}
            style={{
              display: "flex",
              flexDirection: "column",
              flex: "1 1 380px",
              minWidth: "300px",
              width: "100%",
              boxSizing: "border-box",
              padding: "1.5rem",
              background: "var(--panel)",
              border: "1px solid var(--panel-border)",
              borderRadius: "8px",
              boxShadow: "0 4px 12px rgba(0,0,0,0.2)",
            }}
          >
            <h2 style={{ margin: 0 }}>{t("memory.proposeCandidate")}</h2>
            <p className="muted" style={{ fontSize: "0.85rem", margin: "4px 0 1rem" }}>
              {t("memory.candidateIntro", { defaultValue: "Crea una propuesta de patrón o lección aprendida para ser revisada por un 2º analista." })}
            </p>
            <label style={{ display: "flex", flexDirection: "column", gap: "4px", marginBottom: "12px", width: "100%", boxSizing: "border-box" }}>
              <span>{t("memory.kind")}</span>
              <select
                style={{ width: "100%", boxSizing: "border-box", padding: "8px 10px" }}
                value={candidate.kind}
                onChange={(e) => setCandidate({ ...candidate, kind: e.target.value })}
              >
                <option>CASE_NOTE</option>
                <option>TREND</option>
              </select>
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: "4px", marginBottom: "12px", width: "100%", boxSizing: "border-box" }}>
              <span>{t("memory.candidateTitle")}</span>
              <input
                required
                maxLength={200}
                style={{ width: "100%", boxSizing: "border-box", padding: "8px 10px" }}
                value={candidate.title}
                placeholder="Título descriptivo de la lección aprendida..."
                onChange={(e) => setCandidate({ ...candidate, title: e.target.value })}
              />
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: "4px", marginBottom: "12px", width: "100%", boxSizing: "border-box" }}>
              <span>{t("memory.statement")}</span>
              <textarea
                required
                rows={3}
                maxLength={2000}
                style={{ width: "100%", boxSizing: "border-box", padding: "8px 10px" }}
                value={candidate.statement}
                placeholder="Descripción detallada del patrón u observación aprendida..."
                onChange={(e) => setCandidate({ ...candidate, statement: e.target.value })}
              />
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: "4px", marginBottom: "12px", width: "100%", boxSizing: "border-box" }}>
              <span>{t("memory.evidenceIds")}</span>
              <input
                required
                style={{ width: "100%", boxSizing: "border-box", padding: "8px 10px" }}
                value={candidate.evidence_refs}
                placeholder="IDs separados por coma..."
                onChange={(e) => setCandidate({ ...candidate, evidence_refs: e.target.value })}
              />
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: "4px", marginBottom: "12px", width: "100%", boxSizing: "border-box" }}>
              <span>{t("memory.validUntil")}</span>
              <input
                required
                type="datetime-local"
                style={{ width: "100%", boxSizing: "border-box", padding: "8px 10px" }}
                value={candidate.valid_until}
                onChange={(e) => setCandidate({ ...candidate, valid_until: e.target.value })}
              />
            </label>
            <button type="submit" disabled={candidateMutation.isPending} style={{ width: "100%", minHeight: "40px" }}>
              {t("memory.propose")}
            </button>
            {candidateMutation.isError && <p className="form-error" style={{ marginTop: "8px" }}>{t("actionError")}</p>}
          </form>
        </div>
      )}

      {activeTab === "governance" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
          <section className="panel" style={{ padding: "1.25rem" }}>
            <h2>{t("memory.metrics")}</h2>
            <p className="muted" style={{ fontSize: "0.85rem", marginBottom: "1rem" }}>
              {t("memory.metricsIntro", { defaultValue: "Métricas de tamaño de muestra e idoneidad estadística para patrones de lección aprendida." })}
            </p>
            {(!metrics.data || metrics.data.length === 0) ? (
              <p className="muted" style={{ margin: "1rem 0" }}>
                {t("memory.noMetrics", { defaultValue: "No hay métricas registradas en este período." })}
              </p>
            ) : (
              <div className="data-list" style={{ marginTop: "1rem", display: "flex", flexDirection: "column", gap: "10px" }}>
                {metrics.data.map((metric) => (
                  <article key={metric.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", background: "var(--panel-raised)", borderRadius: "6px" }}>
                    <div>
                      <strong style={{ fontSize: "0.95rem" }}>
                        {metric.code} · v{metric.version}
                      </strong>
                      <br />
                      <small style={{ color: "var(--muted)" }}>{t("memory.sampleSize", { count: metric.sample_size })}</small>
                    </div>
                    <span
                      style={{
                        padding: "4px 10px",
                        borderRadius: "4px",
                        fontSize: "0.75rem",
                        fontWeight: 700,
                        background: metric.sufficient_sample ? "var(--accent)" : "var(--line)",
                        color: metric.sufficient_sample ? "#041512" : "var(--text)",
                      }}
                    >
                      {metric.sufficient_sample ? t("memory.sufficient") : t("memory.insufficient")}
                    </span>
                  </article>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </>
  );
}
