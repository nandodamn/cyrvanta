import { z } from "zod";

export const userSchema = z.object({
  id: z.string().uuid(),
  tenant_id: z.string().uuid(),
  email: z.string().email(),
  display_name: z.string(),
});
export type CurrentUser = z.infer<typeof userSchema>;

const tenantSchema = z.object({
  id: z.string().uuid(),
  slug: z.string(),
  name: z.string(),
  status: z.string(),
});
const adminUserSchema = userSchema.extend({ is_active: z.boolean() });
const roleSchema = z.object({
  id: z.string().uuid(),
  code: z.string(),
  name: z.string(),
  is_system: z.boolean(),
});
const permissionSchema = z.object({
  id: z.string().uuid(),
  code: z.string(),
  description: z.string(),
});
const auditEventSchema = z.object({
  id: z.string().uuid(),
  actor_user_id: z.string().uuid().nullable(),
  action: z.string(),
  resource_type: z.string(),
  resource_id: z.string().uuid().nullable(),
  outcome: z.string(),
  correlation_id: z.string().uuid(),
  details: z.record(z.unknown()),
  occurred_at: z.string(),
});
const directoryConfigurationSchema = z.object({
  id: z.string().uuid(),
  provider_type: z.string(),
  status: z.string(),
  server_uri: z.string(),
  use_starttls: z.boolean(),
  base_dn: z.string(),
  bind_dn: z.string(),
  has_bind_secret: z.boolean(),
  user_filter: z.string(),
  login_attribute: z.string(),
  subject_attribute: z.string(),
  email_attribute: z.string(),
  display_name_attribute: z.string(),
  group_base_dn: z.string().nullable(),
  group_filter: z.string().nullable(),
  group_attribute: z.string().nullable(),
  has_ca_certificate: z.boolean(),
  jit_enabled: z.boolean(),
  timeout_seconds: z.number(),
  last_test_success: z.boolean().nullable(),
});
export type Tenant = z.infer<typeof tenantSchema>;
export type AdminUser = z.infer<typeof adminUserSchema>;
export type Role = z.infer<typeof roleSchema>;
export type Permission = z.infer<typeof permissionSchema>;
export type AuditEvent = z.infer<typeof auditEventSchema>;
export type DirectoryConfiguration = z.infer<typeof directoryConfigurationSchema>;
const alertSchema = z.object({
  id: z.string().uuid(),
  source: z.string(),
  external_id: z.string(),
  observed_at: z.string(),
  title: z.string(),
  category: z.string(),
  severity: z.string(),
  asset_summary: z.string().nullable(),
  identity_summary: z.string().nullable(),
  indicator_summary: z.string().nullable(),
  provenance: z.string(),
  is_simulated: z.boolean(),
});
const incidentSchema = z.object({
  id: z.string().uuid(),
  code: z.string(),
  title: z.string(),
  description: z.string(),
  status: z.string(),
  severity: z.string(),
  priority: z.number(),
  classification: z.string(),
  assignee_user_id: z.string().uuid().nullable(),
  version: z.number(),
  is_simulated: z.boolean(),
  detected_at: z.string(),
  acknowledged_at: z.string().nullable(),
  resolved_at: z.string().nullable(),
  closed_at: z.string().nullable(),
  close_reason: z.string().nullable(),
});
const timelineSchema = z.object({
  id: z.string().uuid(),
  actor_user_id: z.string().uuid().nullable(),
  entry_type: z.string(),
  summary: z.string(),
  resource_type: z.string().nullable(),
  resource_id: z.string().uuid().nullable(),
  incident_version: z.number(),
  effective_at: z.string(),
  recorded_at: z.string(),
});
export type Alert = z.infer<typeof alertSchema>;
export type Incident = z.infer<typeof incidentSchema>;
export type TimelineEntry = z.infer<typeof timelineSchema>;
const integrationHealthSchema = z.object({
  code: z.string(),
  mode: z.string(),
  healthy: z.boolean(),
  detail: z.string(),
});
const techniqueSchema = z.object({
  external_id: z.string(),
  name_es: z.string(),
  name_en: z.string(),
  tactic: z.string(),
});
const analysisSchema = z.object({
  incident_id: z.string().uuid(),
  provider: z.string(),
  model: z.string(),
  mode: z.string(),
  summary_es: z.string(),
  summary_en: z.string(),
  confidence: z.number(),
  risk_score: z.number(),
  techniques: z.array(techniqueSchema),
  recommendations: z.array(z.string()),
  grounded: z.boolean(),
});
const playbookConnectorSchema = z.object({
  node_type: z.string(),
  name: z.string(),
  credential_names: z.array(z.string()),
});
const playbookSummarySchema = z.object({
  workflow_id: z.string(),
  name: z.string(),
  active: z.boolean().nullable(),
  registered: z.boolean(),
  version_id: z.string().nullable(),
  connectors: z.array(playbookConnectorSchema),
});
const playbookCatalogSchema = z.object({
  items: z.array(playbookSummarySchema),
  total: z.number().int().nonnegative(),
  synchronized: z.boolean(),
  sync_detail: z.string(),
  mode: z.string(),
});
const playbookManagementSchema = z.object({
  editor_url: z.string().url(),
  local_only: z.boolean(),
  api_sync_configured: z.boolean(),
});
export type IntegrationHealth = z.infer<typeof integrationHealthSchema>;
export type Analysis = z.infer<typeof analysisSchema>;
export type PlaybookCatalog = z.infer<typeof playbookCatalogSchema>;
export type PlaybookManagement = z.infer<typeof playbookManagementSchema>;
export type ListQuery = {
  query?: string;
  page?: number;
  pageSize?: number;
  includeLookahead?: boolean;
};

const tokenSchema = z.object({
  access_token: z.string(),
  token_type: z.literal("bearer"),
});
let accessToken: string | null = null;
let refreshInFlight: Promise<boolean> | null = null;
sessionStorage.removeItem("access_token");
sessionStorage.removeItem("refresh_token");

async function checked(response: Response): Promise<unknown> {
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.status === 204 ? undefined : response.json();
}

function acceptAccessToken(data: unknown): void {
  accessToken = tokenSchema.parse(data).access_token;
}

async function refreshAccessToken(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;
  refreshInFlight = (async () => {
    const response = await fetch("/api/v1/auth/refresh", {
      method: "POST",
      credentials: "include",
      headers: { "X-CSRF-Guard": "1" },
    });
    if (!response.ok) {
      accessToken = null;
      return false;
    }
    acceptAccessToken(await response.json());
    return true;
  })().finally(() => {
    refreshInFlight = null;
  });
  return refreshInFlight;
}

export async function restoreSession(): Promise<boolean> {
  return refreshAccessToken();
}

export async function login(
  tenantSlug: string,
  email: string,
  password: string,
  rememberMe: boolean,
): Promise<void> {
  const data = tokenSchema.parse(
    await checked(
      await fetch("/api/v1/auth/login", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tenant_slug: tenantSlug,
          email,
          password,
          remember_me: rememberMe,
        }),
      }),
    ),
  );
  accessToken = data.access_token;
}

export async function directoryLogin(
  tenantSlug: string,
  username: string,
  password: string,
  rememberMe: boolean,
): Promise<void> {
  const data = tokenSchema.parse(
    await checked(
      await fetch("/api/v1/auth/directory/login", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tenant_slug: tenantSlug,
          username,
          password,
          remember_me: rememberMe,
        }),
      }),
    ),
  );
  accessToken = data.access_token;
}

async function authenticatedFetch(path: string, init: RequestInit = {}): Promise<Response> {
  if (!accessToken && !(await refreshAccessToken())) return new Response(null, { status: 401 });
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${accessToken ?? ""}`);
  let response = await fetch(path, { ...init, headers, credentials: "include" });
  if (response.status === 401 && (await refreshAccessToken())) {
    headers.set("Authorization", `Bearer ${accessToken ?? ""}`);
    response = await fetch(path, { ...init, headers, credentials: "include" });
  }
  return response;
}

async function authorized(path: string): Promise<unknown> {
  return checked(await authenticatedFetch(path));
}

function listPath(path: string, options: ListQuery = {}): string {
  const page = Math.max(0, options.page ?? 0);
  const pageSize = Math.min(100, Math.max(1, options.pageSize ?? 25));
  const limit = Math.min(100, pageSize + (options.includeLookahead ? 1 : 0));
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(page * pageSize),
  });
  const query = options.query?.trim();
  if (query) params.set("q", query.slice(0, 100));
  return `${path}?${params.toString()}`;
}

export async function getMe(): Promise<CurrentUser> {
  return userSchema.parse(await authorized("/api/v1/auth/me"));
}

export async function getTenant(): Promise<Tenant> {
  return tenantSchema.parse(await authorized("/api/v1/tenant"));
}

export async function getUsers(options?: ListQuery): Promise<AdminUser[]> {
  return z.array(adminUserSchema).parse(await authorized(listPath("/api/v1/users", options)));
}

export async function getRoles(): Promise<Role[]> {
  return z.array(roleSchema).parse(await authorized("/api/v1/roles"));
}

export async function getPermissions(): Promise<Permission[]> {
  return z.array(permissionSchema).parse(await authorized("/api/v1/permissions"));
}

export async function getUserRoles(userId: string): Promise<string[]> {
  return z.array(z.string().uuid()).parse(await authorized(`/api/v1/users/${userId}/roles`));
}

export async function getRolePermissions(roleId: string): Promise<string[]> {
  return z.array(z.string().uuid()).parse(await authorized(`/api/v1/roles/${roleId}/permissions`));
}

export async function getAuditEvents(options?: ListQuery): Promise<AuditEvent[]> {
  return z
    .array(auditEventSchema)
    .parse(await authorized(listPath("/api/v1/audit-events", options)));
}

async function authorizedMutation(
  path: string,
  method: "POST" | "PATCH" | "PUT",
  body: unknown,
): Promise<unknown> {
  return checked(
    await authenticatedFetch(path, {
      method,
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    }),
  );
}

export async function createUser(input: {
  email: string;
  display_name: string;
  password: string;
}): Promise<AdminUser> {
  return adminUserSchema.parse(await authorizedMutation("/api/v1/users", "POST", input));
}

export async function createRole(input: { code: string; name: string }): Promise<Role> {
  return roleSchema.parse(await authorizedMutation("/api/v1/roles", "POST", input));
}

export async function replaceUserRoles(userId: string, ids: string[]): Promise<void> {
  await authorizedMutation(`/api/v1/users/${userId}/roles`, "PUT", { ids });
}

export async function replaceRolePermissions(roleId: string, ids: string[]): Promise<void> {
  await authorizedMutation(`/api/v1/roles/${roleId}/permissions`, "PUT", { ids });
}

export async function getDirectoryConfiguration(): Promise<DirectoryConfiguration> {
  return directoryConfigurationSchema.parse(await authorized("/api/v1/directory/configuration"));
}

export async function saveDirectoryConfiguration(
  input: Record<string, unknown>,
): Promise<DirectoryConfiguration> {
  return directoryConfigurationSchema.parse(
    await authorizedMutation("/api/v1/directory/configuration", "PUT", input),
  );
}

export async function testDirectoryConfiguration(): Promise<{
  success: boolean;
  detail_code: string;
}> {
  return z
    .object({ success: z.boolean(), detail_code: z.string() })
    .parse(await authorizedMutation("/api/v1/directory/configuration/test", "POST", {}));
}

export async function getAlerts(options?: ListQuery): Promise<Alert[]> {
  return z.array(alertSchema).parse(await authorized(listPath("/api/v1/alerts", options)));
}
export async function getIncidents(options?: ListQuery): Promise<Incident[]> {
  return z.array(incidentSchema).parse(await authorized(listPath("/api/v1/incidents", options)));
}
export async function getIncident(id: string): Promise<Incident> {
  return incidentSchema.parse(await authorized(`/api/v1/incidents/${id}`));
}
export async function getTimeline(id: string): Promise<TimelineEntry[]> {
  return z.array(timelineSchema).parse(await authorized(`/api/v1/incidents/${id}/timeline`));
}
export async function generateDemoScenario() {
  return z
    .object({
      scenario: z.string(),
      incident: incidentSchema,
      alerts_created: z.number(),
      idempotent_replay: z.boolean(),
    })
    .parse(await authorizedMutation("/api/v1/demo/scenarios/credential-attack", "POST", {}));
}
export async function transitionIncident(
  id: string,
  expectedVersion: number,
  targetStatus: string,
) {
  const closing = ["resolved", "closed", "reopened"].includes(targetStatus);
  return incidentSchema.parse(
    await authorizedMutation(`/api/v1/incidents/${id}/transition`, "POST", {
      expected_version: expectedVersion,
      target_status: targetStatus,
      reason: closing ? "Demo analyst lifecycle action" : undefined,
      close_reason: targetStatus === "closed" ? "resolved" : undefined,
    }),
  );
}
export async function getIntegrationHealth(): Promise<IntegrationHealth[]> {
  return z.array(integrationHealthSchema).parse(await authorized("/api/v1/integrations/health"));
}
export async function getPlaybooks(options?: ListQuery): Promise<PlaybookCatalog> {
  return playbookCatalogSchema.parse(await authorized(listPath("/api/v1/playbooks", options)));
}
export async function getPlaybookManagement(): Promise<PlaybookManagement> {
  return playbookManagementSchema.parse(await authorized("/api/v1/playbooks/management"));
}
export async function analyzeIncident(id: string): Promise<Analysis> {
  return analysisSchema.parse(
    await authorizedMutation(`/api/v1/incidents/${id}/analysis`, "POST", {}),
  );
}
export async function executeDemoAutomation(id: string) {
  return z
    .object({
      execution_id: z.string(),
      status: z.string(),
      mode: z.string(),
      workflow_id: z.string(),
    })
    .parse(
      await authorizedMutation("/api/v1/automations/execute", "POST", {
        incident_id: id,
        workflow_id: "cyrvanta-demo-response",
        approved: true,
        idempotency_key: `demo-${id}`,
      }),
    );
}

export async function downloadIncidentReport(id: string, code: string): Promise<void> {
  const response = await authenticatedFetch(`/api/v1/incidents/${id}/report`);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${code}.html`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export async function clearSession(): Promise<void> {
  accessToken = null;
  try {
    await fetch("/api/v1/auth/logout", {
      method: "POST",
      credentials: "include",
      headers: { "X-CSRF-Guard": "1" },
    });
  } finally {
    accessToken = null;
  }
}
