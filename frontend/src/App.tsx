import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { NavLink, Navigate, Outlet, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { z } from "zod";

import {
  createRole,
  createUser,
  createDemoResponseProposal,
  analyzeIncident,
  directoryLogin,
  downloadIncidentReport,
  generateCanonicalDemoScenario,
  generateIncidentExplanation,
  getAlerts,
  getAuditEvents,
  getClaims,
  getCorrelations,
  getDirectoryConfiguration,
  getIncident,
  getIncidentEnrichment,
  getIncidents,
  getIntegrationHealth,
  getMe,
  getPermissions,
  getPlaybookManagement,
  getPlaybooks,
  getRolePermissions,
  getResponseDecisions,
  getRoles,
  getTenant,
  getTimeline,
  getUserRoles,
  getUsers,
  login,
  recalculateIncidentRisk,
  replaceRolePermissions,
  replaceUserRoles,
  saveDirectoryConfiguration,
  testDirectoryConfiguration,
  transitionIncident,
} from "./api";
import { useAuth } from "./AuthContext";

const NAV_ITEMS: ReadonlyArray<{ to: string; icon: string; key: string; end?: boolean }> = [
  { to: "/", icon: "RE", key: "overview", end: true },
  { to: "/incidents", icon: "IN", key: "incidents" },
  { to: "/alerts", icon: "AL", key: "alerts" },
  { to: "/playbooks", icon: "PB", key: "playbooks" },
  { to: "/integrations", icon: "IG", key: "integrations" },
  { to: "/audit", icon: "AU", key: "audit" },
  { to: "/administration", icon: "AD", key: "administration" },
];

const loginSchema = z.object({
  tenantSlug: z.string().min(3),
  email: z.string().min(1),
  password: z.string().min(8),
  rememberMe: z.boolean(),
});
type LoginInput = z.infer<typeof loginSchema>;

function LoginPage() {
  const { t } = useTranslation();
  const auth = useAuth();
  const navigate = useNavigate();
  const [authMode, setAuthMode] = useState<"local" | "directory">("local");
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<LoginInput>({
    resolver: zodResolver(loginSchema),
    defaultValues: { rememberMe: false },
  });
  if (!auth.ready) return <main className="login-shell">{t("loading")}</main>;
  if (auth.authenticated) return <Navigate to="/" replace />;
  const submit = handleSubmit(async (values) => {
    try {
      if (authMode === "directory") {
        await directoryLogin(values.tenantSlug, values.email, values.password, values.rememberMe);
      } else {
        await login(values.tenantSlug, values.email, values.password, values.rememberMe);
      }
      auth.activate();
      navigate("/");
    } catch {
      setError("root", { message: t("error") });
    }
  });
  return (
    <main className="login-shell">
      <section className="login-brand">
        <img
          className="brand-mark"
          src="/cyrvanta-logo.png"
          alt={t("product")}
          width="96"
          height="96"
        />
        <p className="eyebrow">{t("securityOperations")}</p>
        <h1>{t("product")}</h1>
        <p>{t("welcome")}</p>
      </section>
      <form className="login-card" onSubmit={submit}>
        <h2>{t("signIn")}</h2>
        <div className="auth-tabs">
          <button
            type="button"
            className={authMode === "local" ? "" : "ghost"}
            onClick={() => setAuthMode("local")}
          >
            {t("localAccess")}
          </button>
          <button
            type="button"
            className={authMode === "directory" ? "" : "ghost"}
            onClick={() => setAuthMode("directory")}
          >
            LDAP / AD
          </button>
        </div>
        <label>
          {t("tenant")}
          <input autoComplete="organization" {...register("tenantSlug")} />
        </label>
        <label>
          {authMode === "local" ? t("email") : t("directoryUsername")}
          <input
            type={authMode === "local" ? "email" : "text"}
            autoComplete="username"
            {...register("email")}
          />
        </label>
        <label>
          {t("password")}
          <input type="password" autoComplete="current-password" {...register("password")} />
        </label>
        <label className="check-row">
          <input type="checkbox" {...register("rememberMe")} />
          <span>{t("rememberSession")}</span>
        </label>
        {(errors.email || errors.password || errors.root) && (
          <p className="form-error">{errors.root?.message ?? t("error")}</p>
        )}
        <button disabled={isSubmitting}>{isSubmitting ? t("loading") : t("signIn")}</button>
      </form>
    </main>
  );
}

function ProtectedRoute() {
  const auth = useAuth();
  if (!auth.ready) return null;
  return auth.authenticated ? <Outlet /> : <Navigate to="/login" replace />;
}

function Layout() {
  const { t, i18n } = useTranslation();
  const auth = useAuth();
  const signOut = auth.signOut;
  const [lightTheme, setLightTheme] = useState(() => sessionStorage.getItem("theme") === "light");
  const me = useQuery({ queryKey: ["me"], queryFn: getMe, retry: false });
  useEffect(() => {
    if (me.isError) void signOut();
  }, [me.isError, signOut]);
  useEffect(() => {
    document.documentElement.classList.toggle("light", lightTheme);
  }, [lightTheme]);
  const toggleTheme = () => {
    const next = !lightTheme;
    sessionStorage.setItem("theme", next ? "light" : "dark");
    setLightTheme(next);
  };
  const setLanguage = (language: string) => {
    sessionStorage.setItem("locale", language);
    void i18n.changeLanguage(language);
  };
  return (
    <div className="app-shell">
      <aside aria-label={t("primaryNavigation")}>
        <div className="brand">
          <img src="/cyrvanta-logo-192.png" alt="" width="40" height="40" />
          <strong>Cyrvanta</strong>
        </div>
        <nav aria-label={t("primaryNavigation")}>
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} title={t(item.key)}>
              <span className="nav-icon" aria-hidden="true">
                {item.icon}
              </span>
              <span className="nav-label">{t(item.key)}</span>
            </NavLink>
          ))}
        </nav>
        <p className="tenant-code">TENANT · {me.data?.tenant_id.slice(0, 8) ?? "—"}</p>
      </aside>
      <section className="workspace">
        <header>
          <div className="header-identity">
            <img
              className="mobile-logo"
              src="/cyrvanta-logo-192.png"
              alt=""
              width="42"
              height="42"
            />
            <div>
              <p className="eyebrow">{t("securityOperations")}</p>
              <strong>{me.data?.display_name ?? t("loading")}</strong>
            </div>
          </div>
          <div className="actions">
            <select
              aria-label={t("language")}
              value={i18n.language.slice(0, 2)}
              onChange={(e) => setLanguage(e.target.value)}
            >
              <option value="es">ES</option>
              <option value="en">EN</option>
            </select>
            <button className="ghost" type="button" aria-pressed={lightTheme} onClick={toggleTheme}>
              {lightTheme ? t("darkTheme") : t("lightTheme")}
            </button>
            <button className="ghost" type="button" onClick={() => void signOut()}>
              {t("signOut")}
            </button>
          </div>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </section>
    </div>
  );
}

function PageState({
  loading,
  error,
  empty,
}: {
  loading: boolean;
  error: boolean;
  empty: boolean;
}) {
  const { t } = useTranslation();
  if (loading)
    return (
      <p className="status-message" role="status">
        {t("loading")}
      </p>
    );
  if (error)
    return (
      <p className="status-message status-error" role="alert">
        {t("loadError")}
      </p>
    );
  if (empty) return <p className="status-message">{t("emptyState")}</p>;
  return null;
}

function useListControls(defaultPageSize = 10) {
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(defaultPageSize);
  return {
    draft,
    query,
    page,
    pageSize,
    setDraft,
    setPage,
    setPageSize: (size: number) => {
      setPage(0);
      setPageSize(size);
    },
    applySearch: () => {
      setPage(0);
      setQuery(draft.trim());
    },
  };
}

function ListControls({
  state,
  visibleCount,
  hasNext,
}: {
  state: ReturnType<typeof useListControls>;
  visibleCount: number;
  hasNext: boolean;
}) {
  const { t } = useTranslation();
  return (
    <form
      className="list-controls"
      role="search"
      onSubmit={(event) => {
        event.preventDefault();
        state.applySearch();
      }}
    >
      <label>
        <span>{t("search")}</span>
        <input
          type="search"
          maxLength={100}
          value={state.draft}
          placeholder={t("searchPlaceholder")}
          onChange={(event) => state.setDraft(event.target.value)}
        />
      </label>
      <button type="submit">{t("search")}</button>
      <label>
        <span>{t("itemsPerPage")}</span>
        <select
          value={state.pageSize}
          onChange={(event) => state.setPageSize(Number(event.target.value))}
        >
          {[10, 25, 50].map((size) => (
            <option key={size} value={size}>
              {size}
            </option>
          ))}
        </select>
      </label>
      <span className="list-result-count">
        {t("visibleResults", { count: visibleCount, page: state.page + 1 })}
      </span>
      <div className="pager">
        <button
          type="button"
          className="ghost"
          disabled={state.page === 0}
          onClick={() => state.setPage(Math.max(0, state.page - 1))}
        >
          {t("previous")}
        </button>
        <button
          type="button"
          className="ghost"
          disabled={!hasNext}
          onClick={() => state.setPage(state.page + 1)}
        >
          {t("next")}
        </button>
      </div>
    </form>
  );
}

function Overview() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const incidents = useQuery({
    queryKey: ["incidents", "overview"],
    queryFn: () => getIncidents({ pageSize: 100 }),
  });
  const alerts = useQuery({
    queryKey: ["alerts", "overview"],
    queryFn: () => getAlerts({ pageSize: 100 }),
  });
  const demo = useMutation({
    mutationFn: generateCanonicalDemoScenario,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["incidents"] }),
        queryClient.invalidateQueries({ queryKey: ["alerts"] }),
      ]);
      window.setTimeout(() => {
        void queryClient.invalidateQueries({ queryKey: ["incidents"] });
        void queryClient.invalidateQueries({ queryKey: ["alerts"] });
      }, 2500);
    },
  });
  const open = incidents.data?.filter((item) => item.status !== "closed") ?? [];
  const cards = [
    [t("openIncidents"), String(open.length)],
    [t("critical"), String(open.filter((item) => item.severity === "critical").length)],
    [t("pendingReview"), String(open.filter((item) => item.status === "new").length)],
    [t("alerts"), String(alerts.data?.length ?? 0)],
  ];
  return (
    <>
      <div className="page-title">
        <div>
          <p className="eyebrow">SOC / 24H</p>
          <h1>{t("overview")}</h1>
        </div>
        <button disabled={demo.isPending} onClick={() => demo.mutate()}>
          {demo.isPending ? t("loading") : t("runCanonicalDemo")}
        </button>
      </div>
      <section className="metrics">
        {cards.map(([label, value]) => (
          <article key={label}>
            <p>{label}</p>
            <strong>{value}</strong>
            <span className="spark">╱╲╱╲╱</span>
          </article>
        ))}
      </section>
      <PageState
        loading={incidents.isLoading || alerts.isLoading}
        error={incidents.isError || alerts.isError}
        empty={false}
      />
      <section className="overview-visuals">
        <article className="panel pulse-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">{t("operationalPulse")}</p>
              <h2>{t("operationalPulseTitle")}</h2>
            </div>
            <span className="preview-badge">{t("staticPreview")}</span>
          </div>
          <div className="signal-grid" role="img" aria-label={t("operationalPulsePreview")}>
            {[64, 42, 78, 55, 88, 70, 49, 81, 61, 75, 92, 68].map((v, i) => (
              <i key={i} style={{ height: `${v}%` }} />
            ))}
          </div>
          <div className="pulse-legend">
            <span>{t("telemetryIngestion")}</span>
            <span>{t("detections")}</span>
            <span>{t("incidentResponse")}</span>
          </div>
        </article>

        <article className="panel topology-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">{t("monitoredEnvironment")}</p>
              <h2>{t("securityTopology")}</h2>
            </div>
            <span className="preview-badge">{t("staticPreview")}</span>
          </div>
          <div className="topology-path" aria-label={t("securityTopology")}>
            <div className="topology-node endpoint">
              <span>01</span>
              <strong>Windows</strong>
              <small>Wazuh Agent</small>
            </div>
            <span className="topology-arrow" aria-hidden="true">
              →
            </span>
            <div className="topology-node detection">
              <span>02</span>
              <strong>Wazuh Manager</strong>
              <small>{t("detectionEngine")}</small>
            </div>
            <span className="topology-arrow" aria-hidden="true">
              →
            </span>
            <div className="topology-node evidence">
              <span>03</span>
              <strong>OpenSearch</strong>
              <small>{t("evidenceSearch")}</small>
            </div>
            <span className="topology-arrow" aria-hidden="true">
              →
            </span>
            <div className="topology-node platform">
              <span>04</span>
              <strong>Cyrvanta</strong>
              <small>{t("correlationAndAudit")}</small>
            </div>
          </div>
          <div className="topology-services">
            <div>
              <strong>Ollama · Gemma 4</strong>
              <small>{t("assistedAnalysis")}</small>
            </div>
            <div>
              <strong>n8n</strong>
              <small>{t("approvedAutomation")}</small>
            </div>
            <div>
              <strong>PostgreSQL</strong>
              <small>{t("traceableHistory")}</small>
            </div>
          </div>
        </article>
      </section>
      {demo.data && (
        <p className="demo-badge">
          {demo.data.correlation_queued ? t("canonicalDemoQueued") : t("canonicalDemoReplay")}
        </p>
      )}
    </>
  );
}

function AlertsPage() {
  const { t, i18n } = useTranslation();
  const controls = useListControls();
  const alerts = useQuery({
    queryKey: ["alerts", controls.query, controls.page, controls.pageSize],
    queryFn: () =>
      getAlerts({
        query: controls.query,
        page: controls.page,
        pageSize: controls.pageSize,
        includeLookahead: true,
      }),
  });
  const items = alerts.data?.slice(0, controls.pageSize) ?? [];
  return (
    <>
      <div className="page-title">
        <h1>{t("alerts")}</h1>
      </div>
      <PageState
        loading={alerts.isLoading}
        error={alerts.isError}
        empty={!alerts.isLoading && !alerts.isError && items.length === 0}
      />
      <section className="panel table-panel">
        <ListControls
          state={controls}
          visibleCount={items.length}
          hasNext={(alerts.data?.length ?? 0) > controls.pageSize}
        />
        <div className="data-list">
          {items.map((alert) => (
            <article key={alert.id}>
              <span className={`severity ${alert.severity}`}>
                {t(`severityCodes.${alert.severity}`, { defaultValue: alert.severity })}
              </span>
              <div>
                <strong>{alert.title}</strong>
                <small>
                  {alert.source} · {alert.category}
                </small>
              </div>
              {alert.is_simulated && <span className="demo-badge">{t("simulated")}</span>}
              <time dateTime={alert.observed_at}>
                {new Date(alert.observed_at).toLocaleString(i18n.language)}
              </time>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}

function IncidentsPage() {
  const { t } = useTranslation();
  const controls = useListControls();
  const incidents = useQuery({
    queryKey: ["incidents", controls.query, controls.page, controls.pageSize],
    queryFn: () =>
      getIncidents({
        query: controls.query,
        page: controls.page,
        pageSize: controls.pageSize,
        includeLookahead: true,
      }),
  });
  const items = incidents.data?.slice(0, controls.pageSize) ?? [];
  return (
    <>
      <div className="page-title">
        <h1>{t("incidents")}</h1>
      </div>
      <PageState
        loading={incidents.isLoading}
        error={incidents.isError}
        empty={!incidents.isLoading && !incidents.isError && items.length === 0}
      />
      <section className="panel table-panel">
        <ListControls
          state={controls}
          visibleCount={items.length}
          hasNext={(incidents.data?.length ?? 0) > controls.pageSize}
        />
        <div className="data-list">
          {items.map((incident) => (
            <NavLink to={`/incidents/${incident.id}`} key={incident.id}>
              <span className={`severity ${incident.severity}`}>
                {t(`severityCodes.${incident.severity}`, { defaultValue: incident.severity })}
              </span>
              <div>
                <strong>
                  {incident.code} · {incident.title}
                </strong>
                <small>{incident.classification}</small>
              </div>
              <span>{t(`statusCodes.${incident.status}`, { defaultValue: incident.status })}</span>
              {incident.is_simulated && <span className="demo-badge">{t("simulated")}</span>}
            </NavLink>
          ))}
        </div>
      </section>
    </>
  );
}

function IncidentDetailPage() {
  const { id = "" } = useParams();
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const incident = useQuery({ queryKey: ["incident", id], queryFn: () => getIncident(id) });
  const timeline = useQuery({ queryKey: ["timeline", id], queryFn: () => getTimeline(id) });
  const claims = useQuery({ queryKey: ["claims", id], queryFn: () => getClaims(id) });
  const correlations = useQuery({
    queryKey: ["correlations", id],
    queryFn: () => getCorrelations(id),
  });
  const enrichment = useQuery({
    queryKey: ["enrichment", id],
    queryFn: () => getIncidentEnrichment(id),
    retry: false,
  });
  const responseDecisions = useQuery({
    queryKey: ["response-decisions", id],
    queryFn: () => getResponseDecisions(id),
    retry: false,
  });
  const transition = useMutation({
    mutationFn: (target: string) => transitionIncident(id, incident.data!.version, target),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["incident", id] }),
        queryClient.invalidateQueries({ queryKey: ["incidents"] }),
        queryClient.invalidateQueries({ queryKey: ["timeline", id] }),
      ]);
    },
  });
  const analysis = useMutation({
    mutationFn: () => analyzeIncident(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["claims", id] });
    },
  });
  const recalculateRisk = useMutation({
    mutationFn: () => recalculateIncidentRisk(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["enrichment", id] });
    },
  });
  const generateExplanation = useMutation({
    mutationFn: () => generateIncidentExplanation(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["enrichment", id] });
    },
  });
  const responseProposal = useMutation({
    mutationFn: () => createDemoResponseProposal(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["response-decisions", id] });
    },
  });
  const next: Record<string, string> = {
    new: "triaged",
    triaged: "investigating",
    investigating: "contained",
    contained: "resolved",
    resolved: "closed",
    closed: "reopened",
    reopened: "investigating",
  };
  if (incident.isLoading) return <PageState loading error={false} empty={false} />;
  if (incident.isError || !incident.data) {
    return <PageState loading={false} error empty={false} />;
  }
  return (
    <>
      <div className="page-title">
        <div>
          <p className="eyebrow">{incident.data.code}</p>
          <h1>{incident.data.title}</h1>
        </div>
        {incident.data.is_simulated && <span className="demo-badge">{t("simulated")}</span>}
      </div>
      <section className="metrics">
        <article>
          <p>{t("status")}</p>
          <strong className="metric-text">
            {t(`statusCodes.${incident.data.status}`, { defaultValue: incident.data.status })}
          </strong>
        </article>
        <article>
          <p>{t("severity")}</p>
          <strong className="metric-text">
            {t(`severityCodes.${incident.data.severity}`, { defaultValue: incident.data.severity })}
          </strong>
        </article>
        <article>
          <p>{t("priority")}</p>
          <strong>{incident.data.priority}</strong>
        </article>
        <article>
          <p>{t("version")}</p>
          <strong>{incident.data.version}</strong>
        </article>
      </section>
      <section className="panel">
        <div>
          <h2>{t("timeline")}</h2>
          <p>{incident.data.description}</p>
        </div>
        <div className="timeline">
          {timeline.data?.map((entry) => (
            <p key={entry.id}>
              <strong>{entry.entry_type}</strong>
              <br />
              {entry.summary}
            </p>
          ))}
          <PageState
            loading={timeline.isLoading}
            error={timeline.isError}
            empty={!timeline.isLoading && !timeline.isError && timeline.data?.length === 0}
          />
          <button
            disabled={transition.isPending}
            onClick={() => transition.mutate(next[incident.data!.status])}
          >
            {t("advanceTo")}{" "}
            {t(`statusCodes.${next[incident.data.status]}`, {
              defaultValue: next[incident.data.status],
            })}
          </button>
          <button className="ghost" disabled={analysis.isPending} onClick={() => analysis.mutate()}>
            {t("analyze")}
          </button>
          <button
            className="ghost"
            disabled={responseProposal.isPending}
            onClick={() => responseProposal.mutate()}
          >
            {t("proposeSafeResponse")}
          </button>
          <button
            className="ghost"
            onClick={() => void downloadIncidentReport(id, incident.data!.code)}
          >
            {t("downloadReport")}
          </button>
          {analysis.data && (
            <div className="analysis-card">
              <strong>
                {t("risk")}: {analysis.data.risk_score}/100
              </strong>
              <p>
                {i18n.language.startsWith("es")
                  ? analysis.data.summary_es
                  : analysis.data.summary_en}
              </p>
              <small>{analysis.data.techniques.map((item) => item.external_id).join(" · ")}</small>
            </div>
          )}
          {responseProposal.data && <p className="demo-badge">{t("proposalCreated")}</p>}
          {(transition.isError || analysis.isError || responseProposal.isError) && (
            <p className="status-message status-error" role="alert">
              {t("actionError")}
            </p>
          )}
        </div>
      </section>
      <section className="panel claim-panel">
        <div>
          <p className="eyebrow">{t("safeResponse")}</p>
          <h2>{t("decisionsAndApprovals")}</h2>
          <p>{t("decisionsIntro")}</p>
        </div>
        <div className="claim-grid">
          {responseDecisions.data?.map((decision) => (
            <article className="claim-card" key={decision.id}>
              <div className="claim-badges">
                <span>{decision.status}</span>
                <span>{decision.impact}</span>
                {decision.is_simulated && <span>{t("simulated")}</span>}
              </div>
              <strong>{decision.action_type}</strong>
              <p>
                {t("approvalProgress")}: {decision.decisions.length}/{decision.required_approvals}
              </p>
              <small>
                {t("policyOutcome")}: {decision.evaluation_outcome}
              </small>
              <br />
              <small>{decision.reason_codes.join(" · ")}</small>
            </article>
          ))}
          <PageState
            loading={responseDecisions.isLoading}
            error={responseDecisions.isError}
            empty={
              !responseDecisions.isLoading &&
              !responseDecisions.isError &&
              responseDecisions.data?.length === 0
            }
          />
        </div>
      </section>
      <section className="panel claim-panel">
        <div>
          <p className="eyebrow">MITRE ATT&amp;CK</p>
          <h2>{t("threatEnrichment")}</h2>
          <p>{t("threatEnrichmentIntro")}</p>
          <button
            className="ghost"
            disabled={recalculateRisk.isPending}
            onClick={() => recalculateRisk.mutate()}
          >
            {t("recalculateRisk")}
          </button>
          <button
            className="ghost"
            disabled={generateExplanation.isPending || !enrichment.data}
            onClick={() => generateExplanation.mutate()}
          >
            {t("redactWithAi")}
          </button>
        </div>
        <div className="claim-grid">
          {enrichment.data && (
            <>
              <article className="claim-card analysis-card">
                <div className="claim-badges">
                  <span>
                    {t("riskDefinition")} {enrichment.data.risk.definition_code} v
                    {enrichment.data.risk.definition_version}
                  </span>
                  <span>
                    {t(`riskBands.${enrichment.data.risk.band}`, {
                      defaultValue: enrichment.data.risk.band,
                    })}
                  </span>
                </div>
                <strong>
                  {t("risk")}: {enrichment.data.risk.score}/100
                </strong>
                <div className="correlation-factors">
                  {enrichment.data.risk.factors.map((factor) => (
                    <span key={factor.code}>
                      {t(`riskFactors.${factor.code}`, { defaultValue: factor.code })}:{" "}
                      {factor.contribution}/{factor.weight}
                    </span>
                  ))}
                </div>
                <p>
                  {enrichment.data.explanations.find(
                    (item) =>
                      item.locale === (i18n.language.startsWith("es") ? "es" : "en") &&
                      item.mode === "AI_REDACTION",
                  )?.text ??
                    enrichment.data.explanations.find(
                      (item) =>
                        item.locale === (i18n.language.startsWith("es") ? "es" : "en") &&
                        item.mode === "DETERMINISTIC",
                    )?.text}
                </p>
              </article>
              {enrichment.data.mappings.map((mapping) => (
                <article className="claim-card" key={mapping.id}>
                  <div className="claim-badges">
                    <span>{mapping.status}</span>
                    <span>{mapping.external_id}</span>
                  </div>
                  <strong>{mapping.name_en}</strong>
                  <p>{mapping.tactic_codes.join(" · ")}</p>
                  <small>
                    {t("evidence")}: {mapping.evidence_revision_ids.length} ·{" "}
                    {mapping.selector_codes.join(", ")}
                  </small>
                </article>
              ))}
            </>
          )}
          <PageState
            loading={enrichment.isLoading || recalculateRisk.isPending}
            error={recalculateRisk.isError || generateExplanation.isError}
            empty={!enrichment.isLoading && !enrichment.data}
          />
        </div>
      </section>
      <section className="panel claim-panel">
        <div>
          <p className="eyebrow">{t("traceability")}</p>
          <h2>{t("knowledgeClaims")}</h2>
          <p>{t("knowledgeClaimsIntro")}</p>
        </div>
        <div className="claim-grid">
          {claims.data?.map((claim) => {
            const locale = i18n.language.startsWith("es") ? "es" : "en";
            const statement =
              claim.presentations[locale] ??
              (claim.language_code === locale ? claim.statement : undefined) ??
              claim.presentations.en ??
              claim.presentations.es ??
              claim.statement;
            return (
              <article className="claim-card" key={claim.id}>
                <div className="claim-badges">
                  <span>
                    {t(`claimTypes.${claim.claim_type}`, { defaultValue: claim.claim_type })}
                  </span>
                  <span>{t(`claimStates.${claim.state}`, { defaultValue: claim.state })}</span>
                  <span>
                    {t(`claimOrigins.${claim.origin_type}`, { defaultValue: claim.origin_type })}
                  </span>
                  {claim.is_simulated && <span>{t("simulated")}</span>}
                </div>
                <p>{statement}</p>
                {claim.confidence !== null && (
                  <small>
                    {t("confidence")}: {Math.round(claim.confidence * 100)}%
                  </small>
                )}
              </article>
            );
          })}
          <PageState
            loading={claims.isLoading}
            error={claims.isError}
            empty={!claims.isLoading && !claims.isError && claims.data?.length === 0}
          />
        </div>
      </section>
      <section className="panel claim-panel">
        <div>
          <p className="eyebrow">{t("traceability")}</p>
          <h2>{t("correlations")}</h2>
          <p>{t("correlationIntro")}</p>
        </div>
        <div className="claim-grid">
          {correlations.data?.map((match) => (
            <article className="claim-card correlation-card" key={match.id}>
              <div className="claim-badges">
                <span>
                  {t("rule")}: {match.rule_code} v{match.rule_version}
                </span>
                <span>{match.result_type}</span>
                {match.is_simulated && <span>{t("simulated")}</span>}
              </div>
              <strong>
                {t("correlationScore")}: {match.score}/100 · {t("threshold")}: {match.threshold}
              </strong>
              <p>
                {t("members")}: {match.members.length}
              </p>
              {match.result_type === "LEGACY_SIMULATED_V0" && (
                <small>{t("legacyCorrelation")}</small>
              )}
              <div className="correlation-factors">
                {match.factors.map((factor) => (
                  <span key={factor.factor_code}>
                    {t(`correlationFactors.${factor.factor_code}`, {
                      defaultValue: factor.factor_code,
                    })}
                    : {factor.contribution}/{factor.weight}
                  </span>
                ))}
              </div>
            </article>
          ))}
          <PageState
            loading={correlations.isLoading}
            error={correlations.isError}
            empty={
              !correlations.isLoading && !correlations.isError && correlations.data?.length === 0
            }
          />
        </div>
      </section>
    </>
  );
}

function IntegrationsPage() {
  const { t } = useTranslation();
  const health = useQuery({ queryKey: ["integration-health"], queryFn: getIntegrationHealth });
  const wazuh = health.data?.find((item) => item.code === "wazuh");
  const platformServices = health.data?.filter((item) => item.code !== "wazuh") ?? [];
  const plannedConnectors = [
    "IBM QRadar",
    "Splunk Enterprise Security",
    "Microsoft Sentinel",
    "Elastic Security",
    "ArcSight",
    "LogRhythm",
    "Google Security Operations",
  ];
  return (
    <>
      <div className="page-title">
        <div>
          <p className="eyebrow">{t("securityDataSources")}</p>
          <h1>{t("integrations")}</h1>
        </div>
      </div>
      <PageState
        loading={health.isLoading}
        error={health.isError}
        empty={!health.isLoading && !health.isError && health.data?.length === 0}
      />
      <h2>{t("connectedSiem")}</h2>
      <section className="metrics">
        {wazuh && (
          <article>
            <p>Wazuh</p>
            <strong className="metric-text">
              {wazuh.healthy ? t("connected") : t("unavailable")}
            </strong>
            <span>
              {t("connectorType")} ·{" "}
              {t(`integrationModes.${wazuh.mode}`, { defaultValue: wazuh.mode })}
            </span>
          </article>
        )}
      </section>
      <h2>{t("platformServices")}</h2>
      <section className="metrics">
        {platformServices.map((item) => (
          <article key={item.code}>
            <p>{item.code}</p>
            <strong className="metric-text">
              {item.healthy ? t("healthy") : t("unavailable")}
            </strong>
            <span>
              {t(`integrationModes.${item.mode}`, { defaultValue: item.mode })}
              {" · "}
              {item.detail.startsWith("HTTP ")
                ? item.detail
                : t(`integrationDetails.${item.detail}`, { defaultValue: item.detail })}
            </span>
          </article>
        ))}
      </section>
      <h2>{t("plannedConnectors")}</h2>
      <section className="metrics">
        {plannedConnectors.map((name) => (
          <article key={name}>
            <p>{name}</p>
            <strong className="metric-text">{t("planned")}</strong>
            <span>{t("notAvailableVersion")}</span>
          </article>
        ))}
      </section>
    </>
  );
}

function PlaybooksPage() {
  const { t } = useTranslation();
  const controls = useListControls();
  const catalog = useQuery({
    queryKey: ["playbooks", controls.query, controls.page, controls.pageSize],
    queryFn: () =>
      getPlaybooks({
        query: controls.query,
        page: controls.page,
        pageSize: controls.pageSize,
      }),
  });
  const management = useQuery({
    queryKey: ["playbook-management"],
    queryFn: getPlaybookManagement,
    retry: false,
  });
  const items = catalog.data?.items ?? [];
  const hasNext =
    catalog.data !== undefined && (controls.page + 1) * controls.pageSize < catalog.data.total;
  return (
    <>
      <div className="page-title">
        <div>
          <p className="eyebrow">{t("approvedAutomation")}</p>
          <h1>{t("playbooks")}</h1>
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
          <strong>n8n · {t(`integrationModes.${catalog.data?.mode ?? "disabled"}`)}</strong>
        </div>
        <div>
          <span>{t("synchronizationStatus")}</span>
          <strong>{catalog.data?.synchronized ? t("synchronized") : t("syncPending")}</strong>
          <small>
            {t(`n8nSyncDetails.${catalog.data?.sync_detail ?? "api_key_not_configured"}`)}
          </small>
        </div>
        <div>
          <span>{t("administrationAccess")}</span>
          <strong>{management.data ? t("localOnly") : t("permissionDenied")}</strong>
          {management.data && <small>{management.data.editor_url}</small>}
        </div>
      </section>
      <section className="panel table-panel">
        <ListControls state={controls} visibleCount={items.length} hasNext={hasNext} />
        <PageState
          loading={catalog.isLoading}
          error={catalog.isError}
          empty={!catalog.isLoading && !catalog.isError && items.length === 0}
        />
        <div className="playbook-list">
          {items.map((playbook) => (
            <article key={playbook.workflow_id}>
              <div className="playbook-heading">
                <div>
                  <span className="demo-badge">
                    {playbook.active === null
                      ? t("statusUnknown")
                      : playbook.active
                        ? t("active")
                        : t("inactive")}
                  </span>
                  <h2>{playbook.name}</h2>
                  <code>{playbook.workflow_id}</code>
                </div>
                <div className="playbook-version">
                  <span>{t("version")}</span>
                  <strong>{playbook.version_id ?? t("notSynchronized")}</strong>
                </div>
              </div>
              <h3>{t("workflowConnectors")}</h3>
              {playbook.connectors.length === 0 ? (
                <p className="muted">{t("connectorMetadataPending")}</p>
              ) : (
                <div className="connector-grid">
                  {playbook.connectors.map((connector) => (
                    <div key={`${connector.node_type}-${connector.name}`}>
                      <strong>{connector.name}</strong>
                      <code>{connector.node_type}</code>
                      <small>
                        {connector.credential_names.length > 0
                          ? t("linkedCredentials", {
                              names: connector.credential_names.join(", "),
                            })
                          : t("noLinkedCredentials")}
                      </small>
                    </div>
                  ))}
                </div>
              )}
            </article>
          ))}
        </div>
      </section>
      <p className="security-note">{t("n8nSecretBoundary")}</p>
    </>
  );
}

function AuditPage() {
  const { t, i18n } = useTranslation();
  const controls = useListControls();
  const audit = useQuery({
    queryKey: ["audit-events", controls.query, controls.page, controls.pageSize],
    queryFn: () =>
      getAuditEvents({
        query: controls.query,
        page: controls.page,
        pageSize: controls.pageSize,
        includeLookahead: true,
      }),
  });
  const items = audit.data?.slice(0, controls.pageSize) ?? [];
  return (
    <>
      <div className="page-title">
        <div>
          <p className="eyebrow">{t("traceability")}</p>
          <h1>{t("audit")}</h1>
        </div>
      </div>
      <PageState
        loading={audit.isLoading}
        error={audit.isError}
        empty={!audit.isLoading && !audit.isError && items.length === 0}
      />
      <section className="panel table-panel">
        <ListControls
          state={controls}
          visibleCount={items.length}
          hasNext={(audit.data?.length ?? 0) > controls.pageSize}
        />
        <div className="data-list">
          {items.map((event) => (
            <article key={event.id}>
              <span className="severity">{event.outcome}</span>
              <div>
                <strong>{event.action}</strong>
                <small>{event.resource_type}</small>
              </div>
              <span>{event.actor_user_id ? t("humanActor") : t("systemActor")}</span>
              <time dateTime={event.occurred_at}>
                {new Date(event.occurred_at).toLocaleString(i18n.language)}
              </time>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}

function Administration() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState("");
  const [selectedUser, setSelectedUser] = useState("");
  const [selectedRole, setSelectedRole] = useState("");
  const userControls = useListControls();
  const tenant = useQuery({ queryKey: ["tenant"], queryFn: getTenant });
  const users = useQuery({
    queryKey: ["users", "list", userControls.query, userControls.page, userControls.pageSize],
    queryFn: () =>
      getUsers({
        query: userControls.query,
        page: userControls.page,
        pageSize: userControls.pageSize,
        includeLookahead: true,
      }),
  });
  const userOptions = useQuery({
    queryKey: ["users", "options"],
    queryFn: () => getUsers({ pageSize: 100 }),
  });
  const roles = useQuery({ queryKey: ["roles"], queryFn: getRoles });
  const permissions = useQuery({ queryKey: ["permissions"], queryFn: getPermissions });
  const userRoles = useQuery({
    queryKey: ["user-roles", selectedUser],
    queryFn: () => getUserRoles(selectedUser),
    enabled: Boolean(selectedUser),
  });
  const rolePermissions = useQuery({
    queryKey: ["role-permissions", selectedRole],
    queryFn: () => getRolePermissions(selectedRole),
    enabled: Boolean(selectedRole),
  });
  const audit = useQuery({
    queryKey: ["audit-events", "administration"],
    queryFn: () => getAuditEvents({ pageSize: 5 }),
  });
  const visibleUsers = users.data?.slice(0, userControls.pageSize) ?? [];
  const directory = useQuery({
    queryKey: ["directory-configuration"],
    queryFn: getDirectoryConfiguration,
    retry: false,
  });
  const userMutation = useMutation({
    mutationFn: createUser,
    onSuccess: async () => {
      setFormError("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["users"] }),
        queryClient.invalidateQueries({ queryKey: ["audit-events"] }),
      ]);
    },
    onError: () => setFormError(t("adminMutationError")),
  });
  const roleMutation = useMutation({
    mutationFn: createRole,
    onSuccess: async () => {
      setFormError("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["roles"] }),
        queryClient.invalidateQueries({ queryKey: ["audit-events"] }),
      ]);
    },
    onError: () => setFormError(t("adminMutationError")),
  });
  const userRolesMutation = useMutation({
    mutationFn: ({ userId, ids }: { userId: string; ids: string[] }) =>
      replaceUserRoles(userId, ids),
    onSuccess: async () => {
      setFormError("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["user-roles", selectedUser] }),
        queryClient.invalidateQueries({ queryKey: ["audit-events"] }),
      ]);
    },
    onError: () => setFormError(t("adminMutationError")),
  });
  const rolePermissionsMutation = useMutation({
    mutationFn: ({ roleId, ids }: { roleId: string; ids: string[] }) =>
      replaceRolePermissions(roleId, ids),
    onSuccess: async () => {
      setFormError("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["role-permissions", selectedRole] }),
        queryClient.invalidateQueries({ queryKey: ["audit-events"] }),
      ]);
    },
    onError: () => setFormError(t("adminMutationError")),
  });
  const directoryMutation = useMutation({
    mutationFn: saveDirectoryConfiguration,
    onSuccess: async () => {
      setFormError("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["directory-configuration"] }),
        queryClient.invalidateQueries({ queryKey: ["audit-events"] }),
      ]);
    },
    onError: () => setFormError(t("adminMutationError")),
  });
  const directoryTestMutation = useMutation({
    mutationFn: testDirectoryConfiguration,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["directory-configuration"] });
    },
    onError: () => setFormError(t("directoryTestFailed")),
  });
  const failed = tenant.isError || users.isError || roles.isError || audit.isError;
  const submitUser = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    try {
      await userMutation.mutateAsync({
        display_name: String(data.get("display_name")),
        email: String(data.get("email")),
        password: String(data.get("password")),
      });
      form.reset();
    } catch {
      // The mutation exposes the localized error and the form remains available for correction.
    }
  };
  const submitRole = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    try {
      await roleMutation.mutateAsync({
        code: String(data.get("code")),
        name: String(data.get("name")),
      });
      form.reset();
    } catch {
      // The mutation exposes the localized error and preserves the submitted values.
    }
  };
  const submitUserRoles = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const ids = new FormData(event.currentTarget).getAll("role_ids").map(String);
    userRolesMutation.mutate({ userId: selectedUser, ids });
  };
  const submitRolePermissions = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const ids = new FormData(event.currentTarget).getAll("permission_ids").map(String);
    rolePermissionsMutation.mutate({ roleId: selectedRole, ids });
  };
  const submitDirectory = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    directoryMutation.mutate({
      provider_type: String(data.get("provider_type")),
      server_uri: String(data.get("server_uri")),
      use_starttls: data.get("use_starttls") === "on",
      base_dn: String(data.get("base_dn")),
      bind_dn: String(data.get("bind_dn")),
      bind_password: String(data.get("bind_password")) || undefined,
      user_filter: String(data.get("user_filter")),
      login_attribute: String(data.get("login_attribute")),
      subject_attribute: String(data.get("subject_attribute")),
      email_attribute: String(data.get("email_attribute")),
      display_name_attribute: String(data.get("display_name_attribute")),
      group_base_dn: null,
      group_filter: null,
      group_attribute: String(data.get("group_attribute")) || null,
      ca_certificate_pem: null,
      jit_enabled: false,
      timeout_seconds: 5,
    });
  };
  return (
    <>
      <div className="page-title">
        <div>
          <p className="eyebrow">{t("controlPlane")}</p>
          <h1>{t("administration")}</h1>
        </div>
      </div>
      {failed && <p className="form-error">{t("permissionDenied")}</p>}
      {formError && <p className="form-error">{formError}</p>}
      <section className="metrics">
        <article>
          <p>{t("tenant")}</p>
          <strong>{tenant.data?.name ?? "—"}</strong>
          <span>{tenant.data?.slug}</span>
        </article>
        <article>
          <p>{t("users")}</p>
          <strong>{userOptions.data?.length ?? "—"}</strong>
          <span>{t("activeUsers")}</span>
        </article>
        <article>
          <p>{t("roles")}</p>
          <strong>{roles.data?.length ?? "—"}</strong>
          <span>{t("accessPolicies")}</span>
        </article>
        <article>
          <p>{t("recentAudit")}</p>
          <strong>{audit.data?.length ?? "—"}</strong>
          <span>{t("traceableEvents")}</span>
        </article>
      </section>
      <section className="admin-forms">
        <form className="panel compact-panel" autoComplete="off" onSubmit={submitUser}>
          <div>
            <p className="eyebrow">{t("identity")}</p>
            <h2>{t("createUser")}</h2>
          </div>
          <label>
            {t("displayName")}
            <input name="display_name" required minLength={1} maxLength={200} />
          </label>
          <label>
            {t("email")}
            <input name="email" type="email" autoComplete="off" required />
          </label>
          <label>
            {t("temporaryPassword")}
            <input
              name="password"
              type="password"
              autoComplete="new-password"
              required
              minLength={12}
            />
          </label>
          <button disabled={userMutation.isPending}>{t("create")}</button>
        </form>
        <form className="panel compact-panel" onSubmit={submitRole}>
          <div>
            <p className="eyebrow">RBAC</p>
            <h2>{t("createRole")}</h2>
          </div>
          <label>
            {t("roleCode")}
            <input name="code" required pattern="[a-z][a-z0-9-]{1,63}" />
          </label>
          <label>
            {t("roleName")}
            <input name="name" required minLength={2} maxLength={120} />
          </label>
          <button disabled={roleMutation.isPending}>{t("create")}</button>
        </form>
      </section>
      <form
        key={directory.data?.id ?? "directory-new"}
        className="panel directory-panel"
        onSubmit={submitDirectory}
      >
        <div>
          <p className="eyebrow">LDAP / Active Directory</p>
          <h2>{t("directoryConfiguration")}</h2>
          <p className="muted">
            {directory.data
              ? `${t("status")}: ${directory.data.status}`
              : t("directoryNotConfigured")}
          </p>
          {directoryTestMutation.data && (
            <p className="status-message" role="status">
              {directoryTestMutation.data.success
                ? t("directoryTestSucceeded")
                : t("directoryTestFailed")}
            </p>
          )}
        </div>
        <div className="directory-grid">
          <label>
            {t("provider")}
            <select
              name="provider_type"
              defaultValue={directory.data?.provider_type ?? "active_directory"}
            >
              <option value="active_directory">Active Directory</option>
              <option value="ldap">LDAP</option>
            </select>
          </label>
          <label>
            {t("serverUri")}
            <input
              name="server_uri"
              required
              defaultValue={directory.data?.server_uri ?? "ldaps://ldap.example.invalid"}
            />
          </label>
          <label>
            {t("baseDn")}
            <input
              name="base_dn"
              required
              defaultValue={directory.data?.base_dn ?? "dc=example,dc=invalid"}
            />
          </label>
          <label>
            {t("bindDn")}
            <input
              name="bind_dn"
              required
              defaultValue={directory.data?.bind_dn ?? "cn=service,dc=example,dc=invalid"}
            />
          </label>
          <label>
            {t("bindSecret")}
            <input
              name="bind_password"
              type="password"
              required={!directory.data?.has_bind_secret}
            />
          </label>
          <label>
            {t("userFilter")}
            <input
              name="user_filter"
              required
              defaultValue={directory.data?.user_filter ?? "(uid={username})"}
            />
          </label>
          <label>
            {t("loginAttribute")}
            <input
              name="login_attribute"
              required
              defaultValue={directory.data?.login_attribute ?? "uid"}
            />
          </label>
          <label>
            {t("subjectAttribute")}
            <input
              name="subject_attribute"
              required
              defaultValue={directory.data?.subject_attribute ?? "objectGUID"}
            />
          </label>
          <label>
            {t("emailAttribute")}
            <input
              name="email_attribute"
              required
              defaultValue={directory.data?.email_attribute ?? "mail"}
            />
          </label>
          <label>
            {t("displayNameAttribute")}
            <input
              name="display_name_attribute"
              required
              defaultValue={directory.data?.display_name_attribute ?? "displayName"}
            />
          </label>
          <label>
            {t("groupAttribute")}
            <input
              name="group_attribute"
              defaultValue={directory.data?.group_attribute ?? "memberOf"}
            />
          </label>
          <label className="check-row">
            <input
              name="use_starttls"
              type="checkbox"
              defaultChecked={directory.data?.use_starttls}
            />
            StartTLS
          </label>
        </div>
        <div className="form-actions">
          <button disabled={directoryMutation.isPending}>{t("save")}</button>
          <button
            className="ghost"
            type="button"
            disabled={!directory.data || directoryTestMutation.isPending}
            onClick={() => directoryTestMutation.mutate()}
          >
            {t("testConnection")}
          </button>
        </div>
      </form>
      <section className="admin-forms">
        <form
          key={`user-${selectedUser}-${userRoles.data?.join("-")}`}
          className="panel compact-panel"
          onSubmit={submitUserRoles}
        >
          <div>
            <p className="eyebrow">RBAC</p>
            <h2>{t("assignRoles")}</h2>
          </div>
          <select value={selectedUser} onChange={(event) => setSelectedUser(event.target.value)}>
            <option value="">{t("selectUser")}</option>
            {userOptions.data?.map((user) => (
              <option key={user.id} value={user.id}>
                {user.display_name}
              </option>
            ))}
          </select>
          {roles.data?.map((role) => (
            <label className="check-row" key={role.id}>
              <input
                type="checkbox"
                name="role_ids"
                value={role.id}
                defaultChecked={userRoles.data?.includes(role.id)}
                disabled={!selectedUser}
              />
              {role.name}
            </label>
          ))}
          <button disabled={!selectedUser || userRolesMutation.isPending}>{t("save")}</button>
        </form>
        <form
          key={`role-${selectedRole}-${rolePermissions.data?.join("-")}`}
          className="panel compact-panel"
          onSubmit={submitRolePermissions}
        >
          <div>
            <p className="eyebrow">RBAC</p>
            <h2>{t("assignPermissions")}</h2>
          </div>
          <select value={selectedRole} onChange={(event) => setSelectedRole(event.target.value)}>
            <option value="">{t("selectRole")}</option>
            {roles.data?.map((role) => (
              <option key={role.id} value={role.id} disabled={role.is_system}>
                {role.name}
              </option>
            ))}
          </select>
          {permissions.data?.map((permission) => (
            <label className="check-row" key={permission.id}>
              <input
                type="checkbox"
                name="permission_ids"
                value={permission.id}
                defaultChecked={rolePermissions.data?.includes(permission.id)}
                disabled={!selectedRole}
              />
              {permission.code}
            </label>
          ))}
          <button disabled={!selectedRole || rolePermissionsMutation.isPending}>{t("save")}</button>
        </form>
      </section>
      <section className="panel admin-panel" id="audit-summary">
        <div>
          <h2>{t("users")}</h2>
          <ListControls
            state={userControls}
            visibleCount={visibleUsers.length}
            hasNext={(users.data?.length ?? 0) > userControls.pageSize}
          />
          <div className="admin-list">
            {visibleUsers.map((user) => (
              <div key={user.id}>
                <strong>{user.display_name}</strong>
                <span>{user.email}</span>
                <small>{user.is_active ? t("active") : t("inactive")}</small>
              </div>
            ))}
          </div>
        </div>
        <div>
          <h2>{t("recentAudit")}</h2>
          <div className="admin-list">
            {audit.data?.map((event) => (
              <div key={event.id}>
                <strong>{event.action}</strong>
                <span>{event.resource_type}</span>
                <small>{new Date(event.occurred_at).toLocaleString()}</small>
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}

function NotFound() {
  const { t } = useTranslation();
  return (
    <main className="center">
      <h1>404</h1>
      <p>{t("notFound")}</p>
      <NavLink to="/">{t("returnHome")}</NavLink>
    </main>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route index element={<Overview />} />
          <Route path="alerts" element={<AlertsPage />} />
          <Route path="incidents" element={<IncidentsPage />} />
          <Route path="incidents/:id" element={<IncidentDetailPage />} />
          <Route path="playbooks" element={<PlaybooksPage />} />
          <Route path="integrations" element={<IntegrationsPage />} />
          <Route path="audit" element={<AuditPage />} />
          <Route path="administration" element={<Administration />} />
        </Route>
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
