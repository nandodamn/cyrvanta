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
  triage_status: z.enum(["UNREVIEWED", "RELEVANT", "DISCARDED"]).default("UNREVIEWED"),
  reviewed_by_user_id: z.string().uuid().nullable().optional(),
  reviewed_at: z.string().nullable().optional(),
  reviewer_display_name: z.string().nullable().optional(),
});
const incidentSchema = z.object({
  id: z.string(),
  code: z.string().optional().default("INC-000"),
  title: z.string().optional().default("Untitled Incident"),
  description: z.string().nullable().optional().default(""),
  status: z.string().optional().default("new"),
  severity: z.string().optional().default("medium"),
  priority: z.number().nullable().optional().default(1),
  classification: z.string().nullable().optional().default("unclassified"),
  assignee_user_id: z.string().nullable().optional(),
  version: z.number().optional().default(1),
  is_simulated: z.boolean().nullable().optional().default(false),
  detected_at: z.string().nullable().optional().default(""),
  acknowledged_at: z.string().nullable().optional(),
  resolved_at: z.string().nullable().optional(),
  closed_at: z.string().nullable().optional(),
  close_reason: z.string().nullable().optional(),
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
const activityBucketSchema = z.object({
  bucket_start: z.string(),
  bucket_end: z.string(),
  alerts: z.number().int().nonnegative(),
  incidents: z.number().int().nonnegative(),
});
const operationalActivity24hSchema = z.object({
  window_start: z.string(),
  window_end: z.string(),
  updated_at: z.string(),
  source_mode: z.enum(["EMPTY", "SIMULATED", "LIVE", "MIXED"]),
  totals: z.object({
    alerts: z.number().int().nonnegative(),
    incidents: z.number().int().nonnegative(),
  }),
  series: z.array(activityBucketSchema).length(12),
});
const integrationHealthSchema = z.object({
  code: z.string(),
  mode: z.enum(["disabled", "simulated", "live"]),
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
const claimSchema = z.object({
  id: z.string().uuid(),
  incident_id: z.string().uuid(),
  claim_type: z.string(),
  statement: z.string(),
  language_code: z.string(),
  confidence: z.number().nullable(),
  origin_type: z.string(),
  origin_actor_user_id: z.string().uuid().nullable(),
  origin_code: z.string().nullable(),
  origin_version: z.string().nullable(),
  provider: z.string().nullable(),
  model: z.string().nullable(),
  explanation: z.string().nullable(),
  validation_criteria: z.string().nullable(),
  missing_evidence: z.array(z.string()),
  is_simulated: z.boolean(),
  state: z.string(),
  evidence: z.array(
    z.object({
      evidence_type: z.string(),
      evidence_id: z.string().uuid(),
      relationship: z.string(),
      evidence_sha256: z.string().nullable(),
    }),
  ),
  presentations: z.record(z.string()),
  created_at: z.string(),
});
const correlationSchema = z.object({
  id: z.string().uuid(),
  incident_id: z.string().uuid(),
  rule_code: z.string(),
  rule_version: z.string(),
  score: z.number().int().min(0).max(100),
  threshold: z.number().int().min(0).max(100),
  result_type: z.string(),
  explanation: z.string(),
  is_simulated: z.boolean(),
  window_start: z.string().nullable(),
  window_end: z.string().nullable(),
  claim_id: z.string().uuid().nullable(),
  created_at: z.string(),
  members: z.array(
    z.object({
      finding_id: z.string().uuid(),
      revision_id: z.string().uuid(),
      role: z.string(),
      selector_code: z.string(),
      effective_at: z.string(),
      source_system: z.string(),
      is_simulated: z.boolean(),
    }),
  ),
  factors: z.array(
    z.object({
      factor_code: z.string(),
      matched: z.boolean(),
      weight: z.number().int(),
      contribution: z.number().int(),
      explanation_code: z.string(),
    }),
  ),
});
const enrichmentSchema = z.object({
  mappings: z.array(
    z.object({
      id: z.string().uuid(),
      incident_id: z.string().uuid(),
      correlation_run_id: z.string().uuid(),
      external_id: z.string(),
      name_en: z.string(),
      tactic_codes: z.array(z.string()),
      status: z.string(),
      selector_codes: z.array(z.string()),
      evidence_revision_ids: z.array(z.string().uuid()),
      created_at: z.string(),
    }),
  ),
  risk: z.object({
    id: z.string().uuid(),
    incident_id: z.string().uuid(),
    definition_code: z.string(),
    definition_version: z.string(),
    score: z.number().int().min(0).max(100),
    band: z.string(),
    fingerprint: z.string(),
    factors: z.array(
      z.object({
        code: z.string(),
        weight: z.number().int(),
        contribution: z.number().int(),
      }),
    ),
    created_at: z.string(),
  }),
  explanations: z.array(
    z.object({
      id: z.string().uuid(),
      incident_id: z.string().uuid(),
      risk_assessment_id: z.string().uuid(),
      locale: z.string(),
      mode: z.string(),
      provider: z.string(),
      text: z.string(),
      grounded: z.boolean(),
      created_at: z.string(),
    }),
  ),
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
const playbookDefinitionSchema = z.object({
  id: z.string().uuid(),
  code: z.string(),
  title_i18n: z.object({ es: z.string(), en: z.string() }),
  description_i18n: z.object({ es: z.string(), en: z.string() }),
  created_at: z.string(),
  latest_version: z.string().nullable(),
  publication_status: z.string().nullable(),
  engine_type: z.enum(["NATIVE", "N8N"]).nullable(),
  binding_status: z.string().nullable(),
  binding_active: z.boolean(),
  execution_mode: z.enum(["SIMULATED", "LIVE"]).nullable(),
  impact: z.string().nullable(),
  required_parameters: z.array(z.string()),
  credential_aliases: z.array(z.string()),
  target_incident_types: z.array(z.string()).default([]),
  mitre_codes: z.array(z.string()).default([]),
  rollback_supported: z.boolean().default(false),
  rollback_target_code: z.string().nullable().default(null),
  rollback_guidance_i18n: z.object({ es: z.string(), en: z.string() }).nullable().default(null),
  automation_policy_i18n: z.object({ es: z.string(), en: z.string() }).nullable().default(null),
  approval_mode: z.enum(["AUTOMATIC", "SINGLE", "FOUR_EYES"]).default("AUTOMATIC"),
  last_execution_status: z.string().nullable(),
  last_executed_at: z.string().nullable(),
});
const playbookDefinitionListSchema = z.object({
  items: z.array(playbookDefinitionSchema),
  total: z.number().int().nonnegative(),
});
const playbookManagementSchema = z.object({
  editor_url: z.string().url(),
  local_only: z.boolean(),
  api_sync_configured: z.boolean(),
});
const responseDecisionSchema = z.object({
  id: z.string().uuid(),
  incident_id: z.string().uuid(),
  requester_user_id: z.string().uuid(),
  action_type: z.string(),
  impact: z.string(),
  requested_mode: z.string(),
  workflow_id: z.string(),
  workflow_version: z.string(),
  targets: z.array(z.string()),
  parameters: z.record(z.unknown()),
  evidence_refs: z.array(z.string().uuid()),
  incident_version: z.number().int(),
  is_simulated: z.boolean(),
  fingerprint: z.string(),
  status: z.string(),
  evaluation_outcome: z.string(),
  reason_codes: z.array(z.string()),
  approval_request_id: z.string().uuid().nullable(),
  required_approvals: z.number().int(),
  approval_status: z.string().nullable(),
  approval_expires_at: z.string().nullable(),
  decisions: z.array(
    z.object({
      id: z.string().uuid(),
      actor_user_id: z.string().uuid(),
      decision: z.string(),
      reason: z.string(),
      created_at: z.string(),
    }),
  ),
  authorization: z
    .object({
      id: z.string().uuid(),
      status: z.string(),
      expires_at: z.string(),
    })
    .nullable(),
  created_at: z.string(),
});
const responseDecisionListSchema = z.object({
  items: z.array(responseDecisionSchema),
  total: z.number().int().nonnegative(),
});
const playbookExecutionSchema = z.object({
  id: z.string().uuid(),
  authorization_id: z.string().uuid().nullable(),
  source_event_id: z.string().uuid().nullable(),
  proposal_id: z.string().uuid().nullable(),
  incident_id: z.string().uuid(),
  playbook_version_id: z.string().uuid(),
  origin: z.string(),
  execution_mode: z.string(),
  status: z.string(),
  inputs: z.record(z.unknown()),
  result: z.record(z.unknown()).nullable(),
  error_code: z.string().nullable(),
  adapter_execution_id: z.string().nullable(),
  claimed_at: z.string().nullable(),
  deadline_at: z.string(),
  completed_at: z.string().nullable(),
  created_at: z.string(),
});
const playbookExecutionListSchema = z.object({
  items: z.array(playbookExecutionSchema),
  total: z.number().int().nonnegative(),
});
export type IntegrationHealth = z.infer<typeof integrationHealthSchema>;
export type OperationalActivity24h = z.infer<typeof operationalActivity24hSchema>;
export type Analysis = z.infer<typeof analysisSchema>;
export type Claim = z.infer<typeof claimSchema>;
export type Correlation = z.infer<typeof correlationSchema>;
export type Enrichment = z.infer<typeof enrichmentSchema>;
export type PlaybookCatalog = z.infer<typeof playbookCatalogSchema>;
export type PlaybookDefinition = z.infer<typeof playbookDefinitionSchema>;
export type PlaybookManagement = z.infer<typeof playbookManagementSchema>;
export type ResponseDecision = z.infer<typeof responseDecisionSchema>;
export type PlaybookExecution = z.infer<typeof playbookExecutionSchema>;
export type ListQuery = {
  query?: string;
  page?: number;
  pageSize?: number;
  includeLookahead?: boolean;
};

const memoryReviewSchema = z.object({
  id: z.string().uuid(),
  reviewer_user_id: z.string().uuid(),
  decision: z.string(),
  reason: z.string(),
  created_at: z.string(),
});
const memoryStateSchema = z.object({
  id: z.string().uuid(),
  actor_user_id: z.string().uuid().nullable(),
  from_status: z.string().nullable(),
  to_status: z.string(),
  reason: z.string(),
  occurred_at: z.string(),
});
const memoryCandidateSchema = z.object({
  id: z.string().uuid(),
  version_id: z.string().uuid(),
  version: z.number().int().positive(),
  kind: z.string(),
  source_type: z.string(),
  created_by_user_id: z.string().uuid(),
  title_es: z.string(),
  title_en: z.string(),
  statement_es: z.string(),
  statement_en: z.string(),
  conditions: z.record(z.unknown()),
  evidence_refs: z.array(z.string().uuid()),
  is_synthetic: z.boolean(),
  valid_from: z.string(),
  valid_until: z.string(),
  status: z.string(),
  reviews: z.array(memoryReviewSchema),
  state_history: z.array(memoryStateSchema),
  created_at: z.string(),
});
const memoryCandidateListSchema = z.object({
  items: z.array(memoryCandidateSchema),
  total: z.number().int().nonnegative(),
});
const memoryMetricSchema = z.object({
  id: z.string().uuid(),
  code: z.string(),
  version: z.number().int(),
  window_start: z.string(),
  window_end: z.string(),
  sample_size: z.number().int().nonnegative(),
  numerator: z.number().int().nonnegative(),
  denominator: z.number().int().positive(),
  value: z.coerce.number(),
  sufficient_sample: z.boolean(),
  input_fingerprint: z.string(),
});
const memoryMetricListSchema = z.object({
  items: z.array(memoryMetricSchema),
  total: z.number().int().nonnegative(),
});
export type MemoryCandidate = z.infer<typeof memoryCandidateSchema>;
export type MemoryMetric = z.infer<typeof memoryMetricSchema>;

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

export async function authorizedMutation(
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

export async function updateAlertTriage(
  alertId: string,
  triageStatus: "UNREVIEWED" | "RELEVANT" | "DISCARDED",
): Promise<Alert> {
  return alertSchema.parse(
    await authorizedMutation(`/api/v1/alerts/${alertId}/triage`, "POST", {
      triage_status: triageStatus,
    }),
  );
}
export async function getIncidents(options?: ListQuery): Promise<Incident[]> {
  return z.array(incidentSchema).parse(await authorized(listPath("/api/v1/incidents", options)));
}
export async function getIncident(id: string): Promise<Incident> {
  return incidentSchema.parse(await authorized(`/api/v1/incidents/${id}`));
}
export async function getIncidentAlerts(id: string): Promise<Alert[]> {
  return z.array(alertSchema).parse(await authorized(`/api/v1/incidents/${id}/alerts`));
}
export async function getTimeline(id: string): Promise<TimelineEntry[]> {
  return z.array(timelineSchema).parse(await authorized(`/api/v1/incidents/${id}/timeline`));
}
export async function getClaims(id: string): Promise<Claim[]> {
  return z.array(claimSchema).parse(await authorized(`/api/v1/incidents/${id}/claims?limit=25`));
}
export async function getCorrelations(id: string): Promise<Correlation[]> {
  return z
    .array(correlationSchema)
    .parse(await authorized(`/api/v1/incidents/${id}/correlations?limit=25`));
}
export async function getIncidentEnrichment(id: string): Promise<Enrichment> {
  return enrichmentSchema.parse(await authorized(`/api/v1/incidents/${id}/enrichment`));
}
export async function recalculateIncidentRisk(id: string): Promise<Enrichment> {
  return enrichmentSchema.parse(
    await authorizedMutation(`/api/v1/incidents/${id}/risk-assessments`, "POST", {}),
  );
}
export async function generateIncidentExplanation(id: string): Promise<Enrichment> {
  return enrichmentSchema.parse(
    await authorizedMutation(`/api/v1/incidents/${id}/explanations`, "POST", {}),
  );
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
export async function generateCanonicalDemoScenario() {
  return z
    .object({
      scenario: z.string(),
      findings_created: z.number().int().nonnegative(),
      duplicates: z.number().int().nonnegative(),
      correlation_queued: z.boolean(),
      correlation_id: z.string().uuid(),
    })
    .parse(await authorizedMutation("/api/v1/demo/scenarios/credential-attack-v2", "POST", {}));
}
export async function transitionIncident(
  id: string,
  expectedVersion: number,
  targetStatus: string,
  reason?: string,
) {
  const closing = ["resolved", "closed", "reopened"].includes(targetStatus);
  return incidentSchema.parse(
    await authorizedMutation(`/api/v1/incidents/${id}/transition`, "POST", {
      expected_version: expectedVersion,
      target_status: targetStatus,
      reason: reason?.trim() || (closing ? "Acción de ciclo de vida del incidente" : "Transición de estado registrada"),
      close_reason: targetStatus === "closed" ? "resolved" : undefined,
    }),
  );
}
export async function getOperationalActivity24h(): Promise<OperationalActivity24h> {
  return operationalActivity24hSchema.parse(await authorized("/api/v1/operations/activity-24h"));
}

export async function getIntegrationHealth(): Promise<IntegrationHealth[]> {
  return z.array(integrationHealthSchema).parse(await authorized("/api/v1/integrations/health"));
}
export async function getPlaybookDefinitions(): Promise<{
  items: PlaybookDefinition[];
  total: number;
}> {
  return playbookDefinitionListSchema.parse(
    await authorized("/api/v1/playbook-definitions?limit=100&offset=0"),
  );
}

export async function togglePlaybookBinding(
  definitionId: string,
  input: { active?: boolean; engine_type?: "NATIVE" | "N8N" },
): Promise<PlaybookDefinition> {
  return playbookDefinitionSchema.parse(
    await authorizedMutation(
      `/api/v1/playbook-definitions/${definitionId}/toggle-binding`,
      "POST",
      input,
    ),
  );
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
export async function getResponseDecisions(incidentId: string): Promise<ResponseDecision[]> {
  const params = new URLSearchParams({ incident_id: incidentId, limit: "25", offset: "0" });
  return responseDecisionListSchema.parse(
    await authorized(`/api/v1/response-proposals?${params.toString()}`),
  ).items;
}

export async function createDemoResponseProposal(id: string): Promise<ResponseDecision> {
  return responseDecisionSchema.parse(
    await checked(
      await authenticatedFetch("/api/v1/response-proposals", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": `demo-proposal-${id}`,
        },
        body: JSON.stringify({
          incident_id: id,
          action_type: "simulate-user-block",
          impact: "MODERATE",
          requested_mode: "HUMAN_APPROVAL",
          workflow_id: "simulate-user-block",
          workflow_version: "1.0.0",
          targets: ["synthetic-demo-user"],
          parameters: { execution_mode: "demo" },
          evidence_refs: [],
        }),
      }),
    ),
  );
}

export async function getPlaybookExecutions(incidentId: string): Promise<PlaybookExecution[]> {
  const params = new URLSearchParams({ incident_id: incidentId, limit: "25", offset: "0" });
  return playbookExecutionListSchema.parse(
    await authorized(`/api/v1/playbook-executions?${params.toString()}`),
  ).items;
}

export async function executeAuthorizedResponse(
  authorizationId: string,
): Promise<PlaybookExecution> {
  return playbookExecutionSchema.parse(
    await checked(
      await authenticatedFetch(`/api/v1/response-authorizations/${authorizationId}/executions`, {
        method: "POST",
        headers: {
          "Idempotency-Key": `authorized-execution-${authorizationId}`,
        },
      }),
    ),
  );
}

export async function decideResponse(
  approvalRequestId: string,
  decision: "APPROVE" | "REJECT",
  fingerprint: string,
): Promise<ResponseDecision> {
  return responseDecisionSchema.parse(
    await authorizedMutation(`/api/v1/approval-requests/${approvalRequestId}/decisions`, "POST", {
      decision,
      reason:
        decision === "APPROVE"
          ? "Independent demo approval after reviewing the synthetic scope"
          : "Independent demo rejection",
      expected_proposal_fingerprint: fingerprint,
    }),
  );
}

export async function updatePlaybookApprovalGovernance(
  definitionId: string,
  approvalMode: "AUTOMATIC" | "SINGLE" | "FOUR_EYES",
): Promise<PlaybookDefinition> {
  return playbookDefinitionSchema.parse(
    await authorizedMutation(
      `/api/v1/playbook-definitions/${definitionId}/approval-governance`,
      "POST",
      { approval_mode: approvalMode },
    ),
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

async function governedMutation(path: string, body: unknown): Promise<unknown> {
  return checked(
    await authenticatedFetch(path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": globalThis.crypto.randomUUID(),
      },
      body: JSON.stringify(body),
    }),
  );
}

export async function getMemoryCandidates(): Promise<MemoryCandidate[]> {
  return memoryCandidateListSchema.parse(
    await authorized("/api/v1/memory-candidates?limit=100&offset=0"),
  ).items;
}

export async function getActiveMemory(): Promise<MemoryCandidate[]> {
  return memoryCandidateListSchema.parse(
    await authorized("/api/v1/memory/active?limit=100&offset=0"),
  ).items;
}

export async function getMemoryMetrics(): Promise<MemoryMetric[]> {
  return memoryMetricListSchema.parse(await authorized("/api/v1/memory/metrics?limit=100&offset=0"))
    .items;
}

export async function createFeedback(input: Record<string, unknown>): Promise<void> {
  await governedMutation("/api/v1/feedback", input);
}

export async function createMemoryCandidate(
  input: Record<string, unknown>,
): Promise<MemoryCandidate> {
  return memoryCandidateSchema.parse(await governedMutation("/api/v1/memory-candidates", input));
}

export async function transitionMemoryVersion(
  versionId: string,
  action: "review-request" | "activate" | "disable",
  reason: string,
): Promise<MemoryCandidate> {
  return memoryCandidateSchema.parse(
    await governedMutation(`/api/v1/memory-versions/${versionId}/${action}`, { reason }),
  );
}

export async function reviewMemoryVersion(
  versionId: string,
  decision: "APPROVE" | "REJECT" | "REQUEST_CHANGES",
  reason: string,
): Promise<MemoryCandidate> {
  return memoryCandidateSchema.parse(
    await governedMutation(`/api/v1/memory-versions/${versionId}/reviews`, {
      decision,
      reason,
    }),
  );
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

export interface TopologyNodeAlert {
  id: string;
  title: string;
  severity: "critical" | "high" | "medium" | "low" | "informational";
  category: string;
  observed_at: string;
}

export interface TopologyNode {
  id: string;
  name: string;
  type: "FIREWALL" | "SERVER" | "DATABASE" | "SIEM" | "GATEWAY" | "ENDPOINT";
  ip_address: string;
  subnet: string;
  status: "ONLINE" | "WARNING" | "OFFLINE";
  latency_ms: number;
  last_ping: string;
  active_alerts_count: number;
  active_alerts?: TopologyNodeAlert[];
  role_description_es: string;
  role_description_en: string;
}

export interface TopologyEdge {
  id: string;
  source_id: string;
  target_id: string;
  protocol: string;
  status: "NORMAL" | "DEGRADED" | "BLOCKED";
}

export interface NetworkTopologyResponse {
  tenant_id: string;
  nodes: TopologyNode[];
  edges: TopologyEdge[];
  updated_at: string;
}

export async function getNetworkTopology(): Promise<NetworkTopologyResponse> {
  return (await authorized("/api/v1/operations/topology")) as NetworkTopologyResponse;
}
