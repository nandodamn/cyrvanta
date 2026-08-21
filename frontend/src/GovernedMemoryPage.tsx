import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  createFeedback,
  createMemoryCandidate,
  createMemoryVersion,
  getActiveMemory,
  getAlerts,
  getFeedback,
  getIncidents,
  getMemoryCandidates,
  getMemoryInfluenceEnabled,
  getMemoryMetrics,
  reviewMemoryVersion,
  transitionMemoryVersion,
  FEEDBACK_OUTCOMES,
  type FeedbackEntry,
  type MemoryCandidate,
} from "./api";
import { INCIDENT_STATUSES, SEVERITIES } from "./domain";
import { PageState } from "./PageState";

/** What this screen can offer to give feedback on.
 *
 * The two the tenant has live, listable inventories of. The backend accepts
 * feedback on claims, proposals and executions too, and those belong beside
 * the object itself rather than in a box asking someone to paste its UUID --
 * which is what this used to be, and what nobody could ever fill.
 */
const RESOURCE_TYPES = ["INCIDENT", "FINDING"] as const;

/** The facts an incident offers a memory to match on.
 *
 * A closed vocabulary rather than free key/value pairs: the incident view
 * builds its context from exactly these three fields, so a condition on
 * anything else could never match and would sit in the file looking like it
 * applied to something.
 */
const CONDITION_KEYS = ["severity", "classification", "status"] as const;

const TERMINAL = ["REJECTED", "EXPIRED", "DISABLED", "SUPERSEDED"];
const FILTERS = [
  "ALL",
  "DRAFT",
  "IN_REVIEW",
  "APPROVED",
  "ACTIVE",
  "DISABLED",
  "EXPIRED",
  "SUPERSEDED",
  "REJECTED",
] as const;

function isoDaysFromNow(days: number): string {
  return new Date(Date.now() + days * 86_400_000).toISOString().slice(0, 16);
}

/** A key that identifies the submission, not the click.
 *
 * Held until the submission succeeds so a retry after a network failure is
 * recognised as the same act. Regenerated afterwards, because the next entry
 * genuinely is a different one.
 */
function useSubmissionKey(): [string, () => void] {
  const [key, setKey] = useState(() => globalThis.crypto.randomUUID());
  return [key, () => setKey(globalThis.crypto.randomUUID())];
}

type Draft = {
  titleEs: string;
  titleEn: string;
  statementEs: string;
  statementEn: string;
  conditions: Record<string, string>;
  evidence: string[];
  validUntil: string;
};

const emptyDraft = (): Draft => ({
  titleEs: "",
  titleEn: "",
  statementEs: "",
  statementEn: "",
  conditions: {},
  evidence: [],
  validUntil: isoDaysFromNow(30),
});

function draftBody(draft: Draft) {
  return {
    title_es: draft.titleEs.trim(),
    title_en: draft.titleEn.trim() || draft.titleEs.trim(),
    statement_es: draft.statementEs.trim(),
    statement_en: draft.statementEn.trim() || draft.statementEs.trim(),
    conditions: draft.conditions,
    evidence_refs: draft.evidence,
    valid_from: new Date().toISOString(),
    valid_until: new Date(draft.validUntil).toISOString(),
  };
}

/** Pick the feedback a memory rests on, by what it is about.
 *
 * The field this replaces asked for "UUIDs separated by commas" and the screen
 * never showed a UUID anywhere, so the only way to propose a memory was to
 * read them out of the database.
 */
function EvidencePicker({
  entries,
  selected,
  onChange,
}: {
  entries: FeedbackEntry[];
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  const { t, i18n } = useTranslation();
  const toggle = (id: string) =>
    onChange(selected.includes(id) ? selected.filter((item) => item !== id) : [...selected, id]);

  if (entries.length === 0) {
    return <p className="muted small">{t("memory.evidenceEmpty")}</p>;
  }
  return (
    <ul className="evidence-picker">
      {entries.map((entry) => (
        <li key={entry.id}>
          <label>
            <input
              type="checkbox"
              checked={selected.includes(entry.id)}
              onChange={() => toggle(entry.id)}
            />
            <span>
              <strong>{t(`memory.outcomes.${entry.outcome}`)}</strong>
              <span className="evidence-target">
                {entry.resource_label ??
                  `${entry.resource_type} · ${entry.resource_id.slice(0, 8)}`}
              </span>
              <span className="evidence-meta">
                {entry.actor_name ?? t("automaticActor")} ·{" "}
                {new Date(entry.occurred_at).toLocaleDateString(i18n.language)}
              </span>
            </span>
          </label>
        </li>
      ))}
    </ul>
  );
}

/** When a memory applies. Empty means always, and says so. */
function ConditionEditor({
  value,
  classifications,
  onChange,
}: {
  value: Record<string, string>;
  classifications: string[];
  onChange: (next: Record<string, string>) => void;
}) {
  const { t } = useTranslation();
  const set = (key: string, next: string) => {
    const merged = { ...value };
    if (next) merged[key] = next;
    else delete merged[key];
    onChange(merged);
  };
  const options = (key: (typeof CONDITION_KEYS)[number]): readonly string[] =>
    key === "severity" ? SEVERITIES : key === "status" ? INCIDENT_STATUSES : [];

  return (
    <div className="condition-editor">
      {CONDITION_KEYS.map((key) => (
        <label key={key}>
          <span>{t(`memory.conditionKeys.${key}`)}</span>
          {key === "classification" ? (
            // Classification is free text in the domain and differs per tenant,
            // so the suggestions come from the classifications this tenant has
            // actually used -- while still accepting one it has not yet.
            <>
              <input
                list="memory-classifications"
                value={value[key] ?? ""}
                placeholder={t("memory.conditionAny")}
                onChange={(event) => set(key, event.target.value.trim())}
              />
              <datalist id="memory-classifications">
                {classifications.map((option) => (
                  <option key={option} value={option} />
                ))}
              </datalist>
            </>
          ) : (
            <select value={value[key] ?? ""} onChange={(event) => set(key, event.target.value)}>
              <option value="">{t("memory.conditionAny")}</option>
              {options(key).map((option) => (
                <option key={option} value={option}>
                  {key === "severity"
                    ? t(`severities.${option}`, { defaultValue: option })
                    : t(`statusCodes.${option}`, { defaultValue: option })}
                </option>
              ))}
            </select>
          )}
        </label>
      ))}
      {Object.keys(value).length === 0 && (
        // Not a warning, a statement of consequence. An unconditional memory is
        // a legitimate thing to write and it will appear on every incident.
        <p className="muted small">{t("memory.conditionNoneMeaning")}</p>
      )}
    </div>
  );
}

function MemoryCard({
  item,
  entries,
  classifications,
  canPropose,
}: {
  item: MemoryCandidate;
  entries: FeedbackEntry[];
  classifications: string[];
  canPropose: boolean;
}) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");
  const [correcting, setCorrecting] = useState(false);
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [correctionKey, rotateCorrectionKey] = useSubmissionKey();

  const refresh = async () => {
    setReason("");
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
  const correct = useMutation({
    mutationFn: () =>
      createMemoryVersion(item.id, { ...draftBody(draft), reason: reason.trim() }, correctionKey),
    onSuccess: async () => {
      rotateCorrectionKey();
      setCorrecting(false);
      setDraft(emptyDraft());
      await refresh();
    },
  });

  const spanish = i18n.language.startsWith("es");
  const title = spanish ? item.title_es : item.title_en;
  const statement = spanish ? item.statement_es : item.statement_en;
  const busy = transition.isPending || review.isPending || correct.isPending;
  const failed = transition.isError || review.isError;
  const needsReason = !reason.trim();
  const conditions = Object.entries(item.conditions);

  return (
    <article className={`panel memory-card state-${item.status.toLowerCase()}`}>
      <header className="memory-card-head">
        <div>
          <p className="eyebrow">
            {t(`memory.kinds.${item.kind}`)} · v{item.version}
          </p>
          <h3>{title}</h3>
          {item.source_type === "AI_SUGGESTED" && (
            // Marked, always. A reviewer reads a drafted sentence differently
            // knowing a machine wrote it, and they are entitled to know.
            <p className="memory-suggested">{t("memory.suggestedByAi")}</p>
          )}
        </div>
        <span className={`memory-state is-${item.status.toLowerCase()}`}>
          {t(`memory.states.${item.status}`)}
        </span>
      </header>

      <p className="memory-statement">{statement}</p>

      <dl className="memory-facts">
        <div>
          <dt>{t("memory.appliesTo")}</dt>
          <dd>
            {conditions.length === 0
              ? t("memory.conditionNone")
              : conditions
                  .map(([key, value]) => `${t(`memory.conditionKeys.${key}`)}: ${String(value)}`)
                  .join(" · ")}
          </dd>
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
          <dt>{t("memory.versionAuthor")}</dt>
          {/* No author means the AI drafted it, which is why any analyst may
              review it -- there is nobody to exclude. Said in words rather
              than shown as a blank. */}
          <dd>
            {item.version_author_name ??
              (item.source_type === "AI_SUGGESTED"
                ? t("memory.authoredByMachine")
                : t("unassigned"))}
          </dd>
        </div>
      </dl>

      <details className="memory-detail">
        <summary>
          {t("memory.history")} ({item.state_history.length})
        </summary>
        <ol className="memory-history">
          {item.state_history.map((event) => (
            <li key={event.id}>
              <strong>{t(`memory.states.${event.to_status}`)}</strong> · {event.reason} ·{" "}
              <time dateTime={event.occurred_at}>
                {new Date(event.occurred_at).toLocaleString(i18n.language)}
              </time>
            </li>
          ))}
        </ol>
      </details>

      <details className="memory-detail">
        <summary>{t("memory.reviews", { count: item.reviews.length })}</summary>
        {item.reviews.length === 0 ? (
          <p className="muted small">{t("memory.noReviews")}</p>
        ) : (
          <ul className="memory-history">
            {item.reviews.map((entry) => (
              <li key={entry.id}>
                <strong>{t(`memory.decisions.${entry.decision}`)}</strong> · {entry.reason}
              </li>
            ))}
          </ul>
        )}
      </details>

      {!TERMINAL.includes(item.status) && (
        <div className="memory-actions">
          <label>
            <span>{t("memory.actionReason")}</span>
            <input
              value={reason}
              maxLength={1000}
              placeholder={t("memory.actionReasonPlaceholder")}
              onChange={(event) => setReason(event.target.value)}
            />
          </label>
          <div className="memory-buttons">
            {item.status === "DRAFT" && (
              <button
                type="button"
                disabled={busy || needsReason}
                onClick={() => transition.mutate("review-request")}
              >
                {t("memory.requestReview")}
              </button>
            )}
            {item.status === "IN_REVIEW" && (
              <>
                <button
                  type="button"
                  disabled={busy || needsReason}
                  onClick={() => review.mutate("APPROVE")}
                >
                  {t("memory.approve")}
                </button>
                <button
                  type="button"
                  className="ghost"
                  disabled={busy || needsReason}
                  onClick={() => review.mutate("REQUEST_CHANGES")}
                >
                  {t("memory.requestChanges")}
                </button>
                <button
                  type="button"
                  className="ghost"
                  disabled={busy || needsReason}
                  onClick={() => review.mutate("REJECT")}
                >
                  {t("memory.reject")}
                </button>
              </>
            )}
            {item.status === "APPROVED" && (
              <button
                type="button"
                disabled={busy || needsReason}
                onClick={() => transition.mutate("activate")}
              >
                {t("memory.activate")}
              </button>
            )}
            {["APPROVED", "ACTIVE"].includes(item.status) && (
              <button
                type="button"
                className="ghost"
                disabled={busy || needsReason}
                onClick={() => transition.mutate("disable")}
              >
                {t("memory.disable")}
              </button>
            )}
            {canPropose && ["DRAFT", "ACTIVE"].includes(item.status) && (
              <button type="button" className="ghost" onClick={() => setCorrecting((on) => !on)}>
                {t("memory.correct")}
              </button>
            )}
          </div>
          {failed && (
            <p className="form-error" role="alert">
              {t("memory.separationError")}
            </p>
          )}
        </div>
      )}

      {correcting && (
        <form
          className="memory-correction"
          onSubmit={(event) => {
            event.preventDefault();
            correct.mutate();
          }}
        >
          {/* Nothing is edited. This writes a new version and, if the current
              one is live, retires it in the same act -- leaving it active while
              its replacement waits for review would keep showing advice the
              author has already judged wrong. */}
          <p className="muted small">{t("memory.correctIntro")}</p>
          <label>
            <span>{t("memory.candidateTitle")}</span>
            <input
              required
              maxLength={200}
              value={draft.titleEs}
              onChange={(event) => setDraft({ ...draft, titleEs: event.target.value })}
            />
          </label>
          <label>
            <span>{t("memory.statement")}</span>
            <textarea
              required
              rows={3}
              maxLength={2000}
              value={draft.statementEs}
              onChange={(event) => setDraft({ ...draft, statementEs: event.target.value })}
            />
          </label>
          <ConditionEditor
            value={draft.conditions}
            classifications={classifications}
            onChange={(conditions) => setDraft({ ...draft, conditions })}
          />
          <fieldset>
            <legend>{t("memory.evidenceIds")}</legend>
            <EvidencePicker
              entries={entries}
              selected={draft.evidence}
              onChange={(evidence) => setDraft({ ...draft, evidence })}
            />
          </fieldset>
          <label>
            <span>{t("memory.validUntil")}</span>
            <input
              required
              type="datetime-local"
              value={draft.validUntil}
              onChange={(event) => setDraft({ ...draft, validUntil: event.target.value })}
            />
          </label>
          <button
            type="submit"
            disabled={correct.isPending || draft.evidence.length === 0 || needsReason}
          >
            {t("memory.correctSubmit")}
          </button>
          {correct.isError && (
            <p className="form-error" role="alert">
              {t("memory.correctError")}
            </p>
          )}
        </form>
      )}
    </article>
  );
}

export function GovernedMemoryPage({
  permissions = new Set<string>(),
}: {
  permissions?: Set<string>;
}) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<"base" | "capture" | "governance">("base");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  const mayReadMetrics = permissions.has("memory.metrics.read");
  const mayPropose = permissions.has("memory.propose");
  const mayRecordFeedback = permissions.has("feedback.create");

  const candidates = useQuery({ queryKey: ["memory-candidates"], queryFn: getMemoryCandidates });
  const active = useQuery({ queryKey: ["memory-active"], queryFn: getActiveMemory });
  const entries = useQuery({ queryKey: ["feedback"], queryFn: getFeedback });
  const influence = useQuery({
    queryKey: ["memory-influence"],
    queryFn: getMemoryInfluenceEnabled,
    retry: false,
  });
  // The tenant's own incidents and alerts, so feedback is recorded against
  // something the analyst recognises rather than an identifier they cannot get.
  const incidents = useQuery({
    queryKey: ["incidents", "feedback-targets"],
    queryFn: () => getIncidents({ pageSize: 50 }),
    retry: false,
  });
  const alerts = useQuery({
    queryKey: ["alerts", "feedback-targets"],
    queryFn: () => getAlerts({ pageSize: 50 }),
    retry: false,
  });
  const metrics = useQuery({
    queryKey: ["memory-metrics"],
    queryFn: getMemoryMetrics,
    // Asked only of someone allowed to see them. It used to be asked of
    // everyone, and the resulting 403 was rendered as "no metrics recorded" --
    // a refusal dressed up as an absence.
    enabled: mayReadMetrics,
  });

  const [feedback, setFeedback] = useState({
    resource_type: "INCIDENT" as (typeof RESOURCE_TYPES)[number],
    resource_id: "",
    outcome: "TRUE_POSITIVE" as (typeof FEEDBACK_OUTCOMES)[number],
    reason: "",
  });
  const [feedbackKey, rotateFeedbackKey] = useSubmissionKey();
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [kind, setKind] = useState<"CASE_NOTE" | "TREND">("CASE_NOTE");
  const [candidateKey, rotateCandidateKey] = useSubmissionKey();

  const feedbackMutation = useMutation({
    mutationFn: () =>
      createFeedback({ ...feedback, occurred_at: new Date().toISOString() }, feedbackKey),
    onSuccess: async () => {
      rotateFeedbackKey();
      setFeedback((current) => ({ ...current, resource_id: "", reason: "" }));
      await queryClient.invalidateQueries({ queryKey: ["feedback"] });
    },
  });

  const candidateMutation = useMutation({
    mutationFn: () =>
      createMemoryCandidate({ kind, source_type: "HUMAN", ...draftBody(draft) }, candidateKey),
    onSuccess: async () => {
      rotateCandidateKey();
      setDraft(emptyDraft());
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

  const visible = (candidates.data ?? []).filter(
    (item) => statusFilter === "ALL" || item.status === statusFilter,
  );

  // Simulated cases are excluded here rather than refused on submit. The
  // server will not accept feedback about them -- it would contaminate the
  // metrics the whole module rests on -- and offering a choice that is going
  // to be rejected teaches people not to trust the screen.
  const resourceOptions =
    feedback.resource_type === "INCIDENT"
      ? (incidents.data ?? [])
          .filter((item) => !item.is_simulated)
          .map((item) => ({ id: item.id, label: `${item.code} · ${item.title}` }))
      : (alerts.data ?? [])
          .filter((item) => !item.is_simulated)
          .map((item) => ({ id: item.id, label: `${item.external_id} · ${item.title}` }));

  // What this tenant actually classifies incidents as, rather than a list
  // invented here that would not match anything they use.
  const classifications = [
    ...new Set(
      (incidents.data ?? [])
        .filter((item) => !item.is_simulated)
        .map((item) => item.classification)
        .filter((value): value is string => Boolean(value)),
    ),
  ].sort();

  return (
    <>
      <div className="page-title memory-title">
        <div>
          <p className="eyebrow">{t("memory.observationalOnly")}</p>
          <h1>{t("memory.title")}</h1>
          <p className="muted">{t("memory.intro")}</p>
        </div>
        <nav aria-label={t("memory.tabsLabel")} className="memory-tabs">
          {(["base", "capture", "governance"] as const).map((name) => (
            <button
              key={name}
              type="button"
              aria-current={tab === name ? "page" : undefined}
              className={tab === name ? "is-selected" : undefined}
              onClick={() => setTab(name)}
            >
              {t(`memory.tab.${name}`)}
              {name === "base" ? ` (${candidates.data?.length ?? 0})` : ""}
            </button>
          ))}
        </nav>
      </div>

      <div className="panel memory-boundary">
        <div>
          {/* What the software does, then what this installation is set to.
              These used to be one sentence, so a deployment that had turned
              influence on still read "disabled by default" -- a claim about
              the product where a reader sees a claim about their system. */}
          <strong>{t("memory.safetyTitle")}</strong>: {t("memory.safetyBody")}
          {influence.data !== undefined && (
            <span className={influence.data ? "memory-flag is-on" : "memory-flag"}>
              {influence.data ? t("memory.influenceOn") : t("memory.influenceOff")}
            </span>
          )}
        </div>
        <div className="memory-counts">
          <span>
            {t("memory.candidates")}: <strong>{candidates.data?.length ?? 0}</strong>
          </span>
          <span>
            {t("memory.active")}: <strong>{active.data?.length ?? 0}</strong>
          </span>
          <span>
            {t("memory.feedbackEntries")}: <strong>{entries.data?.length ?? 0}</strong>
          </span>
        </div>
      </div>

      {tab === "base" && (
        <>
          <div className="memory-filters">
            <span className="muted small">{t("memory.filterByState")}</span>
            {FILTERS.map((key) => (
              <button
                key={key}
                type="button"
                className={`ghost${statusFilter === key ? " is-selected" : ""}`}
                onClick={() => setStatusFilter(key)}
              >
                {key === "ALL" ? t("memory.filterAll") : t(`memory.states.${key}`)}
              </button>
            ))}
          </div>

          <PageState
            loading={candidates.isLoading}
            error={candidates.isError}
            empty={!candidates.isLoading && !candidates.isError && visible.length === 0}
          />
          <section className="memory-list" aria-live="polite">
            {visible.map((item) => (
              <MemoryCard
                key={item.id}
                item={item}
                entries={entries.data ?? []}
                classifications={classifications}
                canPropose={mayPropose}
              />
            ))}
          </section>
        </>
      )}

      {tab === "capture" && (
        <div className="memory-capture">
          <section className="panel">
            <h2>{t("memory.recordFeedback")}</h2>
            <p className="muted small">{t("memory.feedbackIntro")}</p>
            {mayRecordFeedback ? (
              <form className="form-grid" onSubmit={submitFeedback}>
                <label>
                  <span>{t("memory.resourceType")}</span>
                  <select
                    value={feedback.resource_type}
                    onChange={(event) =>
                      setFeedback({
                        ...feedback,
                        resource_type: event.target.value as (typeof RESOURCE_TYPES)[number],
                      })
                    }
                  >
                    {RESOURCE_TYPES.map((value) => (
                      <option key={value} value={value}>
                        {t(`memory.resourceTypes.${value}`)}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>{t("memory.outcome")}</span>
                  <select
                    value={feedback.outcome}
                    onChange={(event) =>
                      setFeedback({
                        ...feedback,
                        outcome: event.target.value as (typeof FEEDBACK_OUTCOMES)[number],
                      })
                    }
                  >
                    {FEEDBACK_OUTCOMES.map((value) => (
                      <option key={value} value={value}>
                        {t(`memory.outcomes.${value}`)}
                      </option>
                    ))}
                  </select>
                </label>
                <label style={{ gridColumn: "1 / -1" }}>
                  <span>{t("memory.resourceId")}</span>
                  {/* Chosen from what the tenant actually has. The field this
                      replaces asked for a UUID, and no screen in the product
                      shows one, so the only way to fill it was a database. */}
                  <select
                    required
                    value={feedback.resource_id}
                    onChange={(event) =>
                      setFeedback({ ...feedback, resource_id: event.target.value })
                    }
                  >
                    <option value="">{t("memory.resourcePick")}</option>
                    {resourceOptions.map((option) => (
                      <option key={option.id} value={option.id}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                {resourceOptions.length === 0 && (
                  <p className="muted small" style={{ gridColumn: "1 / -1" }}>
                    {t("memory.resourceEmpty")}
                  </p>
                )}
                <label style={{ gridColumn: "1 / -1" }}>
                  <span>{t("memory.reason")}</span>
                  <textarea
                    required
                    rows={3}
                    maxLength={1000}
                    value={feedback.reason}
                    placeholder={t("memory.reasonPlaceholder")}
                    onChange={(event) => setFeedback({ ...feedback, reason: event.target.value })}
                  />
                </label>
                <button type="submit" disabled={feedbackMutation.isPending}>
                  {t("memory.saveFeedback")}
                </button>
                {feedbackMutation.isError && (
                  <p className="form-error" role="alert">
                    {t("memory.feedbackError")}
                  </p>
                )}
              </form>
            ) : (
              <p className="muted small">{t("memory.feedbackNotPermitted")}</p>
            )}

            <h3>{t("memory.feedbackLedger")}</h3>
            <p className="muted small">{t("memory.feedbackLedgerIntro")}</p>
            <PageState
              loading={entries.isLoading}
              error={entries.isError}
              empty={!entries.isLoading && !entries.isError && (entries.data?.length ?? 0) === 0}
            />
            <ul className="feedback-list">
              {(entries.data ?? []).map((entry) => (
                <li key={entry.id}>
                  <div>
                    <strong>{t(`memory.outcomes.${entry.outcome}`)}</strong>
                    <span className="evidence-target">
                      {entry.resource_label ??
                        `${entry.resource_type} · ${entry.resource_id.slice(0, 8)}`}
                    </span>
                  </div>
                  <p>{entry.reason}</p>
                  <span className="evidence-meta">
                    {entry.actor_name ?? t("automaticActor")} ·{" "}
                    {new Date(entry.occurred_at).toLocaleString(i18n.language)}
                  </span>
                </li>
              ))}
            </ul>
          </section>

          <section className="panel">
            <h2>{t("memory.proposeCandidate")}</h2>
            <p className="muted small">{t("memory.candidateIntro")}</p>
            {mayPropose ? (
              <form className="form-grid" onSubmit={submitCandidate}>
                <label>
                  <span>{t("memory.kind")}</span>
                  <select
                    value={kind}
                    onChange={(event) => setKind(event.target.value as "CASE_NOTE" | "TREND")}
                  >
                    <option value="CASE_NOTE">{t("memory.kinds.CASE_NOTE")}</option>
                    <option value="TREND">{t("memory.kinds.TREND")}</option>
                  </select>
                </label>
                <label>
                  <span>{t("memory.validUntil")}</span>
                  <input
                    required
                    type="datetime-local"
                    value={draft.validUntil}
                    onChange={(event) => setDraft({ ...draft, validUntil: event.target.value })}
                  />
                </label>
                <label style={{ gridColumn: "1 / -1" }}>
                  <span>{t("memory.candidateTitle")}</span>
                  <input
                    required
                    maxLength={200}
                    value={draft.titleEs}
                    placeholder={t("memory.candidateTitlePlaceholder")}
                    onChange={(event) => setDraft({ ...draft, titleEs: event.target.value })}
                  />
                </label>
                <label style={{ gridColumn: "1 / -1" }}>
                  <span>{t("memory.statement")}</span>
                  <textarea
                    required
                    rows={3}
                    maxLength={2000}
                    value={draft.statementEs}
                    placeholder={t("memory.statementPlaceholder")}
                    onChange={(event) => setDraft({ ...draft, statementEs: event.target.value })}
                  />
                </label>
                {/* The other language, offered and not demanded. Copying the
                    same text into both columns -- which is what this form used
                    to do silently -- puts a Spanish sentence in the English
                    field and calls the result bilingual. */}
                <details style={{ gridColumn: "1 / -1" }}>
                  <summary>{t("memory.otherLanguage")}</summary>
                  <label>
                    <span>{t("memory.candidateTitleEn")}</span>
                    <input
                      maxLength={200}
                      value={draft.titleEn}
                      onChange={(event) => setDraft({ ...draft, titleEn: event.target.value })}
                    />
                  </label>
                  <label>
                    <span>{t("memory.statementEn")}</span>
                    <textarea
                      rows={3}
                      maxLength={2000}
                      value={draft.statementEn}
                      onChange={(event) => setDraft({ ...draft, statementEn: event.target.value })}
                    />
                  </label>
                </details>
                <fieldset style={{ gridColumn: "1 / -1" }}>
                  <legend>{t("memory.appliesTo")}</legend>
                  <ConditionEditor
                    value={draft.conditions}
                    classifications={classifications}
                    onChange={(conditions) => setDraft({ ...draft, conditions })}
                  />
                </fieldset>
                <fieldset style={{ gridColumn: "1 / -1" }}>
                  <legend>{t("memory.evidenceIds")}</legend>
                  {kind === "TREND" && <p className="muted small">{t("memory.trendSample")}</p>}
                  <EvidencePicker
                    entries={entries.data ?? []}
                    selected={draft.evidence}
                    onChange={(evidence) => setDraft({ ...draft, evidence })}
                  />
                </fieldset>
                <button
                  type="submit"
                  disabled={candidateMutation.isPending || draft.evidence.length === 0}
                >
                  {t("memory.propose")}
                </button>
                {candidateMutation.isError && (
                  <p className="form-error" role="alert">
                    {t("memory.candidateError")}
                  </p>
                )}
              </form>
            ) : (
              <p className="muted small">{t("memory.proposeNotPermitted")}</p>
            )}
          </section>
        </div>
      )}

      {tab === "governance" && (
        <section className="panel">
          <h2>{t("memory.metrics")}</h2>
          <p className="muted small">{t("memory.metricsIntro")}</p>
          {!mayReadMetrics ? (
            // Said plainly. Rendering this as "no metrics recorded" told every
            // analyst the SOC had measured nothing.
            <p className="muted small">{t("memory.metricsNotPermitted")}</p>
          ) : (
            <>
              <PageState
                loading={metrics.isLoading}
                error={metrics.isError}
                empty={!metrics.isLoading && !metrics.isError && (metrics.data?.length ?? 0) === 0}
              />
              <ul className="metric-list">
                {(metrics.data ?? []).map((metric) => (
                  <li key={metric.id}>
                    <div>
                      <strong>{t(`memory.metricCodes.${metric.code}`)}</strong>
                      <span className="evidence-meta">
                        {t("memory.metricWindow", {
                          from: new Date(metric.window_start).toLocaleDateString(i18n.language),
                          to: new Date(metric.window_end).toLocaleDateString(i18n.language),
                        })}{" "}
                        · {t("memory.sampleSize", { count: metric.sample_size })} ·{" "}
                        {t("memory.definitionVersion", { version: metric.version })}
                      </span>
                    </div>
                    <div className="metric-value">
                      <strong>{(metric.value * 100).toFixed(1)}%</strong>
                      <span className={metric.sufficient_sample ? "is-sufficient" : "is-thin"}>
                        {metric.sufficient_sample
                          ? t("memory.sufficient")
                          : t("memory.insufficient")}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}
    </>
  );
}
