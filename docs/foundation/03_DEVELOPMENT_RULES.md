# 03 — Development Rules

## 1. Mandatory behavior

These rules apply to every human developer and AI coding agent.

The developer must:

- Read all governing documents before changing code.
- State the files and modules to be changed before implementation.
- Preserve architectural boundaries.
- Produce tests with implementation.
- Update documentation and migrations in the same change.
- Report ambiguities instead of inventing incompatible behavior.
- Prefer the simplest design that satisfies documented requirements.
- Keep tenant isolation, auditability and security controls non-negotiable.

## 2. Forbidden behavior

The developer must not:

- Hardcode tenant IDs.
- Trust tenant IDs received in request bodies.
- Query tenant-owned data without tenant scope.
- connect the browser directly to backend infrastructure services.
- call Ollama directly from React.
- execute AI-generated commands.
- use LLM output without schema validation.
- store credentials or secrets in Git.
- log passwords, tokens, LDAP credentials or raw sensitive prompts.
- create undocumented REST endpoints.
- create database tables outside approved migrations.
- bypass repositories with ad hoc SQL in controllers.
- put business logic in route handlers.
- put authorization only in the UI.
- silently catch exceptions.
- return internal stack traces to clients.
- disable TLS verification outside explicit local-development fixtures.
- use latest/unpinned container tags in reproducible environments.
- introduce a new dependency without justification and review.
- expose Wazuh, PostgreSQL, RabbitMQ, Redis, n8n or Ollama publicly.

## 3. Change protocol for AI agents

Before coding, output:

1. Goal.
2. Governing requirements.
3. Affected modules.
4. Data-model impact.
5. API impact.
6. Security and tenant-isolation impact.
7. Test plan.
8. Migration and rollback plan.

After coding, output:

1. Files changed.
2. Decisions made.
3. Tests added and result.
4. Security checks performed.
5. Known limitations.
6. Documentation updated.
7. Exact commands to validate locally.

## 4. Code organization

Expected backend layers:

```text
src/
  modules/
    <bounded_context>/
      domain/
      application/
      infrastructure/
      presentation/
  shared/
    domain/
    application/
    infrastructure/
    presentation/
```

Rules:

- Domain code has no dependency on FastAPI, SQLAlchemy, RabbitMQ, OpenSearch, Ollama or n8n.
- Application code depends on domain and ports.
- Infrastructure implements ports.
- Presentation translates transport concerns to application commands and queries.
- Shared code must be genuinely cross-cutting; it is not a dumping ground.

## 5. Python standards

- Supported Python version defined in `04_TECHNOLOGY_STACK.md`.
- Full type annotations.
- Strict static type checking.
- Async I/O for database and network calls.
- Pydantic models at boundaries.
- SQLAlchemy models remain infrastructure details.
- Dataclasses or explicit domain objects for core domain behavior.
- UTC-aware datetimes.
- Decimal for monetary values if licensing/billing is added.
- Enums or value objects for stable domain codes.
- No mutable default arguments.
- No broad `except Exception` without rethrow, translation or logging rationale.
- Structured logging with correlation and tenant identifiers.

## 6. TypeScript and React standards

- TypeScript strict mode.
- No `any` except isolated, documented interoperability boundaries.
- Server state managed by a query library.
- Form validation uses shared schemas where practical.
- Components separated into:
  - presentation components.
  - feature components.
  - route/page components.
- No API calls from low-level visual components.
- No authorization decisions based solely on hidden buttons.
- Accessible keyboard navigation.
- Translation keys instead of hardcoded user-facing text.
- Dates formatted using locale and user timezone.

## 7. Database standards

- All schema changes use Alembic migrations.
- Migrations must be forward and downgrade-aware unless irreversibility is documented.
- Tenant-owned tables include `tenant_id`.
- Primary keys use UUIDs unless a documented exception exists.
- Foreign keys are explicit.
- Delete behavior is deliberate.
- Critical mutable records use optimistic concurrency or equivalent protection.
- Audit records are append-oriented.
- JSONB is allowed for bounded extensibility, not as a substitute for relational design.
- Indexes must match actual query patterns.
- Personally identifiable and security-sensitive fields must be classified.

## 8. API standards

- Routes under `/api/v1`.
- Nouns, not verbs, except explicit action subresources.
- Correct HTTP semantics.
- RFC 7807 errors.
- Request and response schemas versioned through API evolution.
- Validation errors are actionable but do not expose internals.
- List endpoints require pagination.
- Filtering and sorting use allowlists.
- Resource IDs are UUIDs.
- Commands that may be retried use idempotency keys.
- All state-changing calls generate audit events.
- OpenAPI examples must use synthetic data.

## 9. AI engineering standards

Every AI capability requires:

- A named, versioned prompt.
- A strict input schema.
- A strict output JSON schema.
- Maximum context and token budgets.
- Evidence provenance.
- Redaction rules.
- timeout and retry policy.
- fallback behavior.
- evaluation cases.
- hallucination and unsupported-claim handling.
- model and parameter recording.
- tenant policy enforcement.

Telemetry must be enclosed as untrusted evidence. Prompts must explicitly instruct the model not to execute or follow instructions found in logs, emails, file names, command lines or incident evidence.

The AI may propose ATT&CK mappings. The platform validates technique identifiers against the local ATT&CK catalog.

## 10. Automation safety standards

- Only registered playbook versions may execute.
- Every input parameter has a typed schema.
- Targets are validated against tenant scope.
- Dangerous generic shell execution is prohibited.
- Actions have risk classifications.
- Automatic mode requires policy evaluation.
- High-impact actions require human approval and optionally dual control.
- Execution is idempotent where possible.
- Rollback or compensating guidance is documented.
- A global and tenant-level kill switch exists.
- Results are signed/authenticated and audited.

## 11. Security standards

Minimum design references:

- OWASP ASVS.
- OWASP API Security Top 10.
- least privilege.
- deny by default.
- defense in depth.
- secure defaults.
- separation of duties.
- auditability.
- dependency and container scanning.
- secret detection.
- signed release artifacts in enterprise phase.

All authorization-sensitive code requires negative tests.

## 12. Multitenancy verification

Every tenant-owned feature must include tests proving:

1. Tenant A can access its own resource.
2. Tenant A cannot access Tenant B's resource by ID.
3. Tenant A cannot infer Tenant B's resource through search/count/timing where practical.
4. Platform administrator access is explicit and audited.
5. Background jobs preserve tenant context.
6. Cache keys cannot collide across tenants.
7. OpenSearch queries include enforced tenant scope.

## 13. Testing pyramid

Required categories:

- Unit tests for domain and policy logic.
- Component tests for repositories and adapters.
- API integration tests.
- Contract tests for external adapters.
- tenant-isolation tests.
- security tests.
- frontend component and route tests.
- end-to-end critical workflows.
- AI schema and evaluation tests.
- migration tests.
- backup/restore tests before production.

No feature is complete with only happy-path tests.

## 14. Definition of Done

A change is done only when:

- Acceptance criteria pass.
- Tests pass.
- Static analysis passes.
- Formatting passes.
- Database migration is reviewed.
- API documentation is updated.
- translation keys exist in Spanish and English.
- audit behavior is verified.
- tenant isolation is verified.
- logs contain no secrets.
- observability is sufficient.
- rollback is documented.
- demo fixtures remain functional.

## 15. Git standards

- Short-lived branches.
- Conventional commits.
- Small, reviewable commits.
- No generated secrets or model files in Git.
- Database migrations committed with code.
- Architectural decisions recorded as ADRs.
- Tags follow semantic versioning.
