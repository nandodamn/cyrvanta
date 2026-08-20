import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { NavLink, Navigate, Outlet, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { z } from "zod";

import {
  Alert,
  addClaimPresentation,
  addIncidentTimelineEntry,
  assessClaim,
  activateDirectoryConfiguration,
  assignIncident,
  createRole,
  createIncident,
  createHumanClaim,
  createUser,
  proposePlaybookAction,
  decideResponse,
  analyzeIncident,
  directoryLogin,
  disableDirectoryConfiguration,
  downloadIncidentReport,
  executeAuthorizedResponse,
  generateIncidentExplanation,
  getAlerts,
  linkIncidentAlerts,
  AlertSeverity,
  AlertSort,
  getAuditEvents,
  getClaims,
  getCorrelations,
  getDirectoryConfiguration,
  getDirectoryGroupMappings,
  getIncident,
  getIncidentAlerts,
  getIncidentEnrichment,
  getIncidents,
  getMe,
  getPermissions,
  Permission,
  getPlaybookExecutions,
  getPlaybookDefinitions,
  getRolePermissions,
  getResponseDecisions,
  getRoles,
  getTenant,
  getTimeline,
  getUserRoles,
  getUserById,
  getUsers,
  linkUserDirectoryIdentity,
  login,
  recalculateIncidentRisk,
  relateClaim,
  replaceDirectoryGroupMappings,
  replaceRolePermissions,
  replaceUserPassword,
  replaceUserRoles,
  saveDirectoryConfiguration,
  testDirectoryConfiguration,
  transitionIncident,
  unlinkUserDirectoryIdentity,
  updateAlertTriage,
  updateIncident,
  updateUser,
} from "./api";
import { OperationalPulse } from "./OperationalPulse";
import { SecurityTopologyPanel } from "./SecurityTopologyPanel";
import { useAuth } from "./AuthContext";

const GovernedMemoryPage = lazy(() =>
  import("./GovernedMemoryPage").then((module) => ({ default: module.GovernedMemoryPage })),
);
const PlaybookLibraryPage = lazy(() =>
  import("./PlaybookLibraryPage").then((module) => ({ default: module.PlaybookLibraryPage })),
);
const VerifiedIntegrationsPage = lazy(() =>
  import("./VerifiedIntegrationsPage").then((module) => ({
    default: module.VerifiedIntegrationsPage,
  })),
);
const NAV_ITEMS: ReadonlyArray<{ to: string; icon: React.ReactNode; key: string; end?: boolean }> =
  [
    {
      to: "/",
      key: "overview",
      end: true,
      icon: (
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
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
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
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
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>
      ),
    },
    {
      to: "/playbooks",
      key: "playbooks",
      icon: (
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
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
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
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
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <ellipse cx="12" cy="5" rx="9" ry="3" />
          <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
          <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
        </svg>
      ),
    },

    {
      to: "/audit",
      key: "audit",
      icon: (
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
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
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
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
          <input
            autoComplete="organization"
            placeholder={t("tenantSlugPlaceholder")}
            {...register("tenantSlug")}
          />
        </label>
        <label>
          {authMode === "local" ? t("email") : t("directoryUsername")}
          <input
            type={authMode === "local" ? "email" : "text"}
            autoComplete="username"
            placeholder={
              authMode === "local" ? t("emailPlaceholder") : t("directoryUserPlaceholder")
            }
            {...register("email")}
          />
        </label>
        <label>
          {t("password")}
          <input
            type="password"
            autoComplete="current-password"
            placeholder="••••••••"
            {...register("password")}
          />
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

/** How an incident came to exist, read from its code prefix.
 *
 * The prefix already encoded this -- CORR- for correlation, RISK- for the
 * entity-risk sweep, INC- for one an analyst logged -- but only to someone who
 * knew the convention. An analyst reading the list should not have to.
 */
function incidentOriginKey(code: string): string {
  if (code.startsWith("CORR-")) return "incidentOriginCorrelated";
  if (code.startsWith("RISK-")) return "incidentOriginRisk";
  return "incidentOriginManual";
}

/** Assignee picker that searches as you type.
 *
 * The plain select loaded the first 100 users and listed them all. With more
 * than that, the hundred-and-first person simply could not be assigned and
 * nothing said so; with dozens, finding anyone meant scrolling a flat list.
 *
 * Search runs on the server (`GET /users?q=`), so the list never has to be
 * held in the browser and the cap stops mattering. The currently assigned
 * user is resolved separately from the search results: an incident assigned
 * to someone whose name you have not typed must still show who owns it.
 */
export function AssigneeCombobox({
  value,
  onChange,
  disabled,
}: {
  value: string;
  onChange: (userId: string) => void;
  disabled?: boolean;
}) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [highlighted, setHighlighted] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  // Typing must not fire a request per keystroke.
  useEffect(() => {
    const timer = setTimeout(() => setQuery(draft.trim()), 200);
    return () => clearTimeout(timer);
  }, [draft]);

  const results = useQuery({
    queryKey: ["users", "assignee-search", query],
    queryFn: () => getUsers({ query, pageSize: 20 }),
    enabled: open,
    retry: false,
  });

  // Resolved by id, not by search: an incident already assigned to someone
  // must name them on first render, and their name is not in a result set the
  // analyst has not typed yet.
  const assigned = useQuery({
    queryKey: ["users", "by-id", value],
    queryFn: () => getUserById(value),
    enabled: value !== "",
    retry: false,
  });

  const options = (results.data ?? []).filter((user) => user.is_active);
  const selected = options.find((user) => user.id === value) ?? assigned.data;

  useEffect(() => {
    if (!open) return;
    const onOutside = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onOutside);
    return () => document.removeEventListener("mousedown", onOutside);
  }, [open]);

  const choose = (userId: string) => {
    onChange(userId);
    setOpen(false);
    setDraft("");
  };

  const closedLabel = value
    ? selected
      ? `${selected.display_name} · ${selected.email}`
      : value
    : t("unassigned");

  return (
    <div ref={containerRef} className="combobox">
      <input
        type="text"
        role="combobox"
        aria-expanded={open}
        aria-controls="assignee-listbox"
        aria-autocomplete="list"
        disabled={disabled}
        placeholder={t("assigneeSearchPlaceholder")}
        value={open ? draft : closedLabel}
        onFocus={() => setOpen(true)}
        onChange={(event) => {
          setDraft(event.target.value);
          setHighlighted(0);
          setOpen(true);
        }}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown") {
            event.preventDefault();
            setOpen(true);
            setHighlighted((current) => Math.min(current + 1, options.length));
          } else if (event.key === "ArrowUp") {
            event.preventDefault();
            setHighlighted((current) => Math.max(current - 1, 0));
          } else if (event.key === "Enter" && open) {
            event.preventDefault();
            if (highlighted === 0) choose("");
            else if (options[highlighted - 1]) choose(options[highlighted - 1].id);
          } else if (event.key === "Escape") {
            setOpen(false);
            setDraft("");
          }
        }}
      />
      {open && (
        <ul className="combobox-list" id="assignee-listbox" role="listbox">
          <li
            role="option"
            aria-selected={value === ""}
            className={highlighted === 0 ? "is-highlighted" : undefined}
            onMouseEnter={() => setHighlighted(0)}
            onMouseDown={(event) => {
              event.preventDefault();
              choose("");
            }}
          >
            {t("unassigned")}
          </li>
          {results.isLoading && <li className="combobox-status">{t("loading")}</li>}
          {!results.isLoading && options.length === 0 && (
            <li className="combobox-status">{t("assigneeNoMatches")}</li>
          )}
          {options.map((user, index) => (
            <li
              key={user.id}
              role="option"
              aria-selected={user.id === value}
              className={highlighted === index + 1 ? "is-highlighted" : undefined}
              onMouseEnter={() => setHighlighted(index + 1)}
              onMouseDown={(event) => {
                event.preventDefault();
                choose(user.id);
              }}
            >
              <strong>{user.display_name}</strong>
              <span className="muted"> · {user.email}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Verbs that grant authority or do something that cannot be taken back.
 *
 * Marked in the permission list so an administrator handing out a role can see
 * at a glance which boxes change what someone may authorize or execute, rather
 * than reading fifty-five dotted codes with equal weight.
 */
const HIGH_IMPACT_VERBS = new Set([
  "approve",
  "activate",
  "cancel",
  "close",
  "disable",
  "execute",
  "manage",
  "publish",
  "retract",
  "revoke",
]);

function isHighImpact(code: string): boolean {
  return HIGH_IMPACT_VERBS.has(code.split(".").pop() ?? "");
}

/** Permission picker for a role.
 *
 * Every checkbox stays mounted even when filtered out of view. The form reads
 * its values with FormData.getAll, which only sees inputs that are in the DOM,
 * so rendering just the matches would silently strip every permission outside
 * the filter the moment someone searched and saved.
 */
export function PermissionMatrix({
  permissions,
  granted,
  readOnly,
}: {
  permissions: Permission[];
  granted: Set<string>;
  readOnly: boolean;
}) {
  const { t } = useTranslation();
  const [filter, setFilter] = useState("");
  // Controlled so each domain can show how many of its permissions are picked
  // and have that number move as boxes are ticked. The inputs keep their name
  // attribute, so the form still collects them with FormData.getAll.
  const [selected, setSelected] = useState<Set<string>>(granted);
  const needle = filter.trim().toLowerCase();

  const byDomain = new Map<string, Permission[]>();
  for (const permission of permissions) {
    const domain = permission.code.split(".")[0];
    byDomain.set(domain, [...(byDomain.get(domain) ?? []), permission]);
  }

  const label = (permission: Permission) =>
    // The stored description is written for whoever built the feature ("Read
    // epistemological claims"), and only in English. The catalogue entry says
    // the same thing in the reader's language and in operational terms; the
    // stored text remains the fallback so a new permission still shows
    // something rather than its bare code.
    t(`permissionCatalog.${permission.code}`, { defaultValue: permission.description });

  return (
    <>
      <label>
        <span className="muted">{t("permissionFilter")}</span>
        <input
          type="search"
          value={filter}
          placeholder={t("permissionFilterPlaceholder")}
          onChange={(event) => setFilter(event.target.value)}
        />
      </label>
      {[...byDomain.entries()]
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([domain, items]) => {
          const visible = items.filter(
            (permission) =>
              !needle ||
              permission.code.toLowerCase().includes(needle) ||
              label(permission).toLowerCase().includes(needle),
          );
          const picked = items.filter((permission) => selected.has(permission.id)).length;
          return (
            // Collapsed by default: fifty-six checkboxes at once is what makes
            // the screen unreadable. `details` keeps its children mounted while
            // closed, so nothing is lost from the form.
            <details
              key={domain}
              className="permission-group"
              hidden={visible.length === 0}
              open={Boolean(needle) || picked > 0}
            >
              <summary>
                <span className="permission-domain">
                  {t(`permissionDomain.${domain}`, { defaultValue: domain })}
                </span>
                <span className="permission-count">
                  {picked}/{items.length}
                </span>
              </summary>
              {items.map((permission) => (
                <label
                  className="check-row permission-row"
                  key={permission.id}
                  hidden={!visible.includes(permission)}
                >
                  <input
                    type="checkbox"
                    name="permission_ids"
                    value={permission.id}
                    checked={selected.has(permission.id)}
                    disabled={readOnly}
                    onChange={(event) =>
                      setSelected((current) => {
                        const next = new Set(current);
                        if (event.target.checked) next.add(permission.id);
                        else next.delete(permission.id);
                        return next;
                      })
                    }
                  />
                  <span>
                    <span className="permission-label">{label(permission)}</span>
                    {isHighImpact(permission.code) && (
                      <span className="permission-impact">{t("permissionHighImpact")}</span>
                    )}
                    <code className="permission-code">{permission.code}</code>
                  </span>
                </label>
              ))}
            </details>
          );
        })}
    </>
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
  compact = false,
}: {
  state: ReturnType<typeof useListControls>;
  visibleCount: number;
  hasNext: boolean;
  compact?: boolean;
}) {
  const { t } = useTranslation();
  return (
    <form
      className={`list-controls${compact ? " list-controls-compact" : ""}`}
      role="search"
      style={{
        display: "flex",
        alignItems: "center",
        flexWrap: "wrap",
        gap: "10px",
        justifyContent: "space-between",
        marginBottom: compact ? "8px" : "1rem",
        paddingBottom: compact ? "0" : "0.75rem",
        borderBottom: compact ? "none" : "1px solid var(--line)",
      }}
      onSubmit={(event) => {
        event.preventDefault();
        state.applySearch();
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          flex: "1 1 240px",
          maxWidth: "420px",
        }}
      >
        <input
          type="search"
          maxLength={100}
          value={state.draft}
          placeholder={t("searchPlaceholder")}
          onChange={(event) => state.setDraft(event.target.value)}
          style={{
            flex: 1,
            padding: "6px 12px",
            fontSize: "0.825rem",
            borderRadius: "4px",
            border: "1px solid var(--line)",
            background: "var(--panel)",
          }}
        />
        <button
          type="submit"
          style={{
            width: "auto",
            minWidth: "unset",
            height: "auto",
            padding: "6px 14px",
            fontSize: "0.825rem",
            whiteSpace: "nowrap",
          }}
        >
          {t("search")}
        </button>
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: compact ? "8px" : "12px",
          flexWrap: compact ? "nowrap" : "wrap",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <span style={{ fontSize: "0.8rem", color: "var(--muted)", whiteSpace: "nowrap" }}>
            {t("itemsPerPage")}:
          </span>
          <select
            value={state.pageSize}
            onChange={(event) => state.setPageSize(Number(event.target.value))}
            style={{
              padding: "4px 8px",
              fontSize: "0.8rem",
              borderRadius: "4px",
              border: "1px solid var(--line)",
              background: "var(--panel)",
              color: "var(--text)",
            }}
          >
            {[10, 25, 50].map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </div>

        <span
          className="list-result-count"
          style={{ fontSize: "0.8rem", color: "var(--muted)", whiteSpace: "nowrap" }}
        >
          {compact
            ? t("visibleResultsCompact", { count: visibleCount })
            : t("visibleResults", { count: visibleCount, page: state.page + 1 })}
        </span>

        <div className="pager" style={{ display: "flex", gap: "4px", flexShrink: 0 }}>
          {compact ? (
            <>
              <button
                type="button"
                className="ghost"
                aria-label={t("previous")}
                style={{
                  width: "26px",
                  minWidth: "unset",
                  height: "26px",
                  padding: 0,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
                disabled={state.page === 0}
                onClick={() => state.setPage(Math.max(0, state.page - 1))}
              >
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <polyline points="15 18 9 12 15 6" />
                </svg>
              </button>
              <button
                type="button"
                className="ghost"
                aria-label={t("next")}
                style={{
                  width: "26px",
                  minWidth: "unset",
                  height: "26px",
                  padding: 0,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
                disabled={!hasNext}
                onClick={() => state.setPage(state.page + 1)}
              >
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <polyline points="9 18 15 12 9 6" />
                </svg>
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                className="ghost"
                style={{
                  width: "auto",
                  minWidth: "unset",
                  height: "auto",
                  padding: "4px 10px",
                  fontSize: "0.75rem",
                  whiteSpace: "nowrap",
                }}
                disabled={state.page === 0}
                onClick={() => state.setPage(Math.max(0, state.page - 1))}
              >
                {t("previous")}
              </button>
              <button
                type="button"
                className="ghost"
                style={{
                  width: "auto",
                  minWidth: "unset",
                  height: "auto",
                  padding: "4px 10px",
                  fontSize: "0.75rem",
                  whiteSpace: "nowrap",
                }}
                disabled={!hasNext}
                onClick={() => state.setPage(state.page + 1)}
              >
                {t("next")}
              </button>
            </>
          )}
        </div>
      </div>
    </form>
  );
}

function Overview() {
  const { t } = useTranslation();
  const incidents = useQuery({
    queryKey: ["incidents", "overview"],
    queryFn: () => getIncidents({ pageSize: 100 }),
  });
  const alerts = useQuery({
    queryKey: ["alerts", "overview"],
    queryFn: () => getAlerts({ pageSize: 100 }),
  });
  const open = incidents.data?.filter((item) => item.status !== "closed") ?? [];
  const cards = [
    [t("listedOpenIncidents"), incidents.data ? String(open.length) : "—"],
    [
      t("listedCriticalIncidents"),
      incidents.data ? String(open.filter((item) => item.severity === "critical").length) : "—",
    ],
    [
      t("listedPendingReview"),
      incidents.data ? String(open.filter((item) => item.status === "new").length) : "—",
    ],
    [t("listedAlerts"), alerts.data ? String(alerts.data.length) : "—"],
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
    </>
  );
}

function AlertsPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const controls = useListControls();
  const me = useQuery({ queryKey: ["me"], queryFn: getMe, retry: false });

  const [alertSort, setAlertSort] = useState<AlertSort>("recent");
  const [alertSeverity, setAlertSeverity] = useState<AlertSeverity[]>([]);

  const alerts = useQuery({
    queryKey: [
      "alerts",
      controls.query,
      controls.page,
      controls.pageSize,
      alertSort,
      alertSeverity.join(","),
    ],
    queryFn: () =>
      getAlerts({
        query: controls.query,
        page: controls.page,
        pageSize: controls.pageSize,
        includeLookahead: true,
        sort: alertSort,
        severity: alertSeverity,
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
      queryClient.setQueriesData({ queryKey: ["alerts"] }, (oldData: Alert[] | undefined) => {
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
      });
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
        {/* Newest-first buries a critical alert under routine volume, so the
            order is selectable and severity can be narrowed. */}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "1rem",
            alignItems: "center",
            padding: "0 0 0.75rem",
          }}
        >
          <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.85rem" }}>
            {t("alertSort.label")}
            <select
              value={alertSort}
              onChange={(event) => {
                setAlertSort(event.target.value as AlertSort);
                controls.setPage(0);
              }}
              style={{ padding: "4px 8px" }}
            >
              <option value="recent">{t("alertSort.recent")}</option>
              <option value="severity">{t("alertSort.severity")}</option>
            </select>
          </label>
          <span style={{ display: "flex", flexWrap: "wrap", gap: "8px", alignItems: "center" }}>
            <span style={{ fontSize: "0.85rem" }}>{t("alertSeverityFilter")}</span>
            {(["critical", "high", "medium", "low", "informational"] as AlertSeverity[]).map(
              (level) => {
                const active = alertSeverity.includes(level);
                return (
                  <button
                    key={level}
                    type="button"
                    className={active ? "primary" : "ghost"}
                    style={{ padding: "3px 10px", fontSize: "0.78rem" }}
                    aria-pressed={active}
                    onClick={() => {
                      setAlertSeverity((current) =>
                        current.includes(level)
                          ? current.filter((item) => item !== level)
                          : [...current, level],
                      );
                      controls.setPage(0);
                    }}
                  >
                    {t(`severity.${level}`)}
                  </button>
                );
              },
            )}
          </span>
        </div>
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
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    justifyContent: "flex-end",
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
                        justifyContent: "space-between",
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
                          user:
                            alert.reviewer_display_name || alert.reviewed_by_user_id || "Analyst",
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
  const queryClient = useQueryClient();
  const controls = useListControls();
  const createMutation = useMutation({
    mutationFn: createIncident,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["incidents"] });
    },
  });
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
      <details className="panel" style={{ marginBottom: "1.25rem" }}>
        <summary>{t("createRealIncident")}</summary>
        <form
          className="form-grid"
          onSubmit={async (event) => {
            event.preventDefault();
            const form = event.currentTarget;
            const data = new FormData(form);
            try {
              await createMutation.mutateAsync({
                title: String(data.get("title")).trim(),
                description: String(data.get("description")).trim(),
                severity: String(data.get("severity")) as
                  | "informational"
                  | "low"
                  | "medium"
                  | "high"
                  | "critical",
                priority: Number(data.get("priority")),
                classification: String(data.get("classification")).trim(),
              });
              form.reset();
            } catch {
              // The error state remains visible and submitted values are preserved.
            }
          }}
        >
          <label>
            <span>{t("title")}</span>
            <input
              name="title"
              required
              minLength={3}
              maxLength={300}
              placeholder={
                i18n.language.startsWith("es")
                  ? "Ej. Intrusión y ejecución de script malicioso"
                  : "e.g. Host intrusion and malicious script"
              }
            />
          </label>
          <label>
            <span>{t("classification")}</span>
            <input
              name="classification"
              required
              minLength={2}
              maxLength={120}
              placeholder={
                i18n.language.startsWith("es")
                  ? "Ej. Malware / Ransomware"
                  : "e.g. Malware / Ransomware"
              }
            />
          </label>
          <label>
            <span>{t("severity")}</span>
            <select name="severity" defaultValue="medium">
              {(["informational", "low", "medium", "high", "critical"] as const).map((value) => (
                <option key={value} value={value}>
                  {t(`severityCodes.${value}`, { defaultValue: value })}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>{t("priority")}</span>
            <select name="priority" defaultValue="3">
              {[1, 2, 3, 4, 5].map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label style={{ gridColumn: "1 / -1" }}>
            <span>{t("description")}</span>
            <textarea
              name="description"
              required
              minLength={3}
              maxLength={5000}
              rows={4}
              placeholder={
                i18n.language.startsWith("es")
                  ? "Detalle los hallazgos técnicos, vectores observados o sistemas afectados..."
                  : "Detail technical findings, observed vectors or affected systems..."
              }
            />
          </label>
          <div className="form-grid-actions">
            <button type="submit" className="primary" disabled={createMutation.isPending}>
              ➕ {t("createRealIncident")}
            </button>
            {createMutation.isError && (
              <p className="form-error" role="alert" style={{ margin: 0 }}>
                {t("incidentCreateError")}
              </p>
            )}
          </div>
        </form>
      </details>
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
                <div
                  style={{
                    flex: 1,
                    display: "flex",
                    alignItems: "center",
                    gap: "10px",
                    minWidth: 0,
                  }}
                >
                  <strong style={{ whiteSpace: "nowrap" }}>
                    {incident.code} · {incident.title}
                  </strong>
                  <span
                    className="preview-badge"
                    title={t("incidentOrigin")}
                    style={{ whiteSpace: "nowrap" }}
                  >
                    {t(incidentOriginKey(incident.code))}
                  </span>
                  <span
                    style={{
                      color: "var(--muted)",
                      fontSize: "0.85rem",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                  >
                    ({incident.classification})
                  </span>
                </div>
                {isValidDate && (
                  <span
                    style={{
                      fontSize: "0.875rem",
                      color: "var(--text-soft)",
                      whiteSpace: "nowrap",
                      fontFamily: "var(--font-mono, monospace)",
                    }}
                  >
                    {detectedDate.toLocaleString(i18n.language)}
                  </span>
                )}
                <span style={{ whiteSpace: "nowrap" }}>
                  {t(`statusCodes.${incident.status}`, { defaultValue: incident.status })}
                </span>
              </NavLink>
            );
          })}
        </div>
      </section>
    </>
  );
}

const INCIDENT_TRANSITIONS: Record<string, string[]> = {
  new: ["triaged", "closed"],
  triaged: ["investigating", "closed"],
  investigating: ["contained", "resolved", "closed"],
  contained: ["investigating", "resolved"],
  resolved: ["closed", "reopened"],
  closed: ["reopened"],
  reopened: ["triaged", "investigating"],
};

/** Attach already-ingested alerts to an incident as evidence.
 *
 * Correlation and the entity-risk sweep attach their own evidence, so this is
 * for the incidents nobody detected: the ones an analyst opens after a phone
 * call, a CERT notice or an audit finding, where the evidence has to be
 * assembled by hand. Before this they could never hold any.
 *
 * Attaching is additive by design and there is no detach: evidence connected
 * to a case is part of its record, and a mistake is corrected by saying so in
 * the timeline rather than by making it disappear.
 */
function EvidenceLinker({
  incidentId,
  incidentVersion,
  linkedIds,
}: {
  incidentId: string;
  incidentVersion: number | undefined;
  linkedIds: Set<string>;
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<string[]>([]);
  const [failed, setFailed] = useState(false);

  const candidates = useQuery({
    queryKey: ["alerts", "linkable"],
    queryFn: () => getAlerts({ pageSize: 100 }),
  });

  const available = (candidates.data ?? []).filter((alert) => !linkedIds.has(alert.id));

  const attach = useMutation({
    mutationFn: () => linkIncidentAlerts(incidentId, incidentVersion ?? 1, selected),
    onSuccess: async () => {
      setSelected([]);
      setFailed(false);
      await queryClient.invalidateQueries({ queryKey: ["incident-alerts", incidentId] });
      await queryClient.invalidateQueries({ queryKey: ["incident", incidentId] });
      await queryClient.invalidateQueries({ queryKey: ["timeline", incidentId] });
    },
    onError: () => setFailed(true),
  });

  return (
    <details className="panel" style={{ marginBottom: "1.25rem" }}>
      <summary>{t("linkEvidence")}</summary>
      <p style={{ marginTop: "0.75rem" }}>{t("linkEvidenceHelp")}</p>
      {failed && (
        <p className="status-message status-error" role="alert">
          {t("linkEvidenceError")}
        </p>
      )}
      {available.length === 0 ? (
        <p className="status-message">{t("linkEvidenceEmpty")}</p>
      ) : (
        <>
          <div
            className="data-list"
            style={{ marginTop: "0.75rem", maxHeight: "320px", overflowY: "auto" }}
          >
            {available.map((alert) => (
              <label
                key={alert.id}
                style={{ display: "flex", gap: "10px", alignItems: "baseline", maxWidth: "none" }}
              >
                <input
                  type="checkbox"
                  style={{ width: "auto" }}
                  checked={selected.includes(alert.id)}
                  onChange={(event) =>
                    setSelected((current) =>
                      event.target.checked
                        ? [...current, alert.id]
                        : current.filter((item) => item !== alert.id),
                    )
                  }
                />
                <span>
                  <strong>{alert.title}</strong> · {alert.severity} ·{" "}
                  {new Date(alert.observed_at).toLocaleString()}
                </span>
              </label>
            ))}
          </div>
          <button
            type="button"
            style={{ marginTop: "0.75rem" }}
            disabled={selected.length === 0 || attach.isPending || incidentVersion === undefined}
            onClick={() => attach.mutate()}
          >
            {t("linkEvidenceAction")} ({selected.length})
          </button>
        </>
      )}
    </details>
  );
}

function IncidentDetailPage() {
  const { id = "" } = useParams();
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<"overview" | "alerts" | "threatIntel" | "audit">(
    "overview",
  );
  const [expandedAlertId, setExpandedAlertId] = useState<string | null>(null);
  const [showMoreMenu, setShowMoreMenu] = useState(false);
  const [selectedPlaybookCode, setSelectedPlaybookCode] = useState("");
  const [approvalReasons, setApprovalReasons] = useState<Record<string, string>>({});
  const [incidentDraft, setIncidentDraft] = useState({
    title: "",
    description: "",
    severity: "medium" as "informational" | "low" | "medium" | "high" | "critical",
    priority: 3,
    classification: "",
  });
  const [assigneeUserId, setAssigneeUserId] = useState("");
  const [timelineComment, setTimelineComment] = useState("");
  const [claimDraft, setClaimDraft] = useState({
    claimType: "INFERENCE" as
      | "FACT"
      | "DERIVED_FACT"
      | "INFERENCE"
      | "HYPOTHESIS"
      | "RECOMMENDATION",
    statement: "",
    confidence: 0.5,
    explanation: "",
    validationCriteria: "",
    missingEvidence: "",
    methodCode: "",
    methodVersion: "",
    evidenceKey: "",
  });
  const [claimAssessment, setClaimAssessment] = useState({
    claimId: "",
    outcome: "VALIDATED" as "VALIDATED" | "REJECTED" | "INSUFFICIENT_EVIDENCE" | "RETRACTED",
    explanation: "",
  });
  const [claimRelation, setClaimRelation] = useState({
    sourceClaimId: "",
    targetClaimId: "",
    relationshipType: "SUPPORTS" as
      | "SUPPORTS"
      | "CONTRADICTS"
      | "DERIVED_FROM"
      | "SUPERSEDES"
      | "RESPONDS_TO",
  });
  const [claimPresentation, setClaimPresentation] = useState({
    claimId: "",
    locale: "en" as "es" | "en",
    text: "",
  });
  const [transitionTarget, setTransitionTarget] = useState("");
  const [closeReason, setCloseReason] = useState<
    "false_positive" | "duplicate" | "accepted_risk" | "resolved" | "other"
  >("resolved");

  const incident = useQuery({ queryKey: ["incident", id], queryFn: () => getIncident(id) });
  const currentUser = useQuery({ queryKey: ["me"], queryFn: getMe, retry: false });
  const tenantUsers = useQuery({
    queryKey: ["users", "incident-assignment"],
    queryFn: () => getUsers({ pageSize: 100 }),
    retry: false,
  });
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
  const claimEvidenceOptions = [
    { key: `INCIDENT:${id}`, type: "INCIDENT" as const, id, label: incident.data?.code ?? id },
    ...(linkedAlerts.data ?? []).map((alert) => ({
      key: `ALERT_REFERENCE:${alert.id}`,
      type: "ALERT_REFERENCE" as const,
      id: alert.id,
      label: `${alert.external_id} · ${alert.title}`,
    })),
    ...(timeline.data ?? []).map((entry) => ({
      key: `INCIDENT_TIMELINE_ENTRY:${entry.id}`,
      type: "INCIDENT_TIMELINE_ENTRY" as const,
      id: entry.id,
      label: `${entry.entry_type} · ${entry.summary}`,
    })),
    ...(claims.data ?? []).map((claim) => ({
      key: `CLAIM:${claim.id}`,
      type: "CLAIM" as const,
      id: claim.id,
      label: `${claim.claim_type} · ${claim.statement}`,
    })),
  ].filter(
    (option) =>
      claimDraft.claimType !== "FACT" ||
      ["ALERT_REFERENCE", "INCIDENT_TIMELINE_ENTRY"].includes(option.type),
  );
  const selectedClaimEvidence =
    claimEvidenceOptions.find((option) => option.key === claimDraft.evidenceKey) ??
    claimEvidenceOptions[0];

  const playbookDefinitions = useQuery({
    queryKey: ["playbook-definitions"],
    queryFn: getPlaybookDefinitions,
    retry: false,
  });
  const executablePlaybooks = (playbookDefinitions.data?.items ?? []).filter(
    (item) =>
      item.readiness_status === "READY" &&
      item.publication_status === "PUBLISHED" &&
      item.binding_active &&
      Boolean(item.latest_version),
  );
  const incidentAttackCodes = useMemo(
    () => new Set((enrichment.data?.mappings ?? []).map((m) => m.external_id)),
    [enrichment.data?.mappings],
  );

  const sortedPlaybooks = useMemo(() => {
    return [...executablePlaybooks].sort((a, b) => {
      const aRec = a.mitre_codes.some((c) => incidentAttackCodes.has(c));
      const bRec = b.mitre_codes.some((c) => incidentAttackCodes.has(c));
      if (aRec && !bRec) return -1;
      if (!aRec && bRec) return 1;
      return 0;
    });
  }, [executablePlaybooks, incidentAttackCodes]);

  const selectedPlaybook =
    sortedPlaybooks.find((item) => item.code === selectedPlaybookCode) ?? sortedPlaybooks[0];
  const playbookExecutions = useQuery({
    queryKey: ["playbook-executions", id],
    queryFn: () => getPlaybookExecutions(id),
    retry: false,
  });

  useEffect(() => {
    if (!incident.data) return;
    setIncidentDraft({
      title: incident.data.title,
      description: incident.data.description ?? "",
      severity: incident.data.severity as typeof incidentDraft.severity,
      priority: incident.data.priority ?? 3,
      classification: incident.data.classification ?? "",
    });
    setAssigneeUserId(incident.data.assignee_user_id ?? "");
    setTransitionTarget(INCIDENT_TRANSITIONS[incident.data.status]?.[0] ?? "");
    // Keyed on version alone, deliberately. This resets the edit form from the
    // server copy, so depending on `incident.data` would rerun it on every
    // refetch and wipe whatever the analyst is part-way through typing. The
    // form should only be reset when the incident it is editing actually
    // changed underneath them, which is what a new version means.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [incident.data?.version]);

  const refreshIncident = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["incident", id] }),
      queryClient.invalidateQueries({ queryKey: ["incidents"] }),
      queryClient.invalidateQueries({ queryKey: ["timeline", id] }),
    ]);
  };
  const updateDetails = useMutation({
    mutationFn: () => updateIncident(id, incident.data!.version, incidentDraft),
    onSuccess: refreshIncident,
  });
  const assign = useMutation({
    mutationFn: () => assignIncident(id, incident.data!.version, assigneeUserId || null),
    onSuccess: refreshIncident,
  });
  const addTimelineComment = useMutation({
    mutationFn: () => addIncidentTimelineEntry(id, incident.data!.version, timelineComment.trim()),
    onSuccess: async () => {
      setTimelineComment("");
      await refreshIncident();
    },
  });

  const [transitionNote, setTransitionNote] = useState("");

  const transition = useMutation({
    mutationFn: ({
      target,
      reason,
      closingReason,
    }: {
      target: string;
      reason?: string;
      closingReason?: "false_positive" | "duplicate" | "accepted_risk" | "resolved" | "other";
    }) => transitionIncident(id, incident.data!.version, target, reason, closingReason),
    onSuccess: async () => {
      setTransitionNote("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["incident", id] }),
        queryClient.invalidateQueries({ queryKey: ["incidents"] }),
        queryClient.invalidateQueries({ queryKey: ["timeline", id] }),
      ]);
    },
  });
  const createClaim = useMutation({
    mutationFn: () => {
      if (!selectedClaimEvidence) throw new Error("CLAIM_EVIDENCE_REQUIRED");
      const nonDeterministic = ["INFERENCE", "HYPOTHESIS", "RECOMMENDATION"].includes(
        claimDraft.claimType,
      );
      return createHumanClaim(id, {
        claim_type: claimDraft.claimType,
        statement: claimDraft.statement.trim(),
        language_code: i18n.language.startsWith("es") ? "es" : "en",
        confidence: nonDeterministic ? claimDraft.confidence : null,
        explanation: nonDeterministic ? claimDraft.explanation.trim() : null,
        validation_criteria:
          claimDraft.claimType === "HYPOTHESIS" ? claimDraft.validationCriteria.trim() : null,
        missing_evidence:
          claimDraft.claimType === "HYPOTHESIS" ? [claimDraft.missingEvidence.trim()] : [],
        method_code: claimDraft.claimType === "DERIVED_FACT" ? claimDraft.methodCode.trim() : null,
        method_version:
          claimDraft.claimType === "DERIVED_FACT" ? claimDraft.methodVersion.trim() : null,
        evidence: [
          {
            evidence_type: selectedClaimEvidence.type,
            evidence_id: selectedClaimEvidence.id,
            relationship: "SUPPORTS",
          },
        ],
      });
    },
    onSuccess: async () => {
      setClaimDraft((current) => ({
        ...current,
        statement: "",
        explanation: "",
        validationCriteria: "",
        missingEvidence: "",
        evidenceKey: "",
      }));
      await queryClient.invalidateQueries({ queryKey: ["claims", id] });
    },
  });
  const assess = useMutation({
    mutationFn: () =>
      assessClaim(
        claimAssessment.claimId,
        claimAssessment.outcome,
        claimAssessment.explanation.trim(),
      ),
    onSuccess: async () => {
      setClaimAssessment({ claimId: "", outcome: "VALIDATED", explanation: "" });
      await queryClient.invalidateQueries({ queryKey: ["claims", id] });
    },
  });

  const relate = useMutation({
    mutationFn: () =>
      relateClaim(
        claimRelation.sourceClaimId,
        claimRelation.targetClaimId,
        claimRelation.relationshipType,
      ),
    onSuccess: async () => {
      setClaimRelation({ sourceClaimId: "", targetClaimId: "", relationshipType: "SUPPORTS" });
      await queryClient.invalidateQueries({ queryKey: ["claims", id] });
    },
  });
  const presentClaim = useMutation({
    mutationFn: () =>
      addClaimPresentation(
        claimPresentation.claimId,
        claimPresentation.locale,
        claimPresentation.text.trim(),
      ),
    onSuccess: async () => {
      setClaimPresentation({ claimId: "", locale: "en", text: "" });
      await queryClient.invalidateQueries({ queryKey: ["claims", id] });
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
    mutationFn: () => {
      if (!selectedPlaybook) throw new Error("PLAYBOOK_NOT_READY");
      return proposePlaybookAction(id, selectedPlaybook);
    },
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
  const approvalDecision = useMutation({
    mutationFn: ({
      requestId,
      decision,
      fingerprint,
      reason,
    }: {
      requestId: string;
      decision: "APPROVE" | "REJECT";
      fingerprint: string;
      reason: string;
    }) => decideResponse(requestId, decision, fingerprint, reason),
    onSuccess: async (_data, variables) => {
      setApprovalReasons((current) => {
        const next = { ...current };
        delete next[variables.requestId];
        return next;
      });
      await queryClient.invalidateQueries({ queryKey: ["response-decisions", id] });
    },
  });

  const transitionTargets = incident.data ? (INCIDENT_TRANSITIONS[incident.data.status] ?? []) : [];

  if (incident.isLoading) return <PageState loading error={false} empty={false} />;
  if (incident.isError || !incident.data) {
    return <PageState loading={false} error empty={false} />;
  }

  return (
    <>
      <div className="page-title">
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
            <p className="eyebrow" style={{ margin: 0 }}>
              {incident.data.code}
            </p>
            {incident.data.detected_at && !isNaN(new Date(incident.data.detected_at).getTime()) && (
              <span style={{ fontSize: "0.8rem", color: "var(--muted)", fontWeight: 500 }}>
                📅{" "}
                {new Date(incident.data.detected_at).toLocaleString(i18n.language, {
                  dateStyle: "medium",
                  timeStyle: "medium",
                })}
              </span>
            )}
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
            justifyContent: "space-between",
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
              <svg
                width="15"
                height="15"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
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
              <svg
                width="15"
                height="15"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
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
              <svg
                width="15"
                height="15"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
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
              <svg
                width="15"
                height="15"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
              </svg>
              {t("tabAudit")}{" "}
              {playbookExecutions.data?.length ? `(${playbookExecutions.data.length})` : ""}
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
              aria-label={t("moreOptions")}
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
          <section className="panel" style={{ marginBottom: "1.25rem" }}>
            <p className="eyebrow">{t("incidentOperations")}</p>
            <h2>{t("incidentDetails")}</h2>
            <form
              className="form-grid"
              onSubmit={(event) => {
                event.preventDefault();
                updateDetails.mutate();
              }}
            >
              <label>
                {t("title")}
                <input
                  required
                  minLength={3}
                  maxLength={300}
                  value={incidentDraft.title}
                  onChange={(event) =>
                    setIncidentDraft({ ...incidentDraft, title: event.target.value })
                  }
                />
              </label>
              <label>
                {t("classification")}
                <input
                  required
                  minLength={2}
                  maxLength={120}
                  value={incidentDraft.classification}
                  onChange={(event) =>
                    setIncidentDraft({ ...incidentDraft, classification: event.target.value })
                  }
                />
              </label>
              <label>
                {t("severity")}
                <select
                  value={incidentDraft.severity}
                  onChange={(event) =>
                    setIncidentDraft({
                      ...incidentDraft,
                      severity: event.target.value as typeof incidentDraft.severity,
                    })
                  }
                >
                  {(["informational", "low", "medium", "high", "critical"] as const).map(
                    (value) => (
                      <option key={value} value={value}>
                        {t(`severityCodes.${value}`, { defaultValue: value })}
                      </option>
                    ),
                  )}
                </select>
              </label>
              <label>
                {t("priority")}
                <select
                  value={incidentDraft.priority}
                  onChange={(event) =>
                    setIncidentDraft({ ...incidentDraft, priority: Number(event.target.value) })
                  }
                >
                  {[1, 2, 3, 4, 5].map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </label>
              <label style={{ gridColumn: "1 / -1" }}>
                {t("description")}
                <textarea
                  required
                  minLength={3}
                  maxLength={5000}
                  rows={4}
                  value={incidentDraft.description}
                  onChange={(event) =>
                    setIncidentDraft({ ...incidentDraft, description: event.target.value })
                  }
                />
              </label>
              <button type="submit" disabled={updateDetails.isPending}>
                {t("saveIncident")}
              </button>
            </form>

            <div className="form-grid" style={{ marginTop: "1.25rem" }}>
              <label>
                {t("assignee")}
                <AssigneeCombobox value={assigneeUserId} onChange={setAssigneeUserId} />
              </label>
              <div style={{ alignSelf: "end" }}>
                <button
                  type="button"
                  disabled={assign.isPending || tenantUsers.isLoading || tenantUsers.isError}
                  onClick={() => assign.mutate()}
                >
                  {t("saveAssignment")}
                </button>
              </div>
              <label style={{ gridColumn: "1 / -1" }}>
                {t("timelineComment")}
                <textarea
                  rows={3}
                  minLength={1}
                  maxLength={5000}
                  value={timelineComment}
                  onChange={(event) => setTimelineComment(event.target.value)}
                />
              </label>
              <button
                type="button"
                disabled={addTimelineComment.isPending || timelineComment.trim().length === 0}
                onClick={() => addTimelineComment.mutate()}
              >
                {t("addTimelineComment")}
              </button>
            </div>
            {(updateDetails.isError || assign.isError || addTimelineComment.isError) && (
              <p className="status-message status-error" role="alert">
                {t("actionError")}
              </p>
            )}
          </section>

          {/* Recommended Playbooks & Approval Section */}
          <section className="panel" style={{ marginBottom: "1.25rem" }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
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
                const hasExistingProposal = (responseDecisions.data ?? []).some((item) =>
                  ["AWAITING_APPROVAL", "AUTHORIZED"].includes(item.status),
                );
                return (
                  // alignItems matters here: the label stacks a caption above
                  // its select, so it is two lines tall. Left to stretch, the
                  // button grew to match that height and read as the biggest
                  // control on the page -- which it is not, and which made a
                  // proposal look like an execution.
                  <div
                    style={{
                      display: "flex",
                      gap: "10px",
                      flexWrap: "wrap",
                      alignItems: "flex-end",
                    }}
                  >
                    <label>
                      <span className="muted">{t("selectReadyPlaybook")}</span>
                      <select
                        value={selectedPlaybook?.code ?? ""}
                        disabled={sortedPlaybooks.length === 0 || hasExistingProposal}
                        onChange={(event) => setSelectedPlaybookCode(event.target.value)}
                      >
                        {sortedPlaybooks.length === 0 && (
                          <option value="">{t("noReadyPlaybooks")}</option>
                        )}
                        {sortedPlaybooks.map((item) => {
                          const isRecommended = item.mitre_codes.some((code) =>
                            incidentAttackCodes.has(code),
                          );
                          const title = i18n.language.startsWith("es")
                            ? item.title_i18n.es
                            : item.title_i18n.en;
                          return (
                            <option key={item.id} value={item.code}>
                              {isRecommended ? "⭐ [RECOMENDADO] " : ""}
                              {title} · v{item.latest_version}
                            </option>
                          );
                        })}
                      </select>
                    </label>
                    <button
                      type="button"
                      disabled={
                        responseProposal.isPending || hasExistingProposal || !selectedPlaybook
                      }
                      title={
                        hasExistingProposal
                          ? t("proposalAlreadyExecuted")
                          : !selectedPlaybook
                            ? t("noReadyPlaybooks")
                            : undefined
                      }
                      onClick={() => responseProposal.mutate()}
                    >
                      ⚡ {t("proposeSafeResponse")}
                    </button>
                  </div>
                );
              })()}
            </div>

            {/* Sub-header Notice Banner for 4-Eye Principle */}
            {responseDecisions.data?.some(
              (d) => d.status === "AWAITING_APPROVAL" && d.approval_status === "PENDING",
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
                const countApproved = decision.decisions.filter(
                  (entry) => entry.decision === "APPROVE",
                ).length;
                const totalApprovals = decision.required_approvals;
                const hasRequiredApprovals = totalApprovals > 0 && countApproved >= totalApprovals;
                return (
                  <article
                    className="claim-card"
                    key={decision.id}
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      justifyContent: "space-between",
                      padding: "1.25rem",
                      border: "1px solid var(--panel-border)",
                      borderRadius: "8px",
                    }}
                  >
                    <div>
                      <div className="claim-badges" style={{ marginBottom: "10px" }}>
                        <span className="severity">{decision.status}</span>
                        <span>{decision.impact}</span>
                      </div>
                      <strong
                        style={{ fontSize: "1.15rem", display: "block", marginBottom: "6px" }}
                      >
                        {decision.action_type}
                      </strong>
                      <div
                        style={{
                          background: "var(--panel-raised)",
                          padding: "8px 12px",
                          borderRadius: "6px",
                          margin: "6px 0 10px",
                          borderLeft: "3px solid var(--accent)",
                        }}
                      >
                        <span
                          style={{
                            fontSize: "0.75rem",
                            color: "var(--muted)",
                            display: "block",
                            marginBottom: "2px",
                          }}
                        >
                          🎯{" "}
                          {t("targetBlockedEntity", {
                            defaultValue: "Usuario / Entidad objetivo del bloqueo:",
                          })}
                        </span>
                        <strong
                          style={{
                            fontSize: "0.9rem",
                            color: "var(--text-bright)",
                            fontFamily: "var(--font-mono, monospace)",
                          }}
                        >
                          {decision.targets && decision.targets.length > 0
                            ? decision.targets.join(", ")
                            : t("notAvailable")}
                        </strong>
                      </div>
                      <p style={{ margin: "6px 0", fontSize: "0.9rem" }}>
                        <strong>{t("approvalProgress")}:</strong> {countApproved}/{totalApprovals}
                        {totalApprovals >= 2 && hasRequiredApprovals && (
                          <span
                            style={{ color: "var(--accent)", marginLeft: "6px", fontWeight: 600 }}
                          >
                            ✓ {t("fourEyesApproved")}
                          </span>
                        )}
                      </p>
                      <small style={{ color: "var(--muted)", display: "block", marginTop: "6px" }}>
                        {t("policyOutcome")}: {decision.evaluation_outcome} ·{" "}
                        {decision.reason_codes.join(" · ")}
                      </small>
                    </div>
                    <div style={{ marginTop: "16px" }}>
                      {decision.approval_request_id &&
                        decision.approval_status === "PENDING" &&
                        decision.status === "AWAITING_APPROVAL" &&
                        (currentUser.data?.id !== decision.requester_user_id ? (
                          <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
                            <textarea
                              aria-label={t("approvalReason")}
                              placeholder={t("approvalReasonPlaceholder")}
                              minLength={1}
                              maxLength={1000}
                              required
                              value={approvalReasons[decision.approval_request_id!] ?? ""}
                              onChange={(event) =>
                                setApprovalReasons((current) => ({
                                  ...current,
                                  [decision.approval_request_id!]: event.target.value,
                                }))
                              }
                              style={{ flexBasis: "100%", minHeight: "72px" }}
                            />
                            <button
                              type="button"
                              style={{ flex: 1 }}
                              disabled={
                                approvalDecision.isPending ||
                                !(approvalReasons[decision.approval_request_id!] ?? "").trim()
                              }
                              onClick={() =>
                                approvalDecision.mutate({
                                  requestId: decision.approval_request_id!,
                                  decision: "APPROVE",
                                  fingerprint: decision.fingerprint,
                                  reason: approvalReasons[decision.approval_request_id!] ?? "",
                                })
                              }
                            >
                              ✓ {t("approveResponse")}
                            </button>
                            <button
                              type="button"
                              className="ghost"
                              style={{ flex: 1 }}
                              disabled={
                                approvalDecision.isPending ||
                                !(approvalReasons[decision.approval_request_id!] ?? "").trim()
                              }
                              onClick={() =>
                                approvalDecision.mutate({
                                  requestId: decision.approval_request_id!,
                                  decision: "REJECT",
                                  fingerprint: decision.fingerprint,
                                  reason: approvalReasons[decision.approval_request_id!] ?? "",
                                })
                              }
                            >
                              ✕ {t("rejectResponse")}
                            </button>
                          </div>
                        ) : (
                          <p
                            style={{
                              margin: 0,
                              fontSize: "0.85rem",
                              color: "var(--text-soft)",
                              background: "var(--panel-raised)",
                              padding: "8px 12px",
                              borderRadius: "6px",
                            }}
                          >
                            🔒 {t("awaitingSecondAnalystNotice")}
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
              <p style={{ color: "var(--muted)", margin: "4px 0 0" }}>
                {incident.data.description}
              </p>
            </div>

            {analysis.data && (
              <div className="analysis-card" style={{ marginBottom: "1rem" }}>
                <strong>
                  {analysis.data.grounded
                    ? `${t("risk")}: ${analysis.data.risk_score}/100`
                    : t("analysisEvidenceUnavailable")}
                </strong>
                <p>
                  {i18n.language.startsWith("es")
                    ? analysis.data.summary_es
                    : analysis.data.summary_en}
                </p>
                {analysis.data.grounded && analysis.data.techniques.length > 0 && (
                  <small>
                    {analysis.data.techniques.map((item) => item.external_id).join(" · ")}
                  </small>
                )}
              </div>
            )}

            {(transition.isError || analysis.isError || responseProposal.isError) && (
              <p
                className="status-message status-error"
                role="alert"
                style={{ marginBottom: "1rem" }}
              >
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
                  📝 {t("investigationWorkflowTitle")}
                </strong>
                <p style={{ margin: "4px 0 0", fontSize: "0.8rem", color: "var(--muted)" }}>
                  {t("investigationWorkflowIntro")}
                </p>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                <label style={{ maxWidth: "320px" }}>
                  {t("targetStatus")}
                  <select
                    value={transitionTarget}
                    onChange={(event) => setTransitionTarget(event.target.value)}
                  >
                    {transitionTargets.map((target) => (
                      <option key={target} value={target}>
                        {t(`statusCodes.${target}`, { defaultValue: target })}
                      </option>
                    ))}
                  </select>
                </label>
                {transitionTarget === "closed" && (
                  <label style={{ maxWidth: "320px" }}>
                    {t("closeReason")}
                    <select
                      value={closeReason}
                      onChange={(event) => setCloseReason(event.target.value as typeof closeReason)}
                    >
                      {(
                        [
                          "resolved",
                          "false_positive",
                          "duplicate",
                          "accepted_risk",
                          "other",
                        ] as const
                      ).map((reason) => (
                        <option key={reason} value={reason}>
                          {t(`closeReasons.${reason}`)}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                <label>
                  {t("transitionReason")}
                  <textarea
                    rows={2}
                    minLength={
                      transitionTarget === "closed" || transitionTarget === "reopened"
                        ? 3
                        : undefined
                    }
                    maxLength={1000}
                    required={transitionTarget === "closed" || transitionTarget === "reopened"}
                    value={transitionNote}
                    onChange={(event) => setTransitionNote(event.target.value)}
                  />
                </label>

                <div
                  style={{
                    display: "flex",
                    justifyContent: "flex-end",
                    alignItems: "center",
                    gap: "10px",
                  }}
                >
                  <button
                    type="button"
                    className="primary"
                    disabled={
                      transition.isPending ||
                      !transitionTarget ||
                      (["closed", "reopened"].includes(transitionTarget) &&
                        transitionNote.trim().length < 3)
                    }
                    onClick={() =>
                      transition.mutate({
                        target: transitionTarget,
                        reason: transitionNote,
                        closingReason: transitionTarget === "closed" ? closeReason : undefined,
                      })
                    }
                  >
                    {transition.isPending
                      ? t("loading")
                      : `➜ ${t("changeStatusTo")} ${t(`statusCodes.${transitionTarget}`, { defaultValue: transitionTarget })}`}
                  </button>
                </div>
              </div>
            </div>
          </section>
        </>
      )}

      {activeTab === "alerts" && (
        <>
          <EvidenceLinker
            incidentId={id}
            incidentVersion={incident.data?.version}
            linkedIds={new Set((linkedAlerts.data ?? []).map((alert) => alert.id))}
          />
          <section className="panel" style={{ marginBottom: "1.25rem" }}>
            <div>
              <p className="eyebrow">{t("traceability")}</p>
              <h2>{t("tabAlerts")}</h2>
              <p>{t("linkedAlertsIntro")}</p>
            </div>
            <PageState
              loading={linkedAlerts.isLoading}
              error={linkedAlerts.isError}
              empty={
                !linkedAlerts.isLoading && !linkedAlerts.isError && linkedAlerts.data?.length === 0
              }
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
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "10px",
                        justifyContent: "flex-end",
                      }}
                    >
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
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            marginBottom: "12px",
                          }}
                        >
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
                  </div>
                  <strong>
                    {t("correlationScore")}: {match.score}/100 · {t("threshold")}: {match.threshold}
                  </strong>
                  <p style={{ margin: "4px 0" }}>
                    {t("members")}: {match.members.length}
                  </p>
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
                  !correlations.isLoading &&
                  !correlations.isError &&
                  correlations.data?.length === 0
                }
              />
            </div>
          </section>
        </>
      )}

      {activeTab === "threatIntel" && (
        <>
          <section
            style={{
              display: "flex",
              flexDirection: "column",
              minHeight: "unset",
              gap: "1rem",
              marginBottom: "1.25rem",
              background: "var(--panel)",
              border: "1px solid var(--panel-border)",
              borderRadius: "8px",
              padding: "1.5rem",
            }}
          >
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
                <p style={{ margin: "4px 0 0", color: "var(--muted)", fontSize: "0.85rem" }}>
                  {t("threatEnrichmentIntro")}
                </p>
              </div>
              <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                <button
                  type="button"
                  className="ghost"
                  style={{
                    width: "auto",
                    minWidth: "unset",
                    height: "auto",
                    padding: "6px 14px",
                    fontSize: "0.825rem",
                  }}
                  disabled={recalculateRisk.isPending}
                  onClick={() => recalculateRisk.mutate()}
                >
                  ⚡ {t("recalculateRisk")}
                </button>
                <button
                  type="button"
                  className="primary"
                  style={{
                    width: "auto",
                    minWidth: "unset",
                    height: "auto",
                    padding: "6px 14px",
                    fontSize: "0.825rem",
                  }}
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
            <details style={{ marginTop: "1rem" }}>
              <summary>{t("createClaim")}</summary>
              <form
                className="form-grid"
                style={{ marginTop: "1rem" }}
                onSubmit={(event) => {
                  event.preventDefault();
                  createClaim.mutate();
                }}
              >
                <label>
                  {t("claimType")}
                  <select
                    value={claimDraft.claimType}
                    onChange={(event) =>
                      setClaimDraft({
                        ...claimDraft,
                        claimType: event.target.value as typeof claimDraft.claimType,
                        evidenceKey: "",
                      })
                    }
                  >
                    {(
                      ["FACT", "DERIVED_FACT", "INFERENCE", "HYPOTHESIS", "RECOMMENDATION"] as const
                    ).map((type) => (
                      <option key={type} value={type}>
                        {t(`claimTypes.${type}`)}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  {t("claimEvidence")}
                  <select
                    required
                    value={selectedClaimEvidence?.key ?? ""}
                    onChange={(event) =>
                      setClaimDraft({ ...claimDraft, evidenceKey: event.target.value })
                    }
                  >
                    {claimEvidenceOptions.length === 0 && (
                      <option value="">{t("noDirectEvidence")}</option>
                    )}
                    {claimEvidenceOptions.map((option) => (
                      <option key={option.key} value={option.key}>
                        {option.type} · {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label style={{ gridColumn: "1 / -1" }}>
                  {t("claimStatement")}
                  <textarea
                    required
                    minLength={1}
                    maxLength={2000}
                    rows={3}
                    value={claimDraft.statement}
                    onChange={(event) =>
                      setClaimDraft({ ...claimDraft, statement: event.target.value })
                    }
                  />
                </label>
                {["INFERENCE", "HYPOTHESIS", "RECOMMENDATION"].includes(claimDraft.claimType) && (
                  <>
                    <label>
                      {t("confidence")}
                      <input
                        type="number"
                        required
                        min={0}
                        max={1}
                        step={0.01}
                        value={claimDraft.confidence}
                        onChange={(event) =>
                          setClaimDraft({ ...claimDraft, confidence: Number(event.target.value) })
                        }
                      />
                    </label>
                    <label style={{ gridColumn: "1 / -1" }}>
                      {t("claimExplanation")}
                      <textarea
                        required
                        minLength={1}
                        maxLength={4000}
                        rows={3}
                        value={claimDraft.explanation}
                        onChange={(event) =>
                          setClaimDraft({ ...claimDraft, explanation: event.target.value })
                        }
                      />
                    </label>
                  </>
                )}
                {claimDraft.claimType === "DERIVED_FACT" && (
                  <>
                    <label>
                      {t("methodCode")}
                      <input
                        required
                        maxLength={120}
                        value={claimDraft.methodCode}
                        onChange={(event) =>
                          setClaimDraft({ ...claimDraft, methodCode: event.target.value })
                        }
                      />
                    </label>
                    <label>
                      {t("methodVersion")}
                      <input
                        required
                        maxLength={80}
                        value={claimDraft.methodVersion}
                        onChange={(event) =>
                          setClaimDraft({ ...claimDraft, methodVersion: event.target.value })
                        }
                      />
                    </label>
                  </>
                )}
                {claimDraft.claimType === "HYPOTHESIS" && (
                  <>
                    <label style={{ gridColumn: "1 / -1" }}>
                      {t("validationCriteria")}
                      <textarea
                        required
                        minLength={1}
                        maxLength={2000}
                        rows={2}
                        value={claimDraft.validationCriteria}
                        onChange={(event) =>
                          setClaimDraft({ ...claimDraft, validationCriteria: event.target.value })
                        }
                      />
                    </label>
                    <label>
                      {t("missingEvidenceCode")}
                      <input
                        required
                        pattern="[a-z][a-z0-9_.-]{0,79}"
                        value={claimDraft.missingEvidence}
                        onChange={(event) =>
                          setClaimDraft({ ...claimDraft, missingEvidence: event.target.value })
                        }
                      />
                    </label>
                  </>
                )}
                <button type="submit" disabled={createClaim.isPending || !selectedClaimEvidence}>
                  {t("createClaim")}
                </button>
                {createClaim.isError && (
                  <p className="form-error" role="alert">
                    {t("actionError")}
                  </p>
                )}
              </form>
            </details>
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
                        {t(`claimOrigins.${claim.origin_type}`, {
                          defaultValue: claim.origin_type,
                        })}
                      </span>
                    </div>
                    <p style={{ margin: "6px 0" }}>{statement}</p>
                    {claim.confidence !== null && (
                      <small style={{ color: "var(--muted)" }}>
                        {t("confidence")}: {Math.round(claim.confidence * 100)}%
                      </small>
                    )}
                    {claimAssessment.claimId === claim.id ? (
                      <form
                        style={{ marginTop: "0.75rem", display: "grid", gap: "0.5rem" }}
                        onSubmit={(event) => {
                          event.preventDefault();
                          assess.mutate();
                        }}
                      >
                        {claim.origin_type === "HUMAN" &&
                        claim.origin_actor_user_id === currentUser.data?.id ? (
                          <input type="hidden" value="RETRACTED" />
                        ) : (
                          <label>
                            {t("assessmentOutcome")}
                            <select
                              value={claimAssessment.outcome}
                              onChange={(event) =>
                                setClaimAssessment({
                                  ...claimAssessment,
                                  outcome: event.target.value as typeof claimAssessment.outcome,
                                })
                              }
                            >
                              {(["VALIDATED", "REJECTED", "INSUFFICIENT_EVIDENCE"] as const).map(
                                (outcome) => (
                                  <option key={outcome} value={outcome}>
                                    {t(`claimStates.${outcome}`)}
                                  </option>
                                ),
                              )}
                            </select>
                          </label>
                        )}
                        <label>
                          {t("assessmentExplanation")}
                          <textarea
                            required
                            minLength={1}
                            maxLength={4000}
                            rows={2}
                            value={claimAssessment.explanation}
                            onChange={(event) =>
                              setClaimAssessment({
                                ...claimAssessment,
                                explanation: event.target.value,
                              })
                            }
                          />
                        </label>
                        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                          <button type="submit" disabled={assess.isPending}>
                            {t("recordAssessment")}
                          </button>
                          <button
                            type="button"
                            className="ghost"
                            onClick={() =>
                              setClaimAssessment({
                                claimId: "",
                                outcome: "VALIDATED",
                                explanation: "",
                              })
                            }
                          >
                            {t("cancel")}
                          </button>
                        </div>
                        {assess.isError && (
                          <p className="form-error" role="alert">
                            {t("actionError")}
                          </p>
                        )}
                      </form>
                    ) : (
                      <button
                        type="button"
                        className="ghost"
                        style={{ marginTop: "0.75rem" }}
                        onClick={() => {
                          const ownHumanClaim =
                            claim.origin_type === "HUMAN" &&
                            claim.origin_actor_user_id === currentUser.data?.id;
                          setClaimAssessment({
                            claimId: claim.id,
                            outcome: ownHumanClaim ? "RETRACTED" : "VALIDATED",
                            explanation: "",
                          });
                        }}
                      >
                        {claim.origin_type === "HUMAN" &&
                        claim.origin_actor_user_id === currentUser.data?.id
                          ? t("retractClaim")
                          : t("assessClaim")}
                      </button>
                    )}
                    {claims.data &&
                      claims.data.length > 1 &&
                      (claimRelation.sourceClaimId === claim.id ? (
                        <form
                          style={{ marginTop: "0.75rem", display: "grid", gap: "0.5rem" }}
                          onSubmit={(event) => {
                            event.preventDefault();
                            relate.mutate();
                          }}
                        >
                          <label>
                            {t("claimRelationship")}
                            <select
                              value={claimRelation.relationshipType}
                              onChange={(event) =>
                                setClaimRelation({
                                  ...claimRelation,
                                  relationshipType: event.target
                                    .value as typeof claimRelation.relationshipType,
                                })
                              }
                            >
                              {(
                                [
                                  "SUPPORTS",
                                  "CONTRADICTS",
                                  "DERIVED_FROM",
                                  "SUPERSEDES",
                                  "RESPONDS_TO",
                                ] as const
                              ).map((relationship) => (
                                <option key={relationship} value={relationship}>
                                  {t(`claimRelationships.${relationship}`)}
                                </option>
                              ))}
                            </select>
                          </label>
                          <label>
                            {t("targetClaim")}
                            <select
                              value={claimRelation.targetClaimId}
                              onChange={(event) =>
                                setClaimRelation({
                                  ...claimRelation,
                                  targetClaimId: event.target.value,
                                })
                              }
                            >
                              {claims.data
                                .filter((item) => item.id !== claim.id)
                                .map((item) => (
                                  <option key={item.id} value={item.id}>
                                    {item.claim_type} · {item.statement}
                                  </option>
                                ))}
                            </select>
                          </label>
                          <button
                            type="submit"
                            disabled={relate.isPending || !claimRelation.targetClaimId}
                          >
                            {t("recordRelationship")}
                          </button>
                          {relate.isError && (
                            <p className="form-error" role="alert">
                              {t("actionError")}
                            </p>
                          )}
                        </form>
                      ) : (
                        <button
                          type="button"
                          className="ghost"
                          style={{ marginTop: "0.5rem" }}
                          onClick={() =>
                            setClaimRelation({
                              sourceClaimId: claim.id,
                              targetClaimId:
                                claims.data!.find((item) => item.id !== claim.id)?.id ?? "",
                              relationshipType: "SUPPORTS",
                            })
                          }
                        >
                          {t("relateClaim")}
                        </button>
                      ))}
                    {claimPresentation.claimId === claim.id ? (
                      <form
                        style={{ marginTop: "0.75rem", display: "grid", gap: "0.5rem" }}
                        onSubmit={(event) => {
                          event.preventDefault();
                          presentClaim.mutate();
                        }}
                      >
                        <label>
                          {t("presentationLocale")}
                          <select
                            value={claimPresentation.locale}
                            onChange={(event) =>
                              setClaimPresentation({
                                ...claimPresentation,
                                locale: event.target.value as "es" | "en",
                              })
                            }
                          >
                            <option value="es">Español</option>
                            <option value="en">English</option>
                          </select>
                        </label>
                        <label>
                          {t("translatedPresentation")}
                          <textarea
                            required
                            minLength={1}
                            maxLength={2000}
                            rows={3}
                            value={claimPresentation.text}
                            onChange={(event) =>
                              setClaimPresentation({
                                ...claimPresentation,
                                text: event.target.value,
                              })
                            }
                          />
                        </label>
                        <button type="submit" disabled={presentClaim.isPending}>
                          {t("savePresentation")}
                        </button>
                        {presentClaim.isError && (
                          <p className="form-error" role="alert">
                            {t("actionError")}
                          </p>
                        )}
                      </form>
                    ) : (
                      <button
                        type="button"
                        className="ghost"
                        style={{ marginTop: "0.5rem" }}
                        onClick={() =>
                          setClaimPresentation({
                            claimId: claim.id,
                            locale: claim.language_code === "es" ? "en" : "es",
                            text: "",
                          })
                        }
                      >
                        {t("addPresentation")}
                      </button>
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
                  const countApproved = decision.decisions.filter(
                    (entry) => entry.decision === "APPROVE",
                  ).length;
                  const totalApprovals = decision.required_approvals;
                  const hasRequiredApprovals =
                    totalApprovals > 0 && countApproved >= totalApprovals;
                  return (
                    <article
                      className="claim-card"
                      key={decision.id}
                      style={{ borderLeft: "3px solid var(--accent)" }}
                    >
                      <div className="claim-badges" style={{ marginBottom: "8px" }}>
                        <span className="severity">{decision.status}</span>
                        <span>{decision.impact}</span>
                      </div>
                      <strong
                        style={{ fontSize: "1.05rem", display: "block", marginBottom: "4px" }}
                      >
                        {decision.action_type}
                      </strong>
                      <div
                        style={{
                          background: "var(--panel-raised)",
                          padding: "6px 10px",
                          borderRadius: "4px",
                          margin: "6px 0",
                          fontSize: "0.825rem",
                        }}
                      >
                        🎯 <span style={{ color: "var(--muted)" }}>{t("target")}:</span>{" "}
                        <strong style={{ fontFamily: "var(--font-mono, monospace)" }}>
                          {decision.targets && decision.targets.length > 0
                            ? decision.targets.join(", ")
                            : t("notAvailable")}
                        </strong>
                      </div>
                      <small
                        style={{ color: "var(--text-soft)", display: "block", marginTop: "4px" }}
                      >
                        📅 {new Date(decision.created_at).toLocaleString(i18n.language)}
                      </small>
                      <small style={{ color: "var(--muted)", display: "block", marginTop: "2px" }}>
                        {t("approvalSummary", {
                          approved: countApproved,
                          total: totalApprovals,
                          evaluation: decision.evaluation_outcome,
                        })}{" "}
                        {totalApprovals >= 2 && hasRequiredApprovals && (
                          <span style={{ color: "var(--accent)", marginLeft: "4px" }}>
                            ✓ {t("fourEyesApproved")}
                          </span>
                        )}
                      </small>
                      <div
                        style={{
                          fontSize: "0.8rem",
                          color: "var(--muted)",
                          marginTop: "6px",
                          display: "flex",
                          flexDirection: "column",
                          gap: "2px",
                          background: "var(--panel-raised)",
                          padding: "6px 10px",
                          borderRadius: "4px",
                        }}
                      >
                        <span>
                          <strong>{t("requester")}:</strong>{" "}
                          {decision.requester_user_id === currentUser.data?.id
                            ? (currentUser.data?.email ?? decision.requester_user_id)
                            : decision.requester_user_id}
                        </span>
                        {decision.decisions.map((entry) => (
                          <span key={entry.id}>
                            {t("decisionRecordedBy", {
                              decision: entry.decision,
                              actor: entry.actor_user_id,
                            })}
                            {" — "}
                            {entry.reason}
                          </span>
                        ))}
                      </div>
                      {decision.approval_request_id &&
                        decision.approval_status === "PENDING" &&
                        (currentUser.data?.id !== decision.requester_user_id ? (
                          <div
                            style={{
                              display: "flex",
                              gap: "8px",
                              marginTop: "10px",
                              flexWrap: "wrap",
                            }}
                          >
                            <textarea
                              aria-label={t("approvalReason")}
                              placeholder={t("approvalReasonPlaceholder")}
                              minLength={1}
                              maxLength={1000}
                              required
                              value={approvalReasons[decision.approval_request_id!] ?? ""}
                              onChange={(event) =>
                                setApprovalReasons((current) => ({
                                  ...current,
                                  [decision.approval_request_id!]: event.target.value,
                                }))
                              }
                              style={{ flexBasis: "100%", minHeight: "72px" }}
                            />
                            <button
                              type="button"
                              style={{ flex: 1, padding: "4px 8px", fontSize: "0.8rem" }}
                              disabled={
                                approvalDecision.isPending ||
                                !(approvalReasons[decision.approval_request_id!] ?? "").trim()
                              }
                              onClick={() =>
                                approvalDecision.mutate({
                                  requestId: decision.approval_request_id!,
                                  decision: "APPROVE",
                                  fingerprint: decision.fingerprint,
                                  reason: approvalReasons[decision.approval_request_id!] ?? "",
                                })
                              }
                            >
                              ✓ {t("approveResponse")}
                            </button>
                            <button
                              type="button"
                              className="ghost"
                              style={{ flex: 1, padding: "4px 8px", fontSize: "0.8rem" }}
                              disabled={
                                approvalDecision.isPending ||
                                !(approvalReasons[decision.approval_request_id!] ?? "").trim()
                              }
                              onClick={() =>
                                approvalDecision.mutate({
                                  requestId: decision.approval_request_id!,
                                  decision: "REJECT",
                                  fingerprint: decision.fingerprint,
                                  reason: approvalReasons[decision.approval_request_id!] ?? "",
                                })
                              }
                            >
                              ✕ {t("rejectResponse")}
                            </button>
                          </div>
                        ) : (
                          <p
                            style={{
                              margin: "8px 0 0",
                              fontSize: "0.8rem",
                              color: "var(--text-soft)",
                              background: "var(--panel-raised)",
                              padding: "6px 10px",
                              borderRadius: "4px",
                            }}
                          >
                            🔒 {t("awaitingSecondAnalystNotice")}
                          </p>
                        ))}
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
            </div>

            <div style={{ marginTop: "1.5rem" }}>
              <h3 style={{ fontSize: "1rem", marginBottom: "0.75rem" }}>
                📋 {t("immutableAuditTimeline")}
              </h3>
              <div className="timeline" style={{ marginTop: "0.5rem" }}>
                {timeline.data?.map((entry) => (
                  <div
                    key={entry.id}
                    style={{
                      background: "var(--panel-raised)",
                      border: "1px solid var(--line)",
                      borderRadius: "6px",
                      padding: "10px 14px",
                      marginBottom: "8px",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        marginBottom: "4px",
                      }}
                    >
                      <span
                        className="severity"
                        style={{ fontSize: "0.75rem", textTransform: "uppercase" }}
                      >
                        {entry.entry_type}
                      </span>
                      <time
                        dateTime={entry.recorded_at}
                        style={{ fontSize: "0.8rem", color: "var(--muted)" }}
                      >
                        📅 {new Date(entry.recorded_at).toLocaleString(i18n.language)}
                      </time>
                    </div>
                    <p style={{ margin: "4px 0 0", fontSize: "0.875rem", color: "var(--text)" }}>
                      {entry.summary}
                    </p>
                  </div>
                ))}
                <PageState
                  loading={timeline.isLoading}
                  error={timeline.isError}
                  empty={!timeline.isLoading && !timeline.isError && timeline.data?.length === 0}
                />
              </div>
            </div>
          </section>
        </div>
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
          {items.map((event) => {
            const recordedActor = event.details?.actor_email;
            const actorLabel =
              typeof recordedActor === "string" && recordedActor.trim()
                ? recordedActor
                : (event.actor_user_id ?? t("systemActor"));
            const recordedClientIp = event.details?.client_ip;
            const clientIp =
              typeof recordedClientIp === "string" && recordedClientIp.trim()
                ? recordedClientIp
                : t("notAvailable");
            return (
              <article
                key={event.id}
                style={{
                  display: "grid",
                  gridTemplateColumns: "100px 1.5fr 1.2fr 1fr 160px",
                  alignItems: "center",
                  gap: "12px",
                }}
              >
                <span className="severity" style={{ textAlign: "center" }}>
                  {event.outcome}
                </span>
                <div>
                  <strong style={{ fontSize: "0.95rem" }}>{event.action}</strong>
                  <small style={{ display: "block", color: "var(--muted)" }}>
                    {event.resource_type}
                  </small>
                </div>
                <div
                  style={{
                    display: "flex",
                    flexDirection: "row",
                    alignItems: "center",
                    gap: "6px",
                    fontSize: "0.85rem",
                    color: "var(--text-soft)",
                  }}
                >
                  <span style={{ fontSize: "0.95rem", lineHeight: 1 }}>👤</span>
                  <strong style={{ whiteSpace: "nowrap" }}>{actorLabel}</strong>
                </div>
                <div
                  style={{
                    display: "flex",
                    flexDirection: "row",
                    alignItems: "center",
                    gap: "6px",
                    fontSize: "0.85rem",
                    color: "var(--muted)",
                    fontFamily: "var(--font-mono, monospace)",
                  }}
                >
                  <span style={{ fontSize: "0.95rem", lineHeight: 1 }}>🌐</span>
                  <span style={{ whiteSpace: "nowrap" }}>{clientIp}</span>
                </div>
                <time
                  dateTime={event.occurred_at}
                  style={{ fontSize: "0.8rem", color: "var(--muted)", textAlign: "right" }}
                >
                  📅 {new Date(event.occurred_at).toLocaleString(i18n.language)}
                </time>
              </article>
            );
          })}
        </div>
      </section>
    </>
  );
}

function Administration() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState("");
  const [directoryIdentityMessage, setDirectoryIdentityMessage] = useState("");
  const [selectedUser, setSelectedUser] = useState("");
  const [selectedRole, setSelectedRole] = useState("");
  const [showCreateUser, setShowCreateUser] = useState(false);
  const [directoryMappingDrafts, setDirectoryMappingDrafts] = useState<
    Array<{
      external_group: string;
      role_id: string;
    }>
  >([]);
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
  const selectedRoleIsSystem = Boolean(
    roles.data?.find((role) => role.id === selectedRole)?.is_system,
  );
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
  const selectedAdminUser = userOptions.data?.find((user) => user.id === selectedUser);
  const directory = useQuery({
    queryKey: ["directory-configuration"],
    queryFn: getDirectoryConfiguration,
    retry: false,
  });
  const directoryMappings = useQuery({
    queryKey: ["directory-group-mappings"],
    queryFn: getDirectoryGroupMappings,
  });
  useEffect(() => {
    if (directoryMappings.data) {
      setDirectoryMappingDrafts(
        directoryMappings.data.map(({ external_group, role_id }) => ({
          external_group,
          role_id,
        })),
      );
    }
  }, [directoryMappings.data]);
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
  const userAccountMutation = useMutation({
    mutationFn: ({
      userId,
      displayName,
      isActive,
    }: {
      userId: string;
      displayName: string;
      isActive: boolean;
    }) => updateUser(userId, { display_name: displayName, is_active: isActive }),
    onSuccess: async () => {
      setFormError("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["users"] }),
        queryClient.invalidateQueries({ queryKey: ["audit-events"] }),
      ]);
    },
    onError: () => setFormError(t("adminMutationError")),
  });
  const userPasswordMutation = useMutation({
    mutationFn: ({ userId, password }: { userId: string; password: string }) =>
      replaceUserPassword(userId, password),
    onSuccess: async () => {
      setFormError("");
      await queryClient.invalidateQueries({ queryKey: ["audit-events"] });
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
  const directoryActivationMutation = useMutation({
    mutationFn: (enabled: boolean) =>
      enabled ? activateDirectoryConfiguration() : disableDirectoryConfiguration(),
    onSuccess: async () => {
      setFormError("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["directory-configuration"] }),
        queryClient.invalidateQueries({ queryKey: ["audit-events"] }),
      ]);
    },
    onError: () => setFormError(t("adminMutationError")),
  });
  const directoryMappingsMutation = useMutation({
    mutationFn: () =>
      replaceDirectoryGroupMappings(
        directoryMappingDrafts.map((item) => ({
          external_group: item.external_group.trim(),
          role_id: item.role_id,
        })),
      ),
    onSuccess: async (items) => {
      setFormError("");
      setDirectoryMappingDrafts(
        items.map(({ external_group, role_id }) => ({ external_group, role_id })),
      );
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["directory-group-mappings"] }),
        queryClient.invalidateQueries({ queryKey: ["audit-events"] }),
      ]);
    },
    onError: () => setFormError(t("adminMutationError")),
  });
  const directoryIdentityLinkMutation = useMutation({
    mutationFn: ({
      userId,
      externalSubject,
      normalizedUsername,
    }: {
      userId: string;
      externalSubject: string;
      normalizedUsername: string;
    }) =>
      linkUserDirectoryIdentity(userId, {
        external_subject: externalSubject,
        normalized_username: normalizedUsername,
      }),
    onSuccess: async () => {
      setFormError("");
      setDirectoryIdentityMessage(t("directoryIdentityLinked"));
      await queryClient.invalidateQueries({ queryKey: ["audit-events"] });
    },
    onError: () => setFormError(t("adminMutationError")),
  });
  const directoryIdentityUnlinkMutation = useMutation({
    mutationFn: unlinkUserDirectoryIdentity,
    onSuccess: async () => {
      setFormError("");
      setDirectoryIdentityMessage(t("directoryIdentityUnlinked"));
      await queryClient.invalidateQueries({ queryKey: ["audit-events"] });
    },
    onError: () => setFormError(t("adminMutationError")),
  });
  const mappableDirectoryRoles = (roles.data ?? []).filter((role) => role.code !== "tenant-admin");
  const normalizedDirectoryMappings = directoryMappingDrafts.map(
    (item) => `${item.external_group.trim().toLowerCase()}\u0000${item.role_id}`,
  );
  const directoryMappingsInvalid =
    directoryMappingDrafts.some((item) => !item.external_group.trim() || !item.role_id) ||
    new Set(normalizedDirectoryMappings).size !== normalizedDirectoryMappings.length;
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
      setShowCreateUser(false);
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
      group_base_dn: String(data.get("group_base_dn")) || null,
      group_filter: String(data.get("group_filter")) || null,
      group_attribute: String(data.get("group_attribute")) || null,
      ca_certificate_pem: String(data.get("ca_certificate_pem")) || null,
      jit_enabled: data.get("jit_enabled") === "on",
      timeout_seconds: Number(data.get("timeout_seconds")) || 5,
    });
  };
  const [activeSubTab, setActiveSubTab] = useState<"overview" | "users" | "rbac" | "directory">(
    "overview",
  );

  return (
    <>
      <div className="page-title">
        <div>
          <p className="eyebrow">{t("controlPlane")}</p>
          <h1>{t("administration")}</h1>
          <p className="muted">{t("administrationIntro")}</p>
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
            <span style={{ fontSize: "0.75rem", opacity: 0.8, fontWeight: 600 }}>
              ({userOptions.data?.length ?? 0})
            </span>
          </button>
          <button
            type="button"
            className={`admin-sub-tab-button ${activeSubTab === "rbac" ? "active" : ""}`}
            onClick={() => setActiveSubTab("rbac")}
          >
            <span>Roles & RBAC</span>
            <span style={{ fontSize: "0.75rem", opacity: 0.8, fontWeight: 600 }}>
              ({roles.data?.length ?? 0})
            </span>
          </button>
          <button
            type="button"
            className={`admin-sub-tab-button ${activeSubTab === "directory" ? "active" : ""}`}
            onClick={() => setActiveSubTab("directory")}
          >
            <span>Directorio LDAP / AD</span>
            <span
              style={{
                fontSize: "0.65rem",
                padding: "2px 6px",
                borderRadius: "4px",
                background: directory.data ? "rgba(13,209,155,0.15)" : "rgba(255,255,255,0.08)",
                color: directory.data ? "var(--accent)" : "var(--muted)",
                fontWeight: 700,
                whiteSpace: "nowrap",
              }}
            >
              {directory.data ? "CONFIGURADO" : "PENDIENTE"}
            </span>
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
            <div className="admin-users-layout">
              {/* Left column: creating a user happens inline, inside the same card as the
                  list it will populate, and every row previews that it opens the panel
                  on the right. */}
              <div className="admin-users-directory">
                <section className="panel admin-panel admin-users-panel">
                  <div>
                    <div className="admin-panel-header">
                      <h2>{t("users")}</h2>
                      <button
                        type="button"
                        className={`admin-inline-toggle${showCreateUser ? " active" : ""}`}
                        aria-expanded={showCreateUser}
                        onClick={() => setShowCreateUser((value) => !value)}
                      >
                        <svg
                          width="15"
                          height="15"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          className="admin-inline-toggle-icon"
                        >
                          <line x1="12" y1="5" x2="12" y2="19" />
                          <line x1="5" y1="12" x2="19" y2="12" />
                        </svg>
                        {showCreateUser ? t("cancel") : t("createUser")}
                      </button>
                    </div>

                    {showCreateUser && (
                      <form
                        className="admin-inline-create-form"
                        autoComplete="off"
                        onSubmit={submitUser}
                      >
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
                        <div className="form-actions">
                          <button disabled={userMutation.isPending}>{t("create")}</button>
                          <button
                            type="button"
                            className="ghost"
                            onClick={() => setShowCreateUser(false)}
                          >
                            {t("cancel")}
                          </button>
                        </div>
                      </form>
                    )}

                    <p className="muted admin-list-hint">{t("selectUserHint")}</p>

                    <ListControls
                      state={userControls}
                      visibleCount={visibleUsers.length}
                      hasNext={(users.data?.length ?? 0) > userControls.pageSize}
                      compact
                    />
                    <div className="admin-list admin-list-selectable">
                      {visibleUsers.map((user) => (
                        <div
                          key={user.id}
                          className={`admin-list-row${selectedUser === user.id ? " selected" : ""}`}
                          role="button"
                          tabIndex={0}
                          onClick={() => {
                            setSelectedUser(user.id);
                            setDirectoryIdentityMessage("");
                          }}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              setSelectedUser(user.id);
                              setDirectoryIdentityMessage("");
                            }
                          }}
                        >
                          <div className="admin-list-row-info">
                            <strong>{user.display_name}</strong>
                            <span>{user.email}</span>
                            <small>{user.is_active ? t("active") : t("inactive")}</small>
                          </div>
                          <svg
                            width="16"
                            height="16"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            className="admin-list-row-chevron"
                          >
                            <polyline points="9 18 15 12 9 6" />
                          </svg>
                        </div>
                      ))}
                    </div>
                  </div>
                </section>
              </div>

              {/* Right column: everything that acts on one selected user — account,
                  password, roles, directory identity — grouped under one heading.
                  Highlighted whenever a row on the left is selected, to make the
                  click -> panel relationship visible. */}
              <section className={`panel admin-user-detail${selectedUser ? " has-selection" : ""}`}>
                <div className="admin-user-detail-header">
                  <div>
                    <p className="eyebrow">{t("identity")}</p>
                    <h2>{selectedAdminUser?.display_name ?? t("manageUser")}</h2>
                    {selectedAdminUser && <p className="muted">{selectedAdminUser.email}</p>}
                  </div>
                  <select
                    value={selectedUser}
                    onChange={(event) => {
                      setSelectedUser(event.target.value);
                      setDirectoryIdentityMessage("");
                    }}
                  >
                    <option value="">{t("selectUser")}</option>
                    {userOptions.data?.map((user) => (
                      <option key={user.id} value={user.id}>
                        {user.display_name}
                      </option>
                    ))}
                  </select>
                </div>

                {!selectedUser && (
                  <div className="admin-user-detail-empty">
                    <svg
                      width="26"
                      height="26"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <polyline points="15 18 9 12 15 6" />
                    </svg>
                    <p className="muted">{t("selectedAccountRequired")}</p>
                  </div>
                )}

                {selectedUser && (
                  <div className="admin-user-detail-grid">
                    <form
                      key={`account-${selectedAdminUser?.id}-${selectedAdminUser?.display_name}-${selectedAdminUser?.is_active}`}
                      className="admin-user-detail-section"
                      onSubmit={(event) => {
                        event.preventDefault();
                        if (!selectedAdminUser) {
                          setFormError(t("selectedAccountRequired"));
                          return;
                        }
                        const data = new FormData(event.currentTarget);
                        userAccountMutation.mutate({
                          userId: selectedAdminUser.id,
                          displayName: String(data.get("display_name")).trim(),
                          isActive: data.get("is_active") === "on",
                        });
                      }}
                    >
                      <h3>{t("manageUser")}</h3>
                      <label>
                        {t("displayName")}
                        <input
                          name="display_name"
                          required
                          minLength={1}
                          maxLength={200}
                          defaultValue={selectedAdminUser?.display_name ?? ""}
                          disabled={!selectedAdminUser}
                        />
                      </label>
                      <label className="check-row">
                        <input
                          type="checkbox"
                          name="is_active"
                          defaultChecked={selectedAdminUser?.is_active ?? false}
                          disabled={!selectedAdminUser}
                        />
                        {t("accountActive")}
                      </label>
                      <button disabled={!selectedAdminUser || userAccountMutation.isPending}>
                        {t("save")}
                      </button>
                    </form>

                    <form
                      className="admin-user-detail-section"
                      autoComplete="off"
                      onSubmit={async (event) => {
                        event.preventDefault();
                        if (!selectedAdminUser) {
                          setFormError(t("selectedAccountRequired"));
                          return;
                        }
                        const form = event.currentTarget;
                        const password = String(new FormData(form).get("password"));
                        try {
                          await userPasswordMutation.mutateAsync({
                            userId: selectedAdminUser.id,
                            password,
                          });
                          form.reset();
                        } catch {
                          // The mutation keeps the form available and exposes a localized error.
                        }
                      }}
                    >
                      <h3>{t("replacePassword")}</h3>
                      <label>
                        {t("newPassword")}
                        <input
                          name="password"
                          type="password"
                          autoComplete="new-password"
                          required
                          minLength={12}
                          maxLength={256}
                          disabled={!selectedAdminUser}
                        />
                      </label>
                      <button disabled={!selectedAdminUser || userPasswordMutation.isPending}>
                        {t("replacePassword")}
                      </button>
                    </form>

                    <form
                      key={`user-${selectedUser}-${userRoles.data?.join("-")}`}
                      className="admin-user-detail-section"
                      onSubmit={submitUserRoles}
                    >
                      <h3>{t("assignRoles")}</h3>
                      {roles.data?.map((role) => (
                        <label className="check-row" key={role.id}>
                          <input
                            type="checkbox"
                            name="role_ids"
                            value={role.id}
                            defaultChecked={userRoles.data?.includes(role.id)}
                          />
                          {role.name}
                        </label>
                      ))}
                      <button disabled={userRolesMutation.isPending}>{t("save")}</button>
                    </form>

                    <form
                      className="admin-user-detail-section admin-user-detail-section-wide"
                      autoComplete="off"
                      onSubmit={(event) => {
                        event.preventDefault();
                        const data = new FormData(event.currentTarget);
                        directoryIdentityLinkMutation.mutate({
                          userId: selectedUser,
                          externalSubject: String(data.get("external_subject")).trim(),
                          normalizedUsername: String(data.get("normalized_username")).trim(),
                        });
                      }}
                    >
                      <h3>{t("directoryIdentityLink")}</h3>
                      <p className="muted">{t("directoryIdentityLinkHelp")}</p>
                      <div className="admin-user-detail-field-row">
                        <label>
                          {t("externalSubject")}
                          <input name="external_subject" required maxLength={1000} />
                        </label>
                        <label>
                          {t("normalizedUsername")}
                          <input name="normalized_username" required maxLength={256} />
                        </label>
                      </div>
                      <div className="form-actions">
                        <button type="submit" disabled={directoryIdentityLinkMutation.isPending}>
                          {t("linkIdentity")}
                        </button>
                        <button
                          className="ghost"
                          type="button"
                          disabled={directoryIdentityUnlinkMutation.isPending}
                          onClick={() => directoryIdentityUnlinkMutation.mutate(selectedUser)}
                        >
                          {t("unlinkIdentity")}
                        </button>
                      </div>
                      {directoryIdentityMessage && (
                        <p className="status-message" role="status">
                          {directoryIdentityMessage}
                        </p>
                      )}
                    </form>
                  </div>
                )}
              </section>
            </div>
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
                <select
                  value={selectedRole}
                  onChange={(event) => setSelectedRole(event.target.value)}
                >
                  <option value="">{t("selectRole")}</option>
                  {/* Grouped rather than suffixed: almost every role is a
                      system role now, so repeating the word on each line said
                      nothing. System roles stay selectable because they are
                      immutable, not secret -- whoever hands out a role needs to
                      see what it grants, and an auditor needs to check it. */}
                  <optgroup label={t("systemRoles")}>
                    {roles.data
                      ?.filter((role) => role.is_system)
                      .map((role) => (
                        <option key={role.id} value={role.id}>
                          {role.name}
                        </option>
                      ))}
                  </optgroup>
                  <optgroup label={t("customRoles")}>
                    {roles.data
                      ?.filter((role) => !role.is_system)
                      .map((role) => (
                        <option key={role.id} value={role.id}>
                          {role.name}
                        </option>
                      ))}
                  </optgroup>
                </select>
                {selectedRoleIsSystem && (
                  <p className="status-message">{t("systemRoleImmutable")}</p>
                )}
                {selectedRole && permissions.data && (
                  <PermissionMatrix
                    permissions={permissions.data}
                    granted={new Set(rolePermissions.data ?? [])}
                    readOnly={selectedRoleIsSystem}
                  />
                )}
                {!selectedRoleIsSystem && (
                  <button disabled={!selectedRole || rolePermissionsMutation.isPending}>
                    {t("save")}
                  </button>
                )}
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
                <label>
                  {t("groupBaseDn")}
                  <input name="group_base_dn" defaultValue={directory.data?.group_base_dn ?? ""} />
                </label>
                <label>
                  {t("groupFilter")}
                  <input name="group_filter" defaultValue={directory.data?.group_filter ?? ""} />
                </label>
                <label>
                  {t("directoryTimeout")}
                  <input
                    name="timeout_seconds"
                    type="number"
                    min={1}
                    max={30}
                    required
                    defaultValue={directory.data?.timeout_seconds ?? 5}
                  />
                </label>
                <label>
                  {t("caCertificate")}
                  <textarea
                    name="ca_certificate_pem"
                    rows={4}
                    maxLength={100000}
                    autoComplete="off"
                    placeholder={
                      directory.data?.has_ca_certificate
                        ? t("caCertificateStored")
                        : t("caCertificateOptional")
                    }
                  />
                </label>
                <label className="check-row">
                  <input
                    name="jit_enabled"
                    type="checkbox"
                    defaultChecked={directory.data?.jit_enabled}
                  />
                  {t("jitProvisioning")}
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
                {directory.data?.status === "active" ? (
                  <button
                    className="ghost"
                    type="button"
                    disabled={directoryActivationMutation.isPending}
                    onClick={() => directoryActivationMutation.mutate(false)}
                  >
                    {t("disable")}
                  </button>
                ) : (
                  <button
                    className="ghost"
                    type="button"
                    disabled={
                      !directory.data?.last_test_success || directoryActivationMutation.isPending
                    }
                    onClick={() => directoryActivationMutation.mutate(true)}
                  >
                    {t("activate")}
                  </button>
                )}
              </div>
            </form>
          )}

          {activeSubTab === "directory" && (
            <section className="panel directory-panel" style={{ marginTop: "1rem" }}>
              <div>
                <p className="eyebrow">LDAP / Active Directory</p>
                <h2>{t("directoryGroupMappings")}</h2>
                <p className="muted">{t("directoryGroupMappingsHelp")}</p>
              </div>
              {directoryMappings.isError && <p className="form-error">{t("loadError")}</p>}
              <div className="form-grid">
                {directoryMappingDrafts.map((mapping, index) => (
                  <div className="directory-grid" key={`${index}-${mapping.role_id}`}>
                    <label>
                      {t("externalDirectoryGroup")}
                      <input
                        required
                        maxLength={1000}
                        value={mapping.external_group}
                        onChange={(event) =>
                          setDirectoryMappingDrafts((current) =>
                            current.map((item, itemIndex) =>
                              itemIndex === index
                                ? { ...item, external_group: event.target.value }
                                : item,
                            ),
                          )
                        }
                      />
                    </label>
                    <label>
                      {t("mappedRole")}
                      <select
                        required
                        value={mapping.role_id}
                        onChange={(event) =>
                          setDirectoryMappingDrafts((current) =>
                            current.map((item, itemIndex) =>
                              itemIndex === index ? { ...item, role_id: event.target.value } : item,
                            ),
                          )
                        }
                      >
                        <option value="">{t("selectRole")}</option>
                        {mappableDirectoryRoles.map((role) => (
                          <option key={role.id} value={role.id}>
                            {role.name} ({role.code})
                          </option>
                        ))}
                      </select>
                    </label>
                    <button
                      className="ghost"
                      type="button"
                      onClick={() =>
                        setDirectoryMappingDrafts((current) =>
                          current.filter((_, itemIndex) => itemIndex !== index),
                        )
                      }
                    >
                      {t("removeMapping")}
                    </button>
                  </div>
                ))}
              </div>
              <div className="form-actions">
                <button
                  className="ghost"
                  type="button"
                  disabled={directoryMappingDrafts.length >= 100}
                  onClick={() =>
                    setDirectoryMappingDrafts((current) => [
                      ...current,
                      { external_group: "", role_id: "" },
                    ])
                  }
                >
                  {t("addMapping")}
                </button>
                <button
                  type="button"
                  disabled={directoryMappingsInvalid || directoryMappingsMutation.isPending}
                  onClick={() => directoryMappingsMutation.mutate()}
                >
                  {t("saveMappings")}
                </button>
              </div>
            </section>
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

function RouteLoadingFallback() {
  const { t } = useTranslation();
  return (
    <main className="center" role="status">
      <p>{t("loading")}</p>
    </main>
  );
}

export default function App() {
  return (
    <Suspense fallback={<RouteLoadingFallback />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route index element={<Overview />} />
            <Route path="alerts" element={<AlertsPage />} />
            <Route path="incidents" element={<IncidentsPage />} />
            <Route path="incidents/:id" element={<IncidentDetailPage />} />
            <Route path="playbooks" element={<PlaybooksPage />} />
            <Route path="integrations" element={<VerifiedIntegrationsPage />} />
            <Route path="memory" element={<GovernedMemoryPage />} />

            <Route path="audit" element={<AuditPage />} />
            <Route path="administration" element={<Administration />} />
          </Route>
        </Route>
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
}
