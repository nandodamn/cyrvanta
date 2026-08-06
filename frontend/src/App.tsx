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
  decideResponse,
  analyzeIncident,
  directoryLogin,
  downloadIncidentReport,
  executeAuthorizedResponse,
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
  getPlaybookExecutions,
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
import { ApiKeysPage } from "./ApiKeysPage";
import { GovernedMemoryPage } from "./GovernedMemoryPage";
import { PlaybookLibraryPage } from "./PlaybookLibraryPage";
import { OperationalPulse } from "./OperationalPulse";
import { SecurityTopologyPanel } from "./SecurityTopologyPanel";
import { useAuth } from "./AuthContext";
import { ConnectionModal, ConnectionMeta } from "./ConnectionModal";

const NAV_ITEMS: ReadonlyArray<{ to: string; icon: React.ReactNode; key: string; end?: boolean }> = [
  {
    to: "/",
    key: "overview",
    end: true,
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="7" height="7" rx="1.5" />
        <rect x="14" y="3" width="7" height="7" rx="1.5" />
        <rect x="14" y="14" width="7" height="7" rx="1.5" />
        <rect x="3" y="14" width="7" height="7" rx="1.5" />
      </svg>
    ),
  },
  {
    to: "/incidents",
    key: "incidents",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
        <line x1="12" y1="8" x2="12" y2="12" />
        <line x1="12" y1="16" x2="12.01" y2="16" />
      </svg>
    ),
  },
  {
    to: "/alerts",
    key: "alerts",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
        <path d="M13.73 21a2 2 0 0 1-3.46 0" />
      </svg>
    ),
  },
  {
    to: "/playbooks",
    key: "playbooks",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="6" height="6" rx="1.5" />
        <rect x="15" y="15" width="6" height="6" rx="1.5" />
        <path d="M6 9v3a3 3 0 0 0 3 3h6" />
        <polyline points="14 12 17 15 14 18" />
      </svg>
    ),
  },
  {
    to: "/integrations",
    key: "integrations",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M16 16v1a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h11a2 2 0 0 1 2 2v1" />
        <path d="M18 8l4 4-4 4" />
        <line x1="8" y1="12" x2="22" y2="12" />
      </svg>
    ),
  },
  {
    to: "/memory",
    key: "memory.navigation",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <ellipse cx="12" cy="5" rx="9" ry="3" />
        <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
        <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
      </svg>
    ),
  },
  {
    to: "/api-keys",
    key: "apiKeys.navigation",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="7.5" cy="15.5" r="5.5" />
        <path d="M21 2l-9.6 9.6" />
        <path d="M15.5 7.5l3 3" />
      </svg>
    ),
  },
  {
    to: "/audit",
    key: "audit",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" />
      </svg>
    ),
  },
  {
    to: "/administration",
    key: "administration",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
      </svg>
    ),
  },
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
          <input autoComplete="organization" placeholder="demo" {...register("tenantSlug")} />
        </label>
        <label>
          {authMode === "local" ? t("email") : t("directoryUsername")}
          <input
            type={authMode === "local" ? "email" : "text"}
            autoComplete="username"
            placeholder={authMode === "local" ? "demo@cyrvanta.uy" : "ldap-demo"}
            {...register("email")}
          />
        </label>
        <label>
          {t("password")}
          <input type="password" autoComplete="current-password" placeholder="••••••••" {...register("password")} />
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
      style={{
        display: "flex",
        alignItems: "center",
        flexWrap: "wrap",
        gap: "10px",
        justifyContent: "space-between",
        marginBottom: "1rem",
        paddingBottom: "0.75rem",
        borderBottom: "1px solid var(--line)",
      }}
      onSubmit={(event) => {
        event.preventDefault();
        state.applySearch();
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "8px", flex: "1 1 240px", maxWidth: "420px" }}>
        <input
          type="search"
          maxLength={100}
          value={state.draft}
          placeholder={t("searchPlaceholder")}
          onChange={(event) => state.setDraft(event.target.value)}
          style={{ flex: 1, padding: "6px 12px", fontSize: "0.825rem", borderRadius: "4px", border: "1px solid var(--line)", background: "var(--panel)" }}
        />
        <button
          type="submit"
          style={{ width: "auto", minWidth: "unset", height: "auto", padding: "6px 14px", fontSize: "0.825rem", whiteSpace: "nowrap" }}
        >
          {t("search")}
        </button>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <span style={{ fontSize: "0.8rem", color: "var(--muted)", whiteSpace: "nowrap" }}>{t("itemsPerPage")}:</span>
          <select
            value={state.pageSize}
            onChange={(event) => state.setPageSize(Number(event.target.value))}
            style={{ padding: "4px 8px", fontSize: "0.8rem", borderRadius: "4px", border: "1px solid var(--line)", background: "var(--panel)", color: "var(--text)" }}
          >
            {[10, 25, 50].map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </div>

        <span className="list-result-count" style={{ fontSize: "0.8rem", color: "var(--muted)", whiteSpace: "nowrap" }}>
          {t("visibleResults", { count: visibleCount, page: state.page + 1 })}
        </span>

        <div className="pager" style={{ display: "flex", gap: "4px" }}>
          <button
            type="button"
            className="ghost"
            style={{ width: "auto", minWidth: "unset", height: "auto", padding: "4px 10px", fontSize: "0.75rem", whiteSpace: "nowrap" }}
            disabled={state.page === 0}
            onClick={() => state.setPage(Math.max(0, state.page - 1))}
          >
            {t("previous")}
          </button>
          <button
            type="button"
            className="ghost"
            style={{ width: "auto", minWidth: "unset", height: "auto", padding: "4px 10px", fontSize: "0.75rem", whiteSpace: "nowrap" }}
            disabled={!hasNext}
            onClick={() => state.setPage(state.page + 1)}
          >
            {t("next")}
          </button>
        </div>
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
        <OperationalPulse />
        <SecurityTopologyPanel />
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
  const queryClient = useQueryClient();
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const controls = useListControls();
  const me = useQuery({ queryKey: ["me"], queryFn: getMe, retry: false });

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

  const triageMutation = useMutation({
    mutationFn: ({
      alertId,
      status,
    }: {
      alertId: string;
      status: "UNREVIEWED" | "RELEVANT" | "DISCARDED";
    }) => updateAlertTriage(alertId, status),
    onMutate: async ({ alertId, status }) => {
      await queryClient.cancelQueries({ queryKey: ["alerts"] });
      queryClient.setQueriesData(
        { queryKey: ["alerts"] },
        (oldData: Alert[] | undefined) => {
          if (!oldData || !Array.isArray(oldData)) return oldData;
          return oldData.map((item) =>
            item.id === alertId
              ? {
                  ...item,
                  triage_status: status,
                  reviewed_at: new Date().toISOString(),
                  reviewer_display_name: me.data?.display_name ?? "Analyst",
                }
              : item,
          );
        },
      );
    },
    onSettled: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["alerts"] }),
        queryClient.invalidateQueries({ queryKey: ["incident-alerts"] }),
        queryClient.invalidateQueries({ queryKey: ["audit-events"] }),
      ]);
    },
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
          {items.map((alert) => {
            const isExpanded = expandedId === alert.id;
            const isDimmed = alert.triage_status === "DISCARDED";
            const isRelevant = alert.triage_status === "RELEVANT";

            return (
              <article
                key={alert.id}
                style={{
                  cursor: "pointer",
                  opacity: isDimmed ? 0.55 : 1,
                  borderLeft: isRelevant
                    ? "4px solid var(--accent)"
                    : isDimmed
                    ? "4px solid var(--muted)"
                    : "1px solid var(--panel-border)",
                  background: isRelevant ? "rgba(13, 209, 155, 0.05)" : "transparent",
                  transition: "all 0.2s ease",
                }}
                onClick={() => setExpandedId(isExpanded ? null : alert.id)}
              >
                <span className={`severity ${alert.severity}`}>
                  {t(`severityCodes.${alert.severity}`, { defaultValue: alert.severity })}
                </span>
                <div>
                  <strong>
                    {alert.title}
                    {alert.triage_status !== "UNREVIEWED" && (
                      <span
                        className="demo-badge"
                        style={{
                          marginLeft: "8px",
                          verticalAlign: "middle",
                          background: isRelevant ? "var(--accent)" : "var(--panel-raised)",
                          color: isRelevant ? "#041512" : "var(--text-soft)",
                          fontWeight: 600,
                        }}
                      >
                        {isRelevant ? "⭐ " : "✓ "}
                        {t(`triageStatus.${alert.triage_status}`, {
                          defaultValue: alert.triage_status,
                        })}
                      </span>
                    )}
                  </strong>
                  <small>
                    {alert.source} · {alert.category}
                  </small>
                </div>
                {alert.is_simulated ? (
                  <span className="demo-badge">{t("simulated")}</span>
                ) : (
                  <span />
                )}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    justify: "flex-end",
                    flexWrap: "wrap",
                  }}
                >
                  <time dateTime={alert.observed_at}>
                    {new Date(alert.observed_at).toLocaleString(i18n.language)}
                  </time>

                  {/* Quick Inline Triage Buttons */}
                  <div style={{ display: "flex", gap: "4px" }}>
                    <button
                      type="button"
                      className="ghost"
                      title={t("markRelevant")}
                      style={{
                        minHeight: "auto",
                        padding: "4px 8px",
                        fontSize: "0.75rem",
                        whiteSpace: "nowrap",
                        background: isRelevant ? "var(--accent)" : "transparent",
                        color: isRelevant ? "#041512" : "var(--text)",
                      }}
                      onClick={(e) => {
                        e.stopPropagation();
                        triageMutation.mutate({
                          alertId: alert.id,
                          status: isRelevant ? "UNREVIEWED" : "RELEVANT",
                        });
                      }}
                    >
                      ⭐ {t("markRelevant")}
                    </button>
                    <button
                      type="button"
                      className="ghost"
                      title={t("discardAlert")}
                      style={{
                        minHeight: "auto",
                        padding: "4px 8px",
                        fontSize: "0.75rem",
                        whiteSpace: "nowrap",
                        opacity: isDimmed ? 0.7 : 1,
                      }}
                      onClick={(e) => {
                        e.stopPropagation();
                        triageMutation.mutate({
                          alertId: alert.id,
                          status: isDimmed ? "UNREVIEWED" : "DISCARDED",
                        });
                      }}
                    >
                      {isDimmed ? "↺ " + t("resetTriage") : "✓ " + t("discardAlert")}
                    </button>
                    <button
                      type="button"
                      className="ghost"
                      style={{
                        minHeight: "auto",
                        padding: "4px 8px",
                        fontSize: "0.75rem",
                        whiteSpace: "nowrap",
                      }}
                      onClick={(e) => {
                        e.stopPropagation();
                        setExpandedId(isExpanded ? null : alert.id);
                      }}
                    >
                      {isExpanded ? t("hideDetails") : t("showDetails")}
                    </button>
                  </div>
                </div>

                {isExpanded && (
                  <div
                    className="analysis-card"
                    style={{ gridColumn: "1 / -1", marginTop: "12px", opacity: 1 }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <div
                      style={{
                        display: "flex",
                        justify: "space-between",
                        alignItems: "center",
                        marginBottom: "12px",
                      }}
                    >
                      <strong>{t("alertDetails")}</strong>
                      <button
                        type="button"
                        className="ghost"
                        style={{ minHeight: "auto", padding: "4px 10px", fontSize: "0.8rem" }}
                        onClick={() => setExpandedId(null)}
                      >
                        ✕ {t("close")}
                      </button>
                    </div>
                    <div className="connector-grid">
                      <div>
                        <strong>{t("externalId")}</strong>
                        <small>{alert.external_id || alert.id}</small>
                      </div>
                      <div>
                        <strong>{t("provenance")}</strong>
                        <small>{alert.provenance || alert.source}</small>
                      </div>
                      <div>
                        <strong>{t("assetSummary")}</strong>
                        <small>{alert.asset_summary || t("noParameters")}</small>
                      </div>
                      <div>
                        <strong>{t("identitySummary")}</strong>
                        <small>{alert.identity_summary || t("noParameters")}</small>
                      </div>
                      <div>
                        <strong>{t("indicatorSummary")}</strong>
                        <small>{alert.indicator_summary || t("noParameters")}</small>
                      </div>
                    </div>
                    <div
                      style={{
                        marginTop: "1rem",
                        display: "flex",
                        gap: "10px",
                        alignItems: "center",
                        flexWrap: "wrap",
                      }}
                    >
                      <button
                        type="button"
                        className="ghost"
                        disabled={triageMutation.isPending}
                        style={{
                          background: isRelevant ? "var(--accent)" : "transparent",
                          color: isRelevant ? "#041512" : "var(--text)",
                        }}
                        onClick={(e) => {
                          e.stopPropagation();
                          triageMutation.mutate({ alertId: alert.id, status: "RELEVANT" });
                        }}
                      >
                        ⭐ {t("markRelevant")}
                      </button>
                      <button
                        type="button"
                        className="ghost"
                        disabled={triageMutation.isPending}
                        onClick={(e) => {
                          e.stopPropagation();
                          triageMutation.mutate({ alertId: alert.id, status: "DISCARDED" });
                        }}
                      >
                        ✓ {t("discardAlert")}
                      </button>
                      {alert.triage_status !== "UNREVIEWED" && (
                        <button
                          type="button"
                          className="ghost"
                          disabled={triageMutation.isPending}
                          onClick={(e) => {
                            e.stopPropagation();
                            triageMutation.mutate({ alertId: alert.id, status: "UNREVIEWED" });
                          }}
                        >
                          ↺ {t("resetTriage")}
                        </button>
                      )}
                    </div>
                    {alert.reviewed_at && (
                      <p style={{ margin: "10px 0 0", fontSize: "0.85rem", color: "var(--muted)" }}>
                        {t("treatedBy", {
                          user: alert.reviewer_display_name || alert.reviewed_by_user_id || "Analyst",
                          time: new Date(alert.reviewed_at).toLocaleString(i18n.language),
                        })}
                      </p>
                    )}
                  </div>
                )}
              </article>
            );
          })}
        </div>
      </section>
    </>
  );
}

function IncidentsPage() {
  const { t, i18n } = useTranslation();
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
          {items.map((incident) => {
            const detectedDate = incident.detected_at ? new Date(incident.detected_at) : null;
            const isValidDate = detectedDate && !isNaN(detectedDate.getTime());
            return (
              <NavLink
                to={`/incidents/${incident.id}`}
                key={incident.id}
                style={{ display: "flex", alignItems: "center", gap: "14px" }}
              >
                <span className={`severity ${incident.severity}`}>
                  {t(`severityCodes.${incident.severity}`, { defaultValue: incident.severity })}
                </span>
                <div style={{ flex: 1, display: "flex", alignItems: "center", gap: "10px", minWidth: 0 }}>
                  <strong style={{ whiteSpace: "nowrap" }}>
                    {incident.code} · {incident.title}
                  </strong>
                  <span style={{ color: "var(--muted)", fontSize: "0.85rem", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    ({incident.classification})
                  </span>
                </div>
                {isValidDate && (
                  <span style={{ fontSize: "0.875rem", color: "var(--text-soft)", whiteSpace: "nowrap", fontFamily: "var(--font-mono, monospace)" }}>
                    {detectedDate.toLocaleString(i18n.language)}
                  </span>
                )}
                <span style={{ whiteSpace: "nowrap" }}>{t(`statusCodes.${incident.status}`, { defaultValue: incident.status })}</span>
                {incident.is_simulated && <span className="demo-badge" style={{ whiteSpace: "nowrap" }}>{t("simulated")}</span>}
              </NavLink>
            );
          })}
        </div>
      </section>
    </>
  );
}

function IncidentDetailPage() {
  const { id = "" } = useParams();
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<"overview" | "alerts" | "threatIntel" | "audit">("overview");
  const [expandedAlertId, setExpandedAlertId] = useState<string | null>(null);
  const [showMoreMenu, setShowMoreMenu] = useState(false);

  const incident = useQuery({ queryKey: ["incident", id], queryFn: () => getIncident(id) });
  const currentUser = useQuery({ queryKey: ["me"], queryFn: getMe, retry: false });
  const timeline = useQuery({ queryKey: ["timeline", id], queryFn: () => getTimeline(id) });
  const claims = useQuery({ queryKey: ["claims", id], queryFn: () => getClaims(id) });
  const correlations = useQuery({
    queryKey: ["correlations", id],
    queryFn: () => getCorrelations(id),
  });
  const linkedAlerts = useQuery({
    queryKey: ["incident-alerts", id],
    queryFn: () => getIncidentAlerts(id),
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
  const playbookExecutions = useQuery({
    queryKey: ["playbook-executions", id],
    queryFn: () => getPlaybookExecutions(id),
    retry: false,
  });

  const [transitionNote, setTransitionNote] = useState("");

  const transition = useMutation({
    mutationFn: ({ target, reason }: { target: string; reason?: string }) =>
      transitionIncident(id, incident.data!.version, target, reason),
    onSuccess: async () => {
      setTransitionNote("");
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
  const executeResponse = useMutation({
    mutationFn: (authorizationId: string) => executeAuthorizedResponse(authorizationId),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["response-decisions", id] }),
        queryClient.invalidateQueries({ queryKey: ["playbook-executions", id] }),
      ]);
    },
  });
  const rollbackResponse = useMutation({
    mutationFn: () => executeRollbackProposal(id),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["response-decisions", id] }),
        queryClient.invalidateQueries({ queryKey: ["playbook-executions", id] }),
        queryClient.invalidateQueries({ queryKey: ["timeline", id] }),
      ]);
    },
  });
  const approvalDecision = useMutation({
    mutationFn: ({
      requestId,
      decision,
      fingerprint,
    }: {
      requestId: string;
      decision: "APPROVE" | "REJECT";
      fingerprint: string;
    }) => decideResponse(requestId, decision, fingerprint),
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
          <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
            <p className="eyebrow" style={{ margin: 0 }}>{incident.data.code}</p>
            {incident.data.detected_at && !isNaN(new Date(incident.data.detected_at).getTime()) && (
              <span style={{ fontSize: "0.8rem", color: "var(--muted)", fontWeight: 500 }}>
                📅 {new Date(incident.data.detected_at).toLocaleString(i18n.language, { dateStyle: "medium", timeStyle: "medium" })}
              </span>
            )}
            {incident.data.is_simulated && <span className="demo-badge">{t("simulated")}</span>}
          </div>
          <h1 style={{ margin: "4px 0 0" }}>{incident.data.title}</h1>
        </div>
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

      {/* Enterprise Tab Bar Segmented Control with 3-Dots Menu */}
      <div style={{ position: "relative", marginBottom: "1.5rem" }}>
        <nav
          aria-label="Incident Detail Sections"
          style={{
            display: "flex",
            justify: "space-between",
            alignItems: "center",
            background: "var(--panel-raised)",
            border: "1px solid var(--line)",
            borderRadius: "8px",
            padding: "4px 8px",
            flexWrap: "wrap",
            gap: "8px",
          }}
        >
          <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
            <button
              type="button"
              style={{
                border: "none",
                borderRadius: "6px",
                padding: "8px 16px",
                fontSize: "0.875rem",
                fontWeight: activeTab === "overview" ? 600 : 400,
                cursor: "pointer",
                background: activeTab === "overview" ? "var(--accent)" : "transparent",
                color: activeTab === "overview" ? "#041512" : "var(--text)",
                transition: "all 0.2s ease",
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
              }}
              onClick={() => setActiveTab("overview")}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="7" height="7" rx="1.5" />
                <rect x="14" y="3" width="7" height="7" rx="1.5" />
                <rect x="14" y="14" width="7" height="7" rx="1.5" />
                <rect x="3" y="14" width="7" height="7" rx="1.5" />
              </svg>
              {t("tabOverview")}
            </button>
            <button
              type="button"
              style={{
                border: "none",
                borderRadius: "6px",
                padding: "8px 16px",
                fontSize: "0.875rem",
                fontWeight: activeTab === "alerts" ? 600 : 400,
                cursor: "pointer",
                background: activeTab === "alerts" ? "var(--accent)" : "transparent",
                color: activeTab === "alerts" ? "#041512" : "var(--text)",
                transition: "all 0.2s ease",
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
              }}
              onClick={() => setActiveTab("alerts")}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                <path d="M13.73 21a2 2 0 0 1-3.46 0" />
              </svg>
              {t("tabAlerts")} {linkedAlerts.data?.length ? `(${linkedAlerts.data.length})` : ""}
            </button>
            <button
              type="button"
              style={{
                border: "none",
                borderRadius: "6px",
                padding: "8px 16px",
                fontSize: "0.875rem",
                fontWeight: activeTab === "threatIntel" ? 600 : 400,
                cursor: "pointer",
                background: activeTab === "threatIntel" ? "var(--accent)" : "transparent",
                color: activeTab === "threatIntel" ? "#041512" : "var(--text)",
                transition: "all 0.2s ease",
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
              }}
              onClick={() => setActiveTab("threatIntel")}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
              {t("tabThreatIntel")}
            </button>
            <button
              type="button"
              style={{
                border: "none",
                borderRadius: "6px",
                padding: "8px 16px",
                fontSize: "0.875rem",
                fontWeight: activeTab === "audit" ? 600 : 400,
                cursor: "pointer",
                background: activeTab === "audit" ? "var(--accent)" : "transparent",
                color: activeTab === "audit" ? "#041512" : "var(--text)",
                transition: "all 0.2s ease",
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
              }}
              onClick={() => setActiveTab("audit")}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
              </svg>
              {t("tabAudit")} {playbookExecutions.data?.length ? `(${playbookExecutions.data.length})` : ""}
            </button>
          </div>

          {/* 3-Dots Vertical Menu Container */}
          <div style={{ position: "relative", display: "inline-block" }}>
            <button
              type="button"
              className="ghost"
              style={{
                padding: "6px 12px",
                fontSize: "1.1rem",
                minHeight: "36px",
                cursor: "pointer",
              }}
              aria-expanded={showMoreMenu}
              aria-label="Más opciones"
              onClick={() => setShowMoreMenu(!showMoreMenu)}
            >
              ⋮
            </button>

            {/* 3-Dots Dropdown Popover */}
            {showMoreMenu && (
              <div
                style={{
                  position: "absolute",
                  top: "calc(100% + 8px)",
                  right: 0,
                  background: "var(--panel-raised)",
                  border: "1px solid var(--line)",
                  borderRadius: "8px",
                  padding: "8px",
                  boxShadow: "0 8px 24px rgba(0, 0, 0, 0.4)",
                  zIndex: 100,
                  minWidth: "220px",
                  display: "flex",
                  flexDirection: "column",
                  gap: "6px",
                }}
              >
                <button
                  type="button"
                  className="ghost"
                  disabled={analysis.isPending}
                  style={{ justifyContent: "flex-start", width: "100%", textAlign: "left" }}
                  onClick={() => {
                    setShowMoreMenu(false);
                    analysis.mutate();
                  }}
                >
                  🔍 {t("analyze")}
                </button>
                <button
                  type="button"
                  className="ghost"
                  style={{ justifyContent: "flex-start", width: "100%", textAlign: "left" }}
                  onClick={() => {
                    setShowMoreMenu(false);
                    void downloadIncidentReport(id, incident.data!.code);
                  }}
                >
                  📄 {t("downloadReport")}
                </button>
              </div>
            )}
          </div>
        </nav>
      </div>

      {activeTab === "overview" && (
        <>
          {/* Recommended Playbooks & Approval Section */}
          <section className="panel" style={{ marginBottom: "1.25rem" }}>
            <div
              style={{
                display: "flex",
                justify: "space-between",
                alignItems: "flex-start",
                marginBottom: "1rem",
                flexWrap: "wrap",
                gap: "12px",
              }}
            >
              <div>
                <p className="eyebrow">{t("safeResponse")}</p>
                <h2 style={{ margin: 0 }}>{t("recommendedPlaybooksHeading")}</h2>
              </div>

              {(() => {
                const hasPending = responseDecisions.data?.some((d) => d.approval_status === "PENDING");
                return (
                  <button
                    type="button"
                    disabled={responseProposal.isPending || hasPending}
                    title={hasPending ? t("proposalPendingNotice", { defaultValue: "Ya existe una propuesta pendiente de aprobación" }) : undefined}
                    onClick={() => responseProposal.mutate()}
                  >
                    ⚡ {t("proposeSafeResponse")}
                  </button>
                );
              })()}
            </div>

            {/* Sub-header Notice Banner for 4-Eye Principle */}
            {responseDecisions.data?.some(
              (d) => d.status === "AWAITING_APPROVAL" && d.approval_status === "PENDING"
            ) && (
              <div
                style={{
                  border: "1px solid var(--line)",
                  borderRadius: "6px",
                  padding: "8px 14px",
                  fontSize: "0.85rem",
                  color: "var(--text-soft)",
                  marginBottom: "1.25rem",
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
                <span>ℹ️</span>
                <span>{t("dualControlNotice")}</span>
              </div>
            )}

            {responseProposal.data && (
              <div
                className="demo-badge"
                style={{
                  padding: "8px 14px",
                  fontSize: "0.85rem",
                  marginBottom: "1rem",
                  display: "inline-block",
                }}
              >
                ✓ {t("proposalCreated")}
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
              {responseDecisions.data?.map((decision) => {
                const isCompleted = ["AUTHORIZED", "ROLLED_BACK", "EXECUTED"].includes(decision.status) || decision.approval_status === "APPROVED";
                const countApproved = isCompleted ? 2 : Math.max(decision.decisions.filter((d) => d.decision === "APPROVE").length, 0);
                const totalApprovals = 2;
                return (
                  <article
                    className="claim-card"
                    key={decision.id}
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      justify: "space-between",
                      padding: "1.25rem",
                      border: "1px solid var(--panel-border)",
                      borderRadius: "8px",
                    }}
                  >
                    <div>
                      <div className="claim-badges" style={{ marginBottom: "10px" }}>
                        <span className="severity">{decision.status}</span>
                        <span>{decision.impact}</span>
                        {decision.is_simulated && <span>{t("simulated")}</span>}
                      </div>
                      <strong style={{ fontSize: "1.15rem", display: "block", marginBottom: "6px" }}>
                        {decision.action_type}
                      </strong>
                      <div style={{ background: "var(--panel-raised)", padding: "8px 12px", borderRadius: "6px", margin: "6px 0 10px", borderLeft: "3px solid var(--accent)" }}>
                        <span style={{ fontSize: "0.75rem", color: "var(--muted)", display: "block", marginBottom: "2px" }}>
                          🎯 {t("targetBlockedEntity", { defaultValue: "Usuario / Entidad objetivo del bloqueo:" })}
                        </span>
                        <strong style={{ fontSize: "0.9rem", color: "var(--text-bright)", fontFamily: "var(--font-mono, monospace)" }}>
                          {decision.targets && decision.targets.length > 0 ? decision.targets.join(", ") : "synthetic-demo-user"}
                        </strong>
                      </div>
                      <p style={{ margin: "6px 0", fontSize: "0.9rem" }}>
                        <strong>{t("approvalProgress")}:</strong> {countApproved}/{totalApprovals}
                        {isCompleted && <span style={{ color: "var(--accent)", marginLeft: "6px", fontWeight: 600 }}>✓ Aprobado por 4-Ojos</span>}
                      </p>
                      <small style={{ color: "var(--muted)", display: "block", marginTop: "6px" }}>
                        {t("policyOutcome")}: {decision.evaluation_outcome} · {decision.reason_codes.join(" · ")}
                      </small>
                    </div>
                    <div style={{ marginTop: "16px" }}>
                      {decision.approval_request_id &&
                        decision.approval_status === "PENDING" &&
                        decision.status === "AWAITING_APPROVAL" &&
                        (currentUser.data?.id !== decision.requester_user_id ? (
                          <div style={{ display: "flex", gap: "10px" }}>
                            <button
                              type="button"
                              style={{ flex: 1 }}
                              disabled={approvalDecision.isPending}
                              onClick={() =>
                                approvalDecision.mutate({
                                  requestId: decision.approval_request_id!,
                                  decision: "APPROVE",
                                  fingerprint: decision.fingerprint,
                                })
                              }
                            >
                              ✓ {t("approveResponse")}
                            </button>
                            <button
                              type="button"
                              className="ghost"
                              style={{ flex: 1 }}
                              disabled={approvalDecision.isPending}
                              onClick={() =>
                                approvalDecision.mutate({
                                  requestId: decision.approval_request_id!,
                                  decision: "REJECT",
                                  fingerprint: decision.fingerprint,
                                })
                              }
                            >
                              ✕ {t("rejectResponse")}
                            </button>
                          </div>
                        ) : (
                          <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-soft)", background: "var(--panel-raised)", padding: "8px 12px", borderRadius: "6px" }}>
                            🔒 {t("awaitingSecondAnalystNotice", { defaultValue: "Esperando aprobación de un 2º analista (Principio 4-Ojos)" })}
                          </p>
                        ))}
                      {decision.authorization?.status === "ACTIVE" && (
                        <button
                          type="button"
                          style={{ width: "100%", minHeight: "40px" }}
                          disabled={executeResponse.isPending}
                          onClick={() => executeResponse.mutate(decision.authorization!.id)}
                        >
                          ▶ {t("simulateResponse")}
                        </button>
                      )}
                      <button
                        type="button"
                        className="ghost"
                        style={{ width: "100%", marginTop: "8px", minHeight: "36px", color: "var(--accent)" }}
                        disabled={rollbackResponse.isPending}
                        onClick={() => rollbackResponse.mutate()}
                      >
                        {rollbackResponse.isPending ? t("loading") : `🔄 ${t("rollbackAction", { defaultValue: "Deshacer / Rollback (Restaurar Acceso)" })}`}
                      </button>
                      {rollbackResponse.isSuccess && (
                        <p style={{ margin: "6px 0 0", fontSize: "0.8rem", color: "#10b981", textAlign: "center" }}>
                          ✓ {t("rollbackExecuted", { defaultValue: "Acceso del usuario restaurado a estado activo." })}
                        </p>
                      )}
                    </div>
                  </article>
                );
              })}
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

          {/* Operational Timeline Panel */}
          <section className="panel">
            <div style={{ marginBottom: "1rem" }}>
              <h2>{t("timeline")}</h2>
              <p style={{ color: "var(--muted)", margin: "4px 0 0" }}>{incident.data.description}</p>
            </div>

            {analysis.data && (
              <div className="analysis-card" style={{ marginBottom: "1rem" }}>
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

            {(transition.isError || analysis.isError || responseProposal.isError) && (
              <p className="status-message status-error" role="alert" style={{ marginBottom: "1rem" }}>
                {t("actionError")}
              </p>
            )}

            <div className="timeline" style={{ marginTop: "1rem" }}>
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
            </div>

            {/* Inline Investigation Workflow & Note Form under timeline events */}
            <div
              style={{
                marginTop: "1.5rem",
                padding: "1rem 1.25rem",
                background: "rgba(255, 255, 255, 0.02)",
                border: "1px solid var(--line)",
                borderRadius: "8px",
              }}
            >
              <div style={{ marginBottom: "0.75rem" }}>
                <strong style={{ fontSize: "0.9rem", color: "var(--text)" }}>
                  📝 Registro de Investigación & Cambio de Estado
                </strong>
                <p style={{ margin: "4px 0 0", fontSize: "0.8rem", color: "var(--muted)" }}>
                  Registra hallazgos, evidencias verificadas o la justificación para avanzar la investigación. Las notas quedan guardadas inmutablemente en la línea temporal del SOC.
                </p>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                <textarea
                  rows={2}
                  maxLength={500}
                  value={transitionNote}
                  placeholder="Escribe la justificación o hallazgos para esta etapa (ej: Se verificaron registros de autenticación del usuario admin...)"
                  onChange={(e) => setTransitionNote(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    fontSize: "0.85rem",
                    borderRadius: "6px",
                    border: "1px solid var(--line)",
                    background: "var(--panel)",
                    color: "var(--text)",
                    resize: "vertical",
                  }}
                />

                <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: "10px" }}>
                  <button
                    type="button"
                    className="primary"
                    disabled={transition.isPending}
                    style={{
                      padding: "6px 16px",
                      fontSize: "0.825rem",
                      fontWeight: 600,
                      width: "auto",
                      minWidth: "unset",
                      height: "auto",
                    }}
                    onClick={() =>
                      transition.mutate({
                        target: next[incident.data.status],
                        reason: transitionNote,
                      })
                    }
                  >
                    {transition.isPending ? t("loading") : `➜ ${t("advanceTo")} ${t(`statusCodes.${next[incident.data.status]}`, { defaultValue: next[incident.data.status] })}`}
                  </button>
                </div>
              </div>
            </div>
          </section>
        </>
      )}

      {activeTab === "alerts" && (
        <>
          <section className="panel" style={{ marginBottom: "1.25rem" }}>
            <div>
              <p className="eyebrow">{t("traceability")}</p>
              <h2>{t("tabAlerts")}</h2>
              <p>{t("linkedAlertsIntro")}</p>
            </div>
            <PageState
              loading={linkedAlerts.isLoading}
              error={linkedAlerts.isError}
              empty={!linkedAlerts.isLoading && !linkedAlerts.isError && linkedAlerts.data?.length === 0}
            />
            <div className="data-list" style={{ marginTop: "1rem" }}>
              {linkedAlerts.data?.map((alert) => {
                const isExpanded = expandedAlertId === alert.id;
                const isDimmed = alert.triage_status === "DISCARDED";
                return (
                  <article
                    key={alert.id}
                    style={{ cursor: "pointer", opacity: isDimmed ? 0.55 : 1 }}
                    onClick={() => setExpandedAlertId(isExpanded ? null : alert.id)}
                  >
                    <span className={`severity ${alert.severity}`}>
                      {t(`severityCodes.${alert.severity}`, { defaultValue: alert.severity })}
                    </span>
                    <div>
                      <strong>
                        {alert.title}
                        {alert.triage_status !== "UNREVIEWED" && (
                          <span
                            className="demo-badge"
                            style={{ marginLeft: "8px", verticalAlign: "middle" }}
                          >
                            {t(`triageStatus.${alert.triage_status}`, {
                              defaultValue: alert.triage_status,
                            })}
                          </span>
                        )}
                      </strong>
                      <small>
                        {alert.source} · {alert.category}
                      </small>
                    </div>
                    {alert.is_simulated ? (
                      <span className="demo-badge">{t("simulated")}</span>
                    ) : (
                      <span />
                    )}
                    <div style={{ display: "flex", alignItems: "center", gap: "10px", justifyContent: "flex-end" }}>
                      <time dateTime={alert.observed_at}>
                        {new Date(alert.observed_at).toLocaleString(i18n.language)}
                      </time>
                      <button
                        type="button"
                        className="ghost"
                        style={{ minHeight: "auto", padding: "4px 8px", fontSize: "0.75rem" }}
                        onClick={(e) => {
                          e.stopPropagation();
                          setExpandedAlertId(isExpanded ? null : alert.id);
                        }}
                      >
                        {isExpanded ? t("hideDetails") : t("showDetails")}
                      </button>
                    </div>
                    {isExpanded && (
                      <div
                        className="analysis-card"
                        style={{ gridColumn: "1 / -1", marginTop: "12px", opacity: 1 }}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                          <strong>{t("alertDetails")}</strong>
                          <button
                            type="button"
                            className="ghost"
                            style={{ minHeight: "auto", padding: "4px 10px", fontSize: "0.8rem" }}
                            onClick={() => setExpandedAlertId(null)}
                          >
                            ✕ {t("close")}
                          </button>
                        </div>
                        <div className="connector-grid">
                          <div>
                            <strong>{t("externalId")}</strong>
                            <small>{alert.external_id || alert.id}</small>
                          </div>
                          <div>
                            <strong>{t("provenance")}</strong>
                            <small>{alert.provenance || alert.source}</small>
                          </div>
                          <div>
                            <strong>{t("assetSummary")}</strong>
                            <small>{alert.asset_summary || t("noParameters")}</small>
                          </div>
                          <div>
                            <strong>{t("identitySummary")}</strong>
                            <small>{alert.identity_summary || t("noParameters")}</small>
                          </div>
                          <div>
                            <strong>{t("indicatorSummary")}</strong>
                            <small>{alert.indicator_summary || t("noParameters")}</small>
                          </div>
                        </div>
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          </section>

          <section className="panel">
            <div>
              <p className="eyebrow">{t("traceability")}</p>
              <h2>{t("correlations")}</h2>
              <p>{t("correlationIntro")}</p>
            </div>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
                gap: "12px",
                marginTop: "1rem",
              }}
            >
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
                  <p style={{ margin: "4px 0" }}>
                    {t("members")}: {match.members.length}
                  </p>
                  {match.result_type === "LEGACY_SIMULATED_V0" && (
                    <small style={{ color: "var(--muted)" }}>{t("legacyCorrelation")}</small>
                  )}
                  <div className="correlation-factors" style={{ marginTop: "8px" }}>
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
      )}

      {activeTab === "threatIntel" && (
        <>
          <section style={{ display: "flex", flexDirection: "column", minHeight: "unset", gap: "1rem", marginBottom: "1.25rem", background: "var(--panel)", border: "1px solid var(--panel-border)", borderRadius: "8px", padding: "1.5rem" }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                flexWrap: "wrap",
                gap: "12px",
                borderBottom: "1px solid var(--line)",
                paddingBottom: "1rem",
              }}
            >
              <div>
                <p className="eyebrow">MITRE ATT&amp;CK</p>
                <h2 style={{ margin: "2px 0 0", fontSize: "1.25rem" }}>{t("threatEnrichment")}</h2>
                <p style={{ margin: "4px 0 0", color: "var(--muted)", fontSize: "0.85rem" }}>{t("threatEnrichmentIntro")}</p>
              </div>
              <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                <button
                  type="button"
                  className="ghost"
                  style={{ width: "auto", minWidth: "unset", height: "auto", padding: "6px 14px", fontSize: "0.825rem" }}
                  disabled={recalculateRisk.isPending}
                  onClick={() => recalculateRisk.mutate()}
                >
                  ⚡ {t("recalculateRisk")}
                </button>
                <button
                  type="button"
                  className="primary"
                  style={{ width: "auto", minWidth: "unset", height: "auto", padding: "6px 14px", fontSize: "0.825rem" }}
                  disabled={generateExplanation.isPending || !enrichment.data}
                  onClick={() => generateExplanation.mutate()}
                >
                  🤖 {t("redactWithAi")}
                </button>
              </div>
            </div>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
                gap: "12px",
              }}
            >
              {enrichment.data && (
                <>
                  <article className="claim-card analysis-card" style={{ gridColumn: "1 / -1" }}>
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
                    <div className="correlation-factors" style={{ margin: "8px 0" }}>
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

          <section className="panel">
            <div>
              <p className="eyebrow">{t("traceability")}</p>
              <h2>{t("knowledgeClaims")}</h2>
              <p>{t("knowledgeClaimsIntro")}</p>
            </div>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
                gap: "12px",
                marginTop: "1rem",
              }}
            >
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
                    <p style={{ margin: "6px 0" }}>{statement}</p>
                    {claim.confidence !== null && (
                      <small style={{ color: "var(--muted)" }}>
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
        </>
      )}

      {activeTab === "audit" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
          <section className="panel">
            <div>
              <p className="eyebrow">{t("traceability")}</p>
              <h2>{t("executionHistory")}</h2>
              <p>{t("decisionsIntro")}</p>
            </div>

            <div style={{ marginTop: "1rem" }}>
              <h3 style={{ fontSize: "1rem", marginBottom: "0.75rem" }}>
                ⚙️ Propuestas & Decisiones de Gobernanza de Playbooks
              </h3>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))",
                  gap: "12px",
                }}
              >
                {responseDecisions.data?.map((decision) => {
                  const isCompleted = ["AUTHORIZED", "ROLLED_BACK", "EXECUTED"].includes(decision.status) || decision.approval_status === "APPROVED";
                  const countApproved = isCompleted ? 2 : Math.max(decision.decisions.filter((d) => d.decision === "APPROVE").length, 0);
                  const totalApprovals = 2;
                  return (
                    <article className="claim-card" key={decision.id} style={{ borderLeft: "3px solid var(--accent)" }}>
                      <div className="claim-badges" style={{ marginBottom: "8px" }}>
                        <span className="severity">{decision.status}</span>
                        <span>{decision.impact}</span>
                        {decision.is_simulated && <span>{t("simulated")}</span>}
                      </div>
                      <strong style={{ fontSize: "1.05rem", display: "block", marginBottom: "4px" }}>
                        {decision.action_type}
                      </strong>
                      <div style={{ background: "var(--panel-raised)", padding: "6px 10px", borderRadius: "4px", margin: "6px 0", fontSize: "0.825rem" }}>
                        🎯 <span style={{ color: "var(--muted)" }}>Target:</span>{" "}
                        <strong style={{ fontFamily: "var(--font-mono, monospace)" }}>
                          {decision.targets && decision.targets.length > 0 ? decision.targets.join(", ") : "synthetic-demo-user"}
                        </strong>
                      </div>
                      <small style={{ color: "var(--text-soft)", display: "block", marginTop: "4px" }}>
                        📅 {new Date(decision.created_at).toLocaleString(i18n.language)}
                      </small>
                      <small style={{ color: "var(--muted)", display: "block", marginTop: "2px" }}>
                        Aprobaciones: {countApproved}/{totalApprovals} {isCompleted && <span style={{ color: "var(--accent)", marginLeft: "4px" }}>✓ Aprobado por 4-Ojos</span>} · Evaluación: {decision.evaluation_outcome}
                      </small>
                      {decision.approval_request_id && decision.approval_status === "PENDING" && (
                        currentUser.data?.id !== decision.requester_user_id ? (
                          <div style={{ display: "flex", gap: "8px", marginTop: "10px" }}>
                            <button
                              type="button"
                              style={{ flex: 1, padding: "4px 8px", fontSize: "0.8rem" }}
                              disabled={approvalDecision.isPending}
                              onClick={() =>
                                approvalDecision.mutate({
                                  requestId: decision.approval_request_id!,
                                  decision: "APPROVE",
                                  fingerprint: decision.fingerprint,
                                })
                              }
                            >
                              ✓ {t("approveResponse")}
                            </button>
                            <button
                              type="button"
                              className="ghost"
                              style={{ flex: 1, padding: "4px 8px", fontSize: "0.8rem" }}
                              disabled={approvalDecision.isPending}
                              onClick={() =>
                                approvalDecision.mutate({
                                  requestId: decision.approval_request_id!,
                                  decision: "REJECT",
                                  fingerprint: decision.fingerprint,
                                })
                              }
                            >
                              ✕ {t("rejectResponse")}
                            </button>
                          </div>
                        ) : (
                          <p style={{ margin: "8px 0 0", fontSize: "0.8rem", color: "var(--text-soft)", background: "var(--panel-raised)", padding: "6px 10px", borderRadius: "4px" }}>
                            🔒 {t("awaitingSecondAnalystNotice", { defaultValue: "Esperando aprobación de un 2º analista (Principio 4-Ojos)" })}
                          </p>
                        )
                      )}
                    </article>
                  );
                })}
                <PageState
                  loading={responseDecisions.isLoading}
                  error={responseDecisions.isError}
                  empty={!responseDecisions.isLoading && !responseDecisions.isError && responseDecisions.data?.length === 0}
                />
              </div>
            </div>

            {(playbookExecutions.data?.length ?? 0) > 0 && (
              <div style={{ marginTop: "1.5rem" }}>
                <h3 style={{ fontSize: "1rem", marginBottom: "0.75rem" }}>
                  ▶️ Instancias de Ejecución de Playbooks
                </h3>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
                    gap: "12px",
                  }}
                >
                  {playbookExecutions.data?.map((execution) => (
                    <article className="claim-card" key={execution.id}>
                      <div className="claim-badges">
                        <span>{execution.status}</span>
                        <span>{execution.execution_mode}</span>
                      </div>
                      <strong style={{ display: "block", margin: "6px 0", fontFamily: "var(--font-mono, monospace)", fontSize: "0.85rem" }}>
                        {execution.id}
                      </strong>
                      <small style={{ color: "var(--muted)" }}>
                        📅 {new Date(execution.created_at).toLocaleString(i18n.language)}
                      </small>
                      {execution.error_code && <p style={{ color: "var(--status-error)", margin: "4px 0 0" }}>{execution.error_code}</p>}
                    </article>
                  ))}
                </div>
              </div>
            )}
          </section>
        </div>
      )}
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
  
  // Interactive Connection Modal & Category Filter state
  const [activeConn, setActiveConn] = useState<ConnectionMeta | null>(null);
  const [modalMode, setModalMode] = useState<"config" | "test">("config");
  const [selectedCategory, setSelectedCategory] = useState<string>("ALL");

  const openModal = (conn: ConnectionMeta, mode: "config" | "test") => {
    setActiveConn(conn);
    setModalMode(mode);
  };

  return (
    <>
      <div className="page-title">
        <div>
          <p className="eyebrow">{t("securityDataSources")}</p>
          <h1>{t("integrations")}</h1>
          <p className="muted">Gestión de Conexiones, Secretos Cifrados y Resoluctor de Capacidades SOAR</p>
        </div>
      </div>
      <PageState
        loading={health.isLoading}
        error={health.isError}
        empty={!health.isLoading && !health.isError && health.data?.length === 0}
      />

      {/* Hero Executive Summary Header */}
      <section
        style={{
          marginBottom: "1.5rem",
          background: "var(--panel)",
          border: "1px solid var(--panel-border)",
          borderRadius: "8px",
          padding: "1.25rem 1.5rem",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px", marginBottom: "1rem" }}>
          <div>
            <span style={{ fontSize: "0.75rem", color: "var(--accent)", fontWeight: 700, letterSpacing: "0.05em", textTransform: "uppercase" }}>
              ARCHITECTURAL SINGLE SOURCE OF TRUTH
            </span>
            <h2 style={{ margin: "2px 0 0", fontSize: "1.3rem" }}>
              🏛️ Biblioteca de Conexiones & Secretos del Tenant
            </h2>
            <p style={{ margin: "4px 0 0", fontSize: "0.85rem", color: "var(--muted)" }}>
              Catálogo centralizado de conectores, credenciales cifradas por tenant (AES-256-GCM) y resoluctor de capacidades SOAR.
            </p>
          </div>
          <span style={{ fontSize: "0.75rem", background: "rgba(13, 209, 155, 0.1)", color: "var(--accent)", padding: "6px 12px", borderRadius: "6px", fontWeight: 700, border: "1px solid rgba(13, 209, 155, 0.2)" }}>
            🔒 AES-256-GCM ENCRYPTED
          </span>
        </div>

        {/* 4 Summary Metric Pills */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "10px" }}>
          <div style={{ background: "var(--panel-raised)", padding: "10px 14px", borderRadius: "6px", border: "1px solid var(--line)" }}>
            <span style={{ fontSize: "0.75rem", color: "var(--muted)", textTransform: "uppercase" }}>Total Conexiones</span>
            <strong style={{ display: "block", fontSize: "1.2rem", color: "var(--text)", marginTop: "2px" }}>9 Configuradas</strong>
          </div>
          <div style={{ background: "var(--panel-raised)", padding: "10px 14px", borderRadius: "6px", border: "1px solid var(--line)" }}>
            <span style={{ fontSize: "0.75rem", color: "var(--muted)", textTransform: "uppercase" }}>Estado de Salud</span>
            <strong style={{ display: "block", fontSize: "1.2rem", color: "var(--accent)", marginTop: "2px" }}>● 9 Saludables</strong>
          </div>
          <div style={{ background: "var(--panel-raised)", padding: "10px 14px", borderRadius: "6px", border: "1px solid var(--line)" }}>
            <span style={{ fontSize: "0.75rem", color: "var(--muted)", textTransform: "uppercase" }}>Ambiente de Lab</span>
            <strong style={{ display: "block", fontSize: "1.2rem", color: "#ffb703", marginTop: "2px" }}>3 Conectores Lab</strong>
          </div>
          <div style={{ background: "var(--panel-raised)", padding: "10px 14px", borderRadius: "6px", border: "1px solid var(--line)" }}>
            <span style={{ fontSize: "0.75rem", color: "var(--muted)", textTransform: "uppercase" }}>Gestor de Secretos</span>
            <strong style={{ display: "block", fontSize: "1.2rem", color: "var(--text)", marginTop: "2px" }}>SecretCipher DB</strong>
          </div>
        </div>
      </section>

      {/* Connection Type Filter Bar */}
      <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "1.5rem", flexWrap: "wrap" }}>
        <span style={{ fontSize: "0.85rem", color: "var(--muted)", fontWeight: 600 }}>Filtrar por tipo de conexión:</span>
        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
          {[
            { id: "ALL", label: "Todas" },
            { id: "SIEM", label: "🛡️ SIEM & Evidencias" },
            { id: "AI_SOAR", label: "🧠 IA & Automatización" },
            { id: "LAB_IDENTITY", label: "🔒 Identidad & Lab" },
            { id: "ENTERPRISE", label: "🌐 Enterprise & EDR" },
          ].map((cat) => {
            const isSelected = selectedCategory === cat.id;
            return (
              <button
                key={cat.id}
                type="button"
                onClick={() => setSelectedCategory(cat.id)}
                style={{
                  width: "auto",
                  minWidth: "unset",
                  height: "auto",
                  padding: "6px 14px",
                  fontSize: "0.825rem",
                  borderRadius: "6px",
                  border: isSelected ? "1px solid var(--accent)" : "1px solid var(--line)",
                  background: isSelected ? "rgba(13, 209, 155, 0.15)" : "var(--panel)",
                  color: isSelected ? "var(--accent)" : "var(--text)",
                  fontWeight: isSelected ? 700 : 500,
                  cursor: "pointer",
                  whiteSpace: "nowrap",
                  transition: "all 0.15s ease",
                }}
              >
                {cat.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Category 1: Fuentes de Seguridad & SIEM */}
      {(selectedCategory === "ALL" || selectedCategory === "SIEM") && (
        <div style={{ marginBottom: "1.5rem" }}>
          <h3 style={{ fontSize: "1rem", color: "var(--text)", marginBottom: "0.75rem", display: "flex", alignItems: "center", gap: "8px" }}>
            <span>🛡️</span> Fuentes de Seguridad, SIEM & Evidencias Forenses
          </h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: "1rem" }}>
            {/* Wazuh */}
            <div style={{ background: "var(--panel)", border: "1px solid var(--line)", borderRadius: "8px", padding: "1rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                <strong style={{ fontSize: "0.95rem" }}>Wazuh SIEM Manager</strong>
                <span style={{ fontSize: "0.7rem", color: "var(--accent)", fontWeight: 700, background: "rgba(13, 209, 155, 0.1)", padding: "2px 6px", borderRadius: "4px" }}>ACTIVE</span>
              </div>
              <p style={{ fontSize: "0.8rem", color: "var(--muted)", margin: "0 0 10px" }}>
                Conector: <code>wazuh</code> · Ambiente: <span style={{ color: "var(--text)" }}>Producción / Lab</span>
              </p>
              <div style={{ fontSize: "0.75rem", background: "#06120f", padding: "6px 8px", borderRadius: "4px", marginBottom: "10px", fontFamily: "monospace", color: "var(--accent)" }}>
                security.alert.read, security.evidence.retrieve
              </div>
              <div style={{ display: "flex", gap: "6px" }}>
                <button type="button" className="ghost" style={{ fontSize: "0.75rem", padding: "4px 10px" }} onClick={() => openModal({ id: "wazuh", name: "Wazuh SIEM Manager", connectorType: "wazuh", environment: "Producción / Lab", capabilities: "security.alert.read, security.evidence.retrieve", defaultUrl: "https://127.0.0.1:55000", secretLabel: "Wazuh API User / Password" }, "config")}>🔑 Credenciales</button>
                <button type="button" className="ghost" style={{ fontSize: "0.75rem", padding: "4px 10px" }} onClick={() => openModal({ id: "wazuh", name: "Wazuh SIEM Manager", connectorType: "wazuh", environment: "Producción / Lab", capabilities: "security.alert.read, security.evidence.retrieve" }, "test")}>⚡ Probar Conexión</button>
              </div>
            </div>

            {/* OpenSearch */}
            <div style={{ background: "var(--panel)", border: "1px solid var(--line)", borderRadius: "8px", padding: "1rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                <strong style={{ fontSize: "0.95rem" }}>OpenSearch Indexer</strong>
                <span style={{ fontSize: "0.7rem", color: "var(--accent)", fontWeight: 700, background: "rgba(13, 209, 155, 0.1)", padding: "2px 6px", borderRadius: "4px" }}>ACTIVE</span>
              </div>
              <p style={{ fontSize: "0.8rem", color: "var(--muted)", margin: "0 0 10px" }}>
                Conector: <code>opensearch</code> · Ambiente: <span style={{ color: "var(--text)" }}>Producción</span>
              </p>
              <div style={{ fontSize: "0.75rem", background: "#06120f", padding: "6px 8px", borderRadius: "4px", marginBottom: "10px", fontFamily: "monospace", color: "var(--accent)" }}>
                security.evidence.search
              </div>
              <div style={{ display: "flex", gap: "6px" }}>
                <button type="button" className="ghost" style={{ fontSize: "0.75rem", padding: "4px 10px" }} onClick={() => openModal({ id: "opensearch", name: "OpenSearch Indexer", connectorType: "opensearch", environment: "Producción", capabilities: "security.evidence.search", defaultUrl: "http://127.0.0.1:9200", secretLabel: "Cluster Auth Key" }, "config")}>🔑 Credenciales</button>
                <button type="button" className="ghost" style={{ fontSize: "0.75rem", padding: "4px 10px" }} onClick={() => openModal({ id: "opensearch", name: "OpenSearch Indexer", connectorType: "opensearch", environment: "Producción", capabilities: "security.evidence.search" }, "test")}>⚡ Probar Conexión</button>
              </div>
            </div>

            {/* MISP */}
            <div style={{ background: "var(--panel)", border: "1px solid var(--line)", borderRadius: "8px", padding: "1rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                <strong style={{ fontSize: "0.95rem" }}>MISP Threat Intelligence</strong>
                <span style={{ fontSize: "0.7rem", color: "var(--accent)", fontWeight: 700, background: "rgba(13, 209, 155, 0.1)", padding: "2px 6px", borderRadius: "4px" }}>ACTIVE</span>
              </div>
              <p style={{ fontSize: "0.8rem", color: "var(--muted)", margin: "0 0 10px" }}>
                Conector: <code>misp</code> · Ambiente: <span style={{ color: "var(--text)" }}>Producción</span>
              </p>
              <div style={{ fontSize: "0.75rem", background: "#06120f", padding: "6px 8px", borderRadius: "4px", marginBottom: "10px", fontFamily: "monospace", color: "var(--accent)" }}>
                threatintel.indicator.search
              </div>
              <div style={{ display: "flex", gap: "6px" }}>
                <button type="button" className="ghost" style={{ fontSize: "0.75rem", padding: "4px 10px" }} onClick={() => openModal({ id: "misp", name: "MISP Threat Intelligence", connectorType: "misp", environment: "Producción", capabilities: "threatintel.indicator.search", defaultUrl: "https://misp.local/attributes/restSearch", secretLabel: "MISP Auth Key" }, "config")}>🔑 Credenciales API Key</button>
                <button type="button" className="ghost" style={{ fontSize: "0.75rem", padding: "4px 10px" }} onClick={() => openModal({ id: "misp", name: "MISP Threat Intelligence", connectorType: "misp", environment: "Producción", capabilities: "threatintel.indicator.search" }, "test")}>⚡ Probar Conexión</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Category 2: IA & Automatización */}
      {(selectedCategory === "ALL" || selectedCategory === "AI_SOAR") && (
        <div style={{ marginBottom: "1.5rem" }}>
          <h3 style={{ fontSize: "1rem", color: "var(--text)", marginBottom: "0.75rem", display: "flex", alignItems: "center", gap: "8px" }}>
            <span>🧠</span> Inteligencia Artificial & Automatización SOAR
          </h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: "1rem" }}>
            {/* Ollama */}
            <div style={{ background: "var(--panel)", border: "1px solid var(--line)", borderRadius: "8px", padding: "1rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                <strong style={{ fontSize: "0.95rem" }}>Ollama AI Engine (Gemma 4)</strong>
                <span style={{ fontSize: "0.7rem", color: "var(--accent)", fontWeight: 700, background: "rgba(13, 209, 155, 0.1)", padding: "2px 6px", borderRadius: "4px" }}>ACTIVE</span>
              </div>
              <p style={{ fontSize: "0.8rem", color: "var(--muted)", margin: "0 0 10px" }}>
                Conector: <code>ollama</code> · Ambiente: <span style={{ color: "var(--text)" }}>Local On-Premise</span>
              </p>
              <div style={{ fontSize: "0.75rem", background: "#06120f", padding: "6px 8px", borderRadius: "4px", marginBottom: "10px", fontFamily: "monospace", color: "var(--accent)" }}>
                ai.inference.execute
              </div>
              <div style={{ display: "flex", gap: "6px" }}>
                <button type="button" className="ghost" style={{ fontSize: "0.75rem", padding: "4px 10px" }} onClick={() => openModal({ id: "ollama", name: "Ollama AI Engine (Gemma 4)", connectorType: "ollama", environment: "Local On-Premise", capabilities: "ai.inference.execute", defaultUrl: "http://127.0.0.1:11434", secretLabel: "API Token / Key (Opcional)" }, "config")}>🔑 Endpoint & Model</button>
                <button type="button" className="ghost" style={{ fontSize: "0.75rem", padding: "4px 10px" }} onClick={() => openModal({ id: "ollama", name: "Ollama AI Engine (Gemma 4)", connectorType: "ollama", environment: "Local On-Premise", capabilities: "ai.inference.execute" }, "test")}>⚡ Probar Conexión</button>
              </div>
            </div>

            {/* n8n */}
            <div style={{ background: "var(--panel)", border: "1px solid var(--line)", borderRadius: "8px", padding: "1rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                <strong style={{ fontSize: "0.95rem" }}>n8n Workflows Engine</strong>
                <span style={{ fontSize: "0.7rem", color: "var(--accent)", fontWeight: 700, background: "rgba(13, 209, 155, 0.1)", padding: "2px 6px", borderRadius: "4px" }}>ACTIVE</span>
              </div>
              <p style={{ fontSize: "0.8rem", color: "var(--muted)", margin: "0 0 10px" }}>
                Conector: <code>n8n</code> · Ambiente: <span style={{ color: "var(--text)" }}>Producción / Lab</span>
              </p>
              <div style={{ fontSize: "0.75rem", background: "#06120f", padding: "6px 8px", borderRadius: "4px", marginBottom: "10px", fontFamily: "monospace", color: "var(--accent)" }}>
                automation.workflow.execute
              </div>
              <div style={{ display: "flex", gap: "6px" }}>
                <button type="button" className="ghost" style={{ fontSize: "0.75rem", padding: "4px 10px" }} onClick={() => openModal({ id: "n8n", name: "n8n Workflows Engine", connectorType: "n8n", environment: "Producción / Lab", capabilities: "automation.workflow.execute", defaultUrl: "http://127.0.0.1:5678", secretLabel: "X-N8N-API-KEY" }, "config")}>🔑 Credenciales API Key</button>
                <button type="button" className="ghost" style={{ fontSize: "0.75rem", padding: "4px 10px" }} onClick={() => openModal({ id: "n8n", name: "n8n Workflows Engine", connectorType: "n8n", environment: "Producción / Lab", capabilities: "automation.workflow.execute" }, "test")}>⚡ Probar Conexión</button>
              </div>
            </div>

            {/* ServiceNow */}
            <div style={{ background: "var(--panel)", border: "1px solid var(--line)", borderRadius: "8px", padding: "1rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                <strong style={{ fontSize: "0.95rem" }}>ServiceNow ITSM / SecOps</strong>
                <span style={{ fontSize: "0.7rem", color: "var(--accent)", fontWeight: 700, background: "rgba(13, 209, 155, 0.1)", padding: "2px 6px", borderRadius: "4px" }}>ENTERPRISE</span>
              </div>
              <p style={{ fontSize: "0.8rem", color: "var(--muted)", margin: "0 0 10px" }}>
                Conector: <code>servicenow</code> · Ambiente: <span style={{ color: "var(--text)" }}>Producción</span>
              </p>
              <div style={{ fontSize: "0.75rem", background: "#06120f", padding: "6px 8px", borderRadius: "4px", marginBottom: "10px", fontFamily: "monospace", color: "var(--accent)" }}>
                ticket.create, ticket.update
              </div>
              <div style={{ display: "flex", gap: "6px" }}>
                <button type="button" className="ghost" style={{ fontSize: "0.75rem", padding: "4px 10px" }} onClick={() => openModal({ id: "servicenow", name: "ServiceNow ITSM / SecOps", connectorType: "servicenow", environment: "Producción", capabilities: "ticket.create, ticket.update", defaultUrl: "https://instance.service-now.com/api/now/table/incident", secretLabel: "Basic Auth / OAuth Token" }, "config")}>🔑 Credenciales Basic/OAuth</button>
                <button type="button" className="ghost" style={{ fontSize: "0.75rem", padding: "4px 10px" }} onClick={() => openModal({ id: "servicenow", name: "ServiceNow ITSM / SecOps", connectorType: "servicenow", environment: "Producción", capabilities: "ticket.create, ticket.update" }, "test")}>⚡ Probar Conexión</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Category 3: Identidad, Red & Aislamiento Local (Lab) */}
      {(selectedCategory === "ALL" || selectedCategory === "LAB_IDENTITY") && (
        <div style={{ marginBottom: "1.5rem" }}>
          <h3 style={{ fontSize: "1rem", color: "var(--text)", marginBottom: "0.75rem", display: "flex", alignItems: "center", gap: "8px" }}>
            <span>🔒</span> Identidad, Notificaciones & Respuesta Local (Laboratorio)
          </h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: "1rem" }}>
            {/* SMTP Lab */}
            <div style={{ background: "var(--panel)", border: "1px solid var(--line)", borderRadius: "8px", padding: "1rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                <strong style={{ fontSize: "0.95rem" }}>SMTP Lab Mailer</strong>
                <span style={{ fontSize: "0.7rem", color: "#ffb703", fontWeight: 700, background: "rgba(255, 183, 3, 0.1)", padding: "2px 6px", borderRadius: "4px" }}>LABORATORY</span>
              </div>
              <p style={{ fontSize: "0.8rem", color: "var(--muted)", margin: "0 0 10px" }}>
                Conector: <code>smtp_lab</code> · Ambiente: <span style={{ color: "var(--text)" }}>Laboratory</span>
              </p>
              <div style={{ fontSize: "0.75rem", background: "#06120f", padding: "6px 8px", borderRadius: "4px", marginBottom: "10px", fontFamily: "monospace", color: "var(--accent)" }}>
                notification.email.send
              </div>
              <div style={{ display: "flex", gap: "6px" }}>
                <button type="button" className="ghost" style={{ fontSize: "0.75rem", padding: "4px 10px" }} onClick={() => openModal({ id: "smtp_lab", name: "SMTP Lab Mailer", connectorType: "smtp_lab", environment: "Laboratory", capabilities: "notification.email.send", defaultUrl: "smtp://127.0.0.1:1025", secretLabel: "SMTP Auth Password" }, "config")}>🔑 Configuración SMTP</button>
                <button type="button" className="ghost" style={{ fontSize: "0.75rem", padding: "4px 10px" }} onClick={() => openModal({ id: "smtp_lab", name: "SMTP Lab Mailer", connectorType: "smtp_lab", environment: "Laboratory", capabilities: "notification.email.send" }, "test")}>⚡ Probar Conexión</button>
              </div>
            </div>

            {/* Windows Local Account */}
            <div style={{ background: "var(--panel)", border: "1px solid var(--line)", borderRadius: "8px", padding: "1rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                <strong style={{ fontSize: "0.95rem" }}>Windows Local Account (Lab)</strong>
                <span style={{ fontSize: "0.7rem", color: "#ffb703", fontWeight: 700, background: "rgba(255, 183, 3, 0.1)", padding: "2px 6px", borderRadius: "4px" }}>LABORATORY</span>
              </div>
              <p style={{ fontSize: "0.8rem", color: "var(--muted)", margin: "0 0 10px" }}>
                Conector: <code>windows_local</code> · Ambiente: <span style={{ color: "var(--text)" }}>Laboratory</span>
              </p>
              <div style={{ fontSize: "0.75rem", background: "#06120f", padding: "6px 8px", borderRadius: "4px", marginBottom: "10px", fontFamily: "monospace", color: "#ffb703" }}>
                identity.local_user.disable (Req. Aprobación)
              </div>
              <div style={{ display: "flex", gap: "6px" }}>
                <button type="button" className="ghost" style={{ fontSize: "0.75rem", padding: "4px 10px" }} onClick={() => openModal({ id: "windows_local", name: "Windows Local Account (Lab)", connectorType: "windows_local", environment: "Laboratory", capabilities: "identity.local_user.disable", defaultUrl: "http://127.0.0.1:8000/api/v1/windows-local", secretLabel: "Local Admin Credential Token" }, "config")}>🔑 Credenciales</button>
                <button type="button" className="ghost" style={{ fontSize: "0.75rem", padding: "4px 10px" }} onClick={() => openModal({ id: "windows_local", name: "Windows Local Account (Lab)", connectorType: "windows_local", environment: "Laboratory", capabilities: "identity.local_user.disable" }, "test")}>⚡ Probar Conexión</button>
              </div>
            </div>

            {/* Windows Local Firewall */}
            <div style={{ background: "var(--panel)", border: "1px solid var(--line)", borderRadius: "8px", padding: "1rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                <strong style={{ fontSize: "0.95rem" }}>Windows Local Firewall (Lab)</strong>
                <span style={{ fontSize: "0.7rem", color: "#ffb703", fontWeight: 700, background: "rgba(255, 183, 3, 0.1)", padding: "2px 6px", borderRadius: "4px" }}>LABORATORY</span>
              </div>
              <p style={{ fontSize: "0.8rem", color: "var(--muted)", margin: "0 0 10px" }}>
                Conector: <code>windows_firewall</code> · Ambiente: <span style={{ color: "var(--text)" }}>Laboratory</span>
              </p>
              <div style={{ fontSize: "0.75rem", background: "#06120f", padding: "6px 8px", borderRadius: "4px", marginBottom: "10px", fontFamily: "monospace", color: "#ffb703" }}>
                network.local_firewall.rule.create (Req. Aprobación)
              </div>
              <div style={{ display: "flex", gap: "6px" }}>
                <button type="button" className="ghost" style={{ fontSize: "0.75rem", padding: "4px 10px" }} onClick={() => openModal({ id: "windows_firewall", name: "Windows Local Firewall (Lab)", connectorType: "windows_firewall", environment: "Laboratory", capabilities: "network.local_firewall.rule.create", defaultUrl: "http://127.0.0.1:8000/api/v1/windows-firewall", secretLabel: "Rule Policy Authorization Secret" }, "config")}>🔑 Configuración</button>
                <button type="button" className="ghost" style={{ fontSize: "0.75rem", padding: "4px 10px" }} onClick={() => openModal({ id: "windows_firewall", name: "Windows Local Firewall (Lab)", connectorType: "windows_firewall", environment: "Laboratory", capabilities: "network.local_firewall.rule.create" }, "test")}>⚡ Probar Conexión</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Category 4: Conectores Perimetrales Enterprise & EDR */}
      {(selectedCategory === "ALL" || selectedCategory === "ENTERPRISE") && (
        <div style={{ marginBottom: "1.5rem" }}>
          <h3 style={{ fontSize: "1rem", color: "var(--text)", marginBottom: "0.75rem", display: "flex", alignItems: "center", gap: "8px" }}>
            <span>🌐</span> Conectores Perimetrales Enterprise & EDR
          </h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: "1rem" }}>
            {/* Microsoft Defender EDR */}
            <div style={{ background: "var(--panel)", border: "1px solid var(--line)", borderRadius: "8px", padding: "1rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                <strong style={{ fontSize: "0.95rem" }}>Microsoft Defender EDR</strong>
                <span style={{ fontSize: "0.7rem", color: "var(--accent)", fontWeight: 700, background: "rgba(13, 209, 155, 0.1)", padding: "2px 6px", borderRadius: "4px" }}>ENTERPRISE</span>
              </div>
              <p style={{ fontSize: "0.8rem", color: "var(--muted)", margin: "0 0 10px" }}>
                Conector: <code>defender</code> · Ambiente: <span style={{ color: "var(--text)" }}>Producción</span>
              </p>
              <div style={{ fontSize: "0.75rem", background: "#06120f", padding: "6px 8px", borderRadius: "4px", marginBottom: "10px", fontFamily: "monospace", color: "#ffb703" }}>
                endpoint.isolate, endpoint.release
              </div>
              <div style={{ display: "flex", gap: "6px" }}>
                <button type="button" className="ghost" style={{ fontSize: "0.75rem", padding: "4px 10px" }} onClick={() => openModal({ id: "defender", name: "Microsoft Defender EDR", connectorType: "defender", environment: "Producción", capabilities: "endpoint.isolate, endpoint.release", defaultUrl: "https://api.securitycenter.microsoft.com", secretLabel: "Client Secret / OAuth2 Token" }, "config")}>🔑 Credenciales OAuth2</button>
                <button type="button" className="ghost" style={{ fontSize: "0.75rem", padding: "4px 10px" }} onClick={() => openModal({ id: "defender", name: "Microsoft Defender EDR", connectorType: "defender", environment: "Producción", capabilities: "endpoint.isolate, endpoint.release" }, "test")}>⚡ Probar Conexión</button>
              </div>
            </div>

            {/* Palo Alto PA-3200 */}
            <div style={{ background: "var(--panel)", border: "1px solid var(--line)", borderRadius: "8px", padding: "1rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                <strong style={{ fontSize: "0.95rem" }}>Palo Alto PA-3200 Firewall</strong>
                <span style={{ fontSize: "0.7rem", color: "var(--accent)", fontWeight: 700, background: "rgba(13, 209, 155, 0.1)", padding: "2px 6px", borderRadius: "4px" }}>ENTERPRISE</span>
              </div>
              <p style={{ fontSize: "0.8rem", color: "var(--muted)", margin: "0 0 10px" }}>
                Conector: <code>palo_alto</code> · Ambiente: <span style={{ color: "var(--text)" }}>Producción</span>
              </p>
              <div style={{ fontSize: "0.75rem", background: "#06120f", padding: "6px 8px", borderRadius: "4px", marginBottom: "10px", fontFamily: "monospace", color: "#ffb703" }}>
                network.ip.block, network.ip.unblock
              </div>
              <div style={{ display: "flex", gap: "6px" }}>
                <button type="button" className="ghost" style={{ fontSize: "0.75rem", padding: "4px 10px" }} onClick={() => openModal({ id: "palo_alto", name: "Palo Alto PA-3200 Firewall", connectorType: "palo_alto", environment: "Producción", capabilities: "network.ip.block, network.ip.unblock", defaultUrl: "https://panorama.local/api", secretLabel: "Panorama API Key" }, "config")}>🔑 Credenciales API Key</button>
                <button type="button" className="ghost" style={{ fontSize: "0.75rem", padding: "4px 10px" }} onClick={() => openModal({ id: "palo_alto", name: "Palo Alto PA-3200 Firewall", connectorType: "palo_alto", environment: "Producción", capabilities: "network.ip.block, network.ip.unblock" }, "test")}>⚡ Probar Conexión</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Render Modal when activeConn is selected */}
      {activeConn && (
        <ConnectionModal
          connection={activeConn}
          mode={modalMode}
          onClose={() => setActiveConn(null)}
        />
      )}
    </>
  );
}

function PlaybooksPage() {
  return <PlaybookLibraryPage />;
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
  const [activeSubTab, setActiveSubTab] = useState<"overview" | "users" | "rbac" | "directory" | "api-keys">("overview");

  return (
    <>
      <div className="page-title">
        <div>
          <p className="eyebrow">{t("controlPlane")}</p>
          <h1>{t("administration")}</h1>
          <p className="muted">Control de Identidades, Permisos RBAC, Integración LDAP/AD y Llaves de API</p>
        </div>
      </div>

      {failed && <p className="form-error">{t("permissionDenied")}</p>}
      {formError && <p className="form-error">{formError}</p>}

      <div className="admin-workspace-layout">
        {/* Sub-Sidebar Navigation */}
        <aside className="admin-sub-sidebar">
          <button
            type="button"
            className={`admin-sub-tab-button ${activeSubTab === "overview" ? "active" : ""}`}
            onClick={() => setActiveSubTab("overview")}
          >
            <span>Resumen General</span>
          </button>
          <button
            type="button"
            className={`admin-sub-tab-button ${activeSubTab === "users" ? "active" : ""}`}
            onClick={() => setActiveSubTab("users")}
          >
            <span>Usuarios & Cuentas</span>
            <span style={{ fontSize: "0.75rem", opacity: 0.8, fontWeight: 600 }}>({userOptions.data?.length ?? 0})</span>
          </button>
          <button
            type="button"
            className={`admin-sub-tab-button ${activeSubTab === "rbac" ? "active" : ""}`}
            onClick={() => setActiveSubTab("rbac")}
          >
            <span>Roles & RBAC</span>
            <span style={{ fontSize: "0.75rem", opacity: 0.8, fontWeight: 600 }}>({roles.data?.length ?? 0})</span>
          </button>
          <button
            type="button"
            className={`admin-sub-tab-button ${activeSubTab === "directory" ? "active" : ""}`}
            onClick={() => setActiveSubTab("directory")}
          >
            <span>Directorio LDAP / AD</span>
            <span style={{ fontSize: "0.65rem", padding: "2px 6px", borderRadius: "4px", background: directory.data ? "rgba(13,209,155,0.15)" : "rgba(255,255,255,0.08)", color: directory.data ? "var(--accent)" : "var(--muted)", fontWeight: 700, whiteSpace: "nowrap" }}>
              {directory.data ? "CONFIGURADO" : "PENDIENTE"}
            </span>
          </button>
          <button
            type="button"
            className={`admin-sub-tab-button ${activeSubTab === "api-keys" ? "active" : ""}`}
            onClick={() => setActiveSubTab("api-keys")}
          >
            <span>Claves API & Tokens</span>
          </button>
        </aside>

        {/* Dynamic Content Panel */}
        <main className="admin-content-panel">
          {/* SUB-TAB 1: OVERVIEW */}
          {activeSubTab === "overview" && (
            <>
              <section className="metrics" style={{ marginTop: 0 }}>
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

              <section className="panel admin-panel" id="audit-summary" style={{ marginTop: 0 }}>
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
          )}

          {/* SUB-TAB 2: USERS */}
          {activeSubTab === "users" && (
            <>
              <section className="admin-forms" style={{ marginTop: 0 }}>
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
              </section>

              <section className="panel admin-panel">
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
              </section>
            </>
          )}

          {/* SUB-TAB 3: RBAC ROLES & PERMISSIONS */}
          {activeSubTab === "rbac" && (
            <section className="admin-forms" style={{ marginTop: 0 }}>
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
          )}

          {/* SUB-TAB 4: DIRECTORY LDAP / ACTIVE DIRECTORY */}
          {activeSubTab === "directory" && (
            <form
              key={directory.data?.id ?? "directory-new"}
              className="panel directory-panel"
              onSubmit={submitDirectory}
              style={{ marginTop: 0 }}
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
          )}

          {/* SUB-TAB 5: API KEYS & TOKENS */}
          {activeSubTab === "api-keys" && (
            <ApiKeysPage />
          )}
        </main>
      </div>
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
          <Route path="memory" element={<GovernedMemoryPage />} />
          <Route path="api-keys" element={<ApiKeysPage />} />
          <Route path="audit" element={<AuditPage />} />
          <Route path="administration" element={<Administration />} />
        </Route>
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
