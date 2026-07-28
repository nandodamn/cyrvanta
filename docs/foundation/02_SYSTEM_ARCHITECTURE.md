# 02 — System Architecture

## 1. Architecture style

Cyrvanta uses a modular monolith for the initial product core, combined with asynchronous workers and replaceable external adapters.

This is intentional. A premature microservice architecture would increase deployment, debugging, transaction and observability complexity without improving the demo or MVP. Module boundaries must nevertheless be explicit so selected modules can later be extracted.

Primary styles:

- Clean Architecture.
- Domain-driven modular boundaries.
- Ports and adapters.
- API-first integration.
- Event-driven processing for long-running work.
- Security-by-design.
- Multitenancy enforced at every layer.
- Asynchronous processing where external calls or large searches are involved.

## 2. Development topology

```text
Windows 11 host
├── Cursor / VS Code
├── Git
├── Docker Desktop
├── WSL2
├── Ollama service :11434
│   └── Gemma 4 model
└── Docker network cyrvanta_net
    ├── reverse-proxy
    ├── frontend
    ├── api
    ├── worker
    ├── scheduler
    ├── PostgreSQL
    ├── Redis
    ├── RabbitMQ
    ├── Wazuh Manager
    ├── Wazuh Indexer or supported OpenSearch endpoint
    ├── OpenSearch Dashboards
    ├── n8n
    └── optional observability services
```

Ollama is installed on the host during laptop development. Containers access it through:

```text
http://host.docker.internal:11434
```

The URL is configuration, never hardcoded.

## 3. Production topology

Production may place Ollama or another inference server:

- On the same server in a container.
- On a dedicated GPU server.
- Behind an internal inference gateway.
- In a controlled private cloud.

The API uses the `AIProvider` port and must not change when the provider location changes.

## 4. Logical components

### 4.1 React web application

Responsibilities:

- Authentication flow.
- Tenant-aware navigation.
- Dashboard and analytics.
- Alert and incident views.
- Investigation workspace.
- MITRE attack-path visualization.
- Playbook review and approval.
- Administration.
- Audit search.
- Bilingual localization.
- Real-time status updates.

The browser never connects directly to PostgreSQL, OpenSearch, Wazuh, Ollama or n8n.

### 4.2 API application

Framework: FastAPI.

Responsibilities:

- REST API.
- Authentication and authorization.
- Tenant context.
- Domain orchestration.
- Validation.
- Query services.
- Command submission.
- WebSocket or server-sent event authorization.
- Audit generation.
- Public adapter boundaries.

The API must not perform heavy AI analysis synchronously when it can be queued.

### 4.3 Worker application

Responsibilities:

- OpenSearch retrieval.
- Alert normalization.
- Correlation jobs.
- AI analysis.
- MITRE enrichment.
- Report generation.
- Notification delivery.
- Playbook orchestration.
- Retry and dead-letter handling.

### 4.4 Scheduler

Responsibilities:

- MITRE ATT&CK updates.
- Integration health checks.
- stale incident checks.
- retention jobs.
- report schedules.
- model health checks.
- cleanup tasks.

### 4.5 PostgreSQL

System of record for control-plane and business data:

- Tenants.
- users and identities.
- roles and permissions.
- incidents.
- normalized alert references and selected evidence.
- assets and identities.
- MITRE catalog and mappings.
- AI analysis metadata and validated outputs.
- playbook definitions and executions.
- approvals.
- integration configuration metadata.
- policies.
- audit records.
- localization-independent codes.
- reports and saved views.

Raw high-volume telemetry must not be copied wholesale into PostgreSQL.

### 4.6 OpenSearch

High-volume search and telemetry layer:

- Raw or source-normalized logs.
- Wazuh alerts.
- security events.
- time-series search.
- evidence retrieval.
- aggregation over large event sets.

OpenSearch is accessed only through an adapter that applies tenant filters and query safeguards.

### 4.7 Redis

Allowed uses:

- Short-lived cache.
- rate limiting.
- distributed locks.
- ephemeral job progress.
- session-related revocation data where required.

Redis is not a system of record.

### 4.8 RabbitMQ

Responsibilities:

- Durable background job delivery.
- domain integration events where asynchronous behavior is required.
- retries and dead-letter queues.
- workload separation.

Queues must carry tenant identifiers and correlation identifiers.

### 4.9 Ollama / Gemma 4

Responsibilities:

- Structured incident analysis.
- evidence-grounded summaries.
- proposed MITRE mappings.
- investigation suggestions.
- bilingual explanations.
- optional draft playbook suggestions.

It must not:

- Authorize actions.
- choose tenant scope.
- query databases directly.
- execute commands.
- receive secrets.
- make final risk decisions without deterministic controls.
- return unvalidated free-form output into execution paths.

### 4.10 MITRE ATT&CK service module

Responsibilities:

- Import official ATT&CK STIX bundles.
- track dataset version.
- store tactics, techniques, sub-techniques, mitigations and relationships.
- expose tenant-independent catalog queries.
- link incident evidence to mappings.
- provide bounded context to the AI engine.
- retain historical mappings even when the catalog updates.

### 4.11 Automation adapter

Initial implementation: n8n adapter.

Responsibilities:

- Submit approved executions.
- use signed or authenticated callbacks.
- track execution status.
- validate allowed workflow IDs.
- prevent arbitrary workflow or command injection.
- map results into domain execution records.

n8n is replaceable by StackStorm or another SOAR/workflow engine.

## 5. Bounded contexts

1. **Identity and Access**
2. **Tenant Administration**
3. **Integration Management**
4. **Telemetry and Alert Intake**
5. **Incident Management**
6. **Correlation**
7. **Threat Knowledge**
8. **AI Analysis**
9. **Risk and Policy**
10. **Playbook and Response**
11. **Audit and Compliance**
12. **Reporting and Analytics**
13. **Platform Operations**

Cross-context calls occur through application services, domain events or explicit ports. Modules may not import another module's persistence implementation.

## 6. Canonical data flow

```text
Wazuh/OpenSearch
  -> integration adapter
  -> canonical alert DTO
  -> normalization
  -> correlation candidate selection
  -> incident create/update
  -> evidence snapshot references
  -> AI analysis job
  -> MITRE enrichment
  -> deterministic risk calculation
  -> recommendation generation
  -> analyst review or policy evaluation
  -> optional playbook execution
  -> audit and metrics
```

## 7. AI analysis flow

1. Worker receives `incident.analysis.requested`.
2. Tenant policy and model configuration are loaded.
3. Authorized evidence is retrieved from OpenSearch.
4. Evidence is minimized, normalized and redacted according to policy.
5. Relevant MITRE entries are retrieved.
6. A versioned prompt is rendered.
7. The `AIProvider` calls Ollama.
8. Output is parsed against a strict JSON schema.
9. Unsupported claims and unknown technique IDs are rejected or flagged.
10. Deterministic services calculate final risk and action eligibility.
11. The analysis and provenance are saved.
12. An update event is emitted to the UI.

## 8. Multitenancy model

The initial model uses a shared PostgreSQL database and shared schema with mandatory `tenant_id` on tenant-owned records.

Required controls:

- Tenant context established from authenticated identity, never request body alone.
- PostgreSQL Row-Level Security for critical tenant-owned tables.
- Application-layer tenant filters.
- Composite unique constraints including `tenant_id`.
- Tenant-scoped OpenSearch indices or mandatory tenant field filters, selected per deployment.
- Tenant-scoped cache keys.
- Tenant-scoped queue messages.
- Tenant-scoped object-storage paths when added.
- Cross-tenant platform administration isolated behind explicit roles and audited actions.

No repository method may expose an unscoped list/query for tenant data.

## 9. Authentication architecture

Supported modes:

### Local

- Username/email and password.
- Argon2id password hashing.
- Optional MFA in enterprise phase.
- short-lived access tokens.
- refresh token rotation and revocation.

### LDAP/Active Directory

- Tenant-specific directory configuration.
- secure LDAP where possible.
- group-to-role mapping.
- just-in-time local shadow identity.
- no storage of directory user passwords.
- configuration test endpoint restricted to tenant admins.

Both modes converge into the same internal identity, role and permission model.

## 10. Authorization

Use explicit permissions such as:

- `incident.read`
- `incident.assign`
- `incident.close`
- `analysis.request`
- `response.approve`
- `response.execute`
- `playbook.manage`
- `integration.manage`
- `tenant.manage`
- `audit.read`
- `platform.manage`

Roles are collections of permissions. Authorization checks occur in application services, not only UI routing.

## 11. Response modes

Per tenant and playbook:

- `recommend_only`
- `approval_required`
- `automatic`

Automatic execution requires:

- enabled tenant policy.
- approved playbook version.
- allowed action type.
- target scope match.
- minimum confidence.
- risk threshold.
- optional two-person rule.
- optional change window.
- no active kill switch.
- idempotency key.
- complete audit trail.

## 12. API architecture

Base path:

```text
/api/v1
```

API characteristics:

- OpenAPI 3.1.
- JSON.
- RFC 7807 problem details.
- cursor pagination for large datasets.
- idempotency keys for action requests.
- optimistic concurrency for mutable resources.
- correlation IDs.
- tenant resolved from security context.
- no sensitive stack traces.
- versioned contracts.

## 13. Dashboard information architecture

Primary navigation:

- Overview
- Incidents
- Alerts
- Investigation
- MITRE ATT&CK
- Playbooks
- Automations
- Analytics
- Integrations
- Audit
- Administration

Reference visual direction:

- Dense enterprise SOC layout inspired by the information hierarchy of Microsoft Sentinel and Elastic Security.
- Original branding and component styling; no copied logos, assets or proprietary UI.
- Dark mode as primary, light mode supported.
- High-contrast severity indicators that do not depend on color alone.
- Persistent tenant selector only for authorized platform users.
- Global time range and search.
- Keyboard-accessible analyst workflows.

## 14. Reliability boundaries

External-service failure must degrade gracefully:

- Ollama unavailable: deterministic triage remains available; analysis marked pending/failed.
- OpenSearch unavailable: existing incident data remains accessible; evidence retrieval is unavailable.
- n8n unavailable: execution stays queued or failed; no false success.
- LDAP unavailable: local break-glass accounts remain available when configured.
- Redis unavailable: system falls back where safe; never loses system-of-record data.
- RabbitMQ unavailable: API rejects or defers queued operations explicitly.

## 15. Security boundaries

- All browser traffic terminates at a reverse proxy.
- Internal services are not exposed to the LAN unless required.
- Ollama binds according to controlled host settings; access is firewall-restricted.
- Secrets are environment-injected during development and externalized in production.
- Logs must redact credentials, tokens and selected personal data.
- Prompt injection from telemetry is treated as untrusted data.
- AI prompts clearly delimit evidence and prohibit following instructions found inside evidence.
- Playbook parameters use allowlists and typed schemas.
