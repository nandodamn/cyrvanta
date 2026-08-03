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
    <article className="panel memory-card">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">
            {item.kind} · v{item.version}
          </p>
          <h2>{title}</h2>
        </div>
        <span className={`memory-state state-${item.status.toLowerCase()}`}>{item.status}</span>
      </div>
      <p>{statement}</p>
      <dl className="memory-facts">
        <div>
          <dt>{t("memory.source")}</dt>
          <dd>{item.source_type}</dd>
        </div>
        <div>
          <dt>{t("memory.validity")}</dt>
          <dd>
            {new Date(item.valid_from).toLocaleDateString(i18n.language)} –{" "}
            {new Date(item.valid_until).toLocaleDateString(i18n.language)}
          </dd>
        </div>
        <div>
          <dt>{t("memory.evidenceCount")}</dt>
          <dd>{item.evidence_refs.length}</dd>
        </div>
        <div>
          <dt>{t("memory.author")}</dt>
          <dd>{item.created_by_user_id.slice(0, 8)}</dd>
        </div>
      </dl>
      {item.is_synthetic && <p className="demo-badge">{t("memory.syntheticBlocked")}</p>}
      <details>
        <summary>{t("memory.history")}</summary>
        <ol className="memory-history">
          {item.state_history.map((event) => (
            <li key={event.id}>
              <strong>{event.to_status}</strong> · {event.reason} ·{" "}
              <time dateTime={event.occurred_at}>
                {new Date(event.occurred_at).toLocaleString(i18n.language)}
              </time>
            </li>
          ))}
        </ol>
      </details>
      <details>
        <summary>{t("memory.reviews", { count: item.reviews.length })}</summary>
        {item.reviews.length === 0 ? (
          <p className="muted">{t("memory.noReviews")}</p>
        ) : (
          <ul className="memory-history">
            {item.reviews.map((entry) => (
              <li key={entry.id}>
                <strong>{entry.decision}</strong> · {entry.reason}
              </li>
            ))}
          </ul>
        )}
      </details>
      {!item.is_synthetic &&
        !["REJECTED", "EXPIRED", "DISABLED", "SUPERSEDED"].includes(item.status) && (
          <div className="memory-actions">
            <label>
              {t("memory.actionReason")}
              <input
                value={reason}
                maxLength={1000}
                onChange={(event) => setReason(event.target.value)}
              />
            </label>
            <div className="form-actions">
              {item.status === "DRAFT" && (
                <button
                  disabled={busy || !reason.trim()}
                  onClick={() => transition.mutate("review-request")}
                >
                  {t("memory.requestReview")}
                </button>
              )}
              {item.status === "IN_REVIEW" && (
                <>
                  <button
                    disabled={busy || !reason.trim()}
                    onClick={() => review.mutate("APPROVE")}
                  >
                    {t("memory.approve")}
                  </button>
                  <button
                    className="ghost"
                    disabled={busy || !reason.trim()}
                    onClick={() => review.mutate("REQUEST_CHANGES")}
                  >
                    {t("memory.requestChanges")}
                  </button>
                  <button
                    className="ghost"
                    disabled={busy || !reason.trim()}
                    onClick={() => review.mutate("REJECT")}
                  >
                    {t("memory.reject")}
                  </button>
                </>
              )}
              {item.status === "APPROVED" && (
                <button
                  disabled={busy || !reason.trim()}
                  onClick={() => transition.mutate("activate")}
                >
                  {t("memory.activate")}
                </button>
              )}
              {["APPROVED", "ACTIVE"].includes(item.status) && (
                <button
                  className="ghost"
                  disabled={busy || !reason.trim()}
                  onClick={() => transition.mutate("disable")}
                >
                  {t("memory.disable")}
                </button>
              )}
            </div>
            {failed && <p className="form-error">{t("memory.separationError")}</p>}
          </div>
        )}
    </article>
  );
}

export function GovernedMemoryPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const candidates = useQuery({ queryKey: ["memory-candidates"], queryFn: getMemoryCandidates });
  const active = useQuery({ queryKey: ["memory-active"], queryFn: getActiveMemory });
  const metrics = useQuery({ queryKey: ["memory-metrics"], queryFn: getMemoryMetrics });
  const [feedback, setFeedback] = useState({
    resource_type: "INCIDENT",
    resource_id: "",
    outcome: "TRUE_POSITIVE",
    reason: "",
    is_synthetic: false,
  });
  const [candidate, setCandidate] = useState({
    kind: "CASE_NOTE",
    title_es: "",
    title_en: "",
    statement_es: "",
    statement_en: "",
    evidence_refs: "",
    valid_until: isoDaysFromNow(30),
    is_synthetic: false,
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
        title_es: candidate.title_es,
        title_en: candidate.title_en,
        statement_es: candidate.statement_es,
        statement_en: candidate.statement_en,
        conditions: {},
        evidence_refs: candidate.evidence_refs
          .split(",")
          .map((value) => value.trim())
          .filter(Boolean),
        is_synthetic: candidate.is_synthetic,
        valid_from: new Date().toISOString(),
        valid_until: new Date(candidate.valid_until).toISOString(),
      }),
    onSuccess: async () => {
      setCandidate((current) => ({
        ...current,
        title_es: "",
        title_en: "",
        statement_es: "",
        statement_en: "",
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

  return (
    <>
      <div className="page-title">
        <div>
          <p className="eyebrow">OBSERVATIONAL_ONLY</p>
          <h1>{t("memory.title")}</h1>
          <p className="muted">{t("memory.intro")}</p>
        </div>
      </div>
      <section className="panel memory-boundary">
        <h2>{t("memory.safetyTitle")}</h2>
        <p>{t("memory.safetyBody")}</p>
        <div className="metrics compact-metrics">
          <article>
            <p>{t("memory.candidates")}</p>
            <strong>{candidates.data?.length ?? 0}</strong>
          </article>
          <article>
            <p>{t("memory.active")}</p>
            <strong>{active.data?.length ?? 0}</strong>
          </article>
          <article>
            <p>{t("memory.metrics")}</p>
            <strong>{metrics.data?.length ?? 0}</strong>
          </article>
        </div>
      </section>
      <section className="memory-form-grid">
        <form className="panel" onSubmit={submitFeedback}>
          <h2>{t("memory.recordFeedback")}</h2>
          <label>
            {t("memory.resourceType")}
            <select
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
          <label>
            {t("memory.resourceId")}
            <input
              required
              value={feedback.resource_id}
              onChange={(e) => setFeedback({ ...feedback, resource_id: e.target.value })}
            />
          </label>
          <label>
            {t("memory.outcome")}
            <select
              value={feedback.outcome}
              onChange={(e) => setFeedback({ ...feedback, outcome: e.target.value })}
            >
              {OUTCOMES.map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>
          <label>
            {t("memory.reason")}
            <textarea
              required
              maxLength={1000}
              value={feedback.reason}
              onChange={(e) => setFeedback({ ...feedback, reason: e.target.value })}
            />
          </label>
          <label className="check-row">
            <input
              type="checkbox"
              checked={feedback.is_synthetic}
              onChange={(e) => setFeedback({ ...feedback, is_synthetic: e.target.checked })}
            />
            <span>{t("memory.synthetic")}</span>
          </label>
          <button disabled={feedbackMutation.isPending}>{t("memory.saveFeedback")}</button>
          {feedbackMutation.isError && <p className="form-error">{t("actionError")}</p>}
        </form>
        <form className="panel" onSubmit={submitCandidate}>
          <h2>{t("memory.proposeCandidate")}</h2>
          <label>
            {t("memory.kind")}
            <select
              value={candidate.kind}
              onChange={(e) => setCandidate({ ...candidate, kind: e.target.value })}
            >
              <option>CASE_NOTE</option>
              <option>TREND</option>
            </select>
          </label>
          <label>
            {t("memory.titleEs")}
            <input
              required
              maxLength={200}
              value={candidate.title_es}
              onChange={(e) => setCandidate({ ...candidate, title_es: e.target.value })}
            />
          </label>
          <label>
            {t("memory.titleEn")}
            <input
              required
              maxLength={200}
              value={candidate.title_en}
              onChange={(e) => setCandidate({ ...candidate, title_en: e.target.value })}
            />
          </label>
          <label>
            {t("memory.statementEs")}
            <textarea
              required
              maxLength={2000}
              value={candidate.statement_es}
              onChange={(e) => setCandidate({ ...candidate, statement_es: e.target.value })}
            />
          </label>
          <label>
            {t("memory.statementEn")}
            <textarea
              required
              maxLength={2000}
              value={candidate.statement_en}
              onChange={(e) => setCandidate({ ...candidate, statement_en: e.target.value })}
            />
          </label>
          <label>
            {t("memory.evidenceIds")}
            <input
              required
              value={candidate.evidence_refs}
              onChange={(e) => setCandidate({ ...candidate, evidence_refs: e.target.value })}
            />
          </label>
          <label>
            {t("memory.validUntil")}
            <input
              required
              type="datetime-local"
              value={candidate.valid_until}
              onChange={(e) => setCandidate({ ...candidate, valid_until: e.target.value })}
            />
          </label>
          <label className="check-row">
            <input
              type="checkbox"
              checked={candidate.is_synthetic}
              onChange={(e) => setCandidate({ ...candidate, is_synthetic: e.target.checked })}
            />
            <span>{t("memory.synthetic")}</span>
          </label>
          <button disabled={candidateMutation.isPending}>{t("memory.propose")}</button>
          {candidateMutation.isError && <p className="form-error">{t("actionError")}</p>}
        </form>
      </section>
      <section className="memory-list" aria-live="polite">
        {candidates.isLoading && <p>{t("loading")}</p>}
        {candidates.isError && <p className="form-error">{t("loadError")}</p>}
        {candidates.data?.map((item) => <MemoryCard key={item.id} item={item} />)}
      </section>
      {metrics.data && metrics.data.length > 0 && (
        <section className="panel">
          <h2>{t("memory.metrics")}</h2>
          <div className="data-list">
            {metrics.data.map((metric) => (
              <article key={metric.id}>
                <strong>
                  {metric.code} · v{metric.version}
                </strong>
                <span>{t("memory.sampleSize", { count: metric.sample_size })}</span>
                <span>
                  {metric.sufficient_sample ? t("memory.sufficient") : t("memory.insufficient")}
                </span>
              </article>
            ))}
          </div>
        </section>
      )}
    </>
  );
}
