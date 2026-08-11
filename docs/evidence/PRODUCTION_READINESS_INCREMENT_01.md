# Production readiness increment 01 — fail-closed integrations

**Date:** 2026-08-11
**Status:** Implemented and statically verified
**Scope:** Integrations, native playbook bootstrap and frontend contract health

## Objective

Remove false-positive integration states and prevent unvalidated native
playbooks from becoming active. This increment does not implement the approved
write-only deployment secret store; unsupported configuration and probe
operations explicitly fail closed until that contract is available.

## Implemented controls

- Connection resolution no longer creates `conn-lab-*` fallbacks.
- Unknown capabilities and missing tenant connections return `not_resolved`
  with `blocking=true`.
- Only tenant integrations with `status=active` are selectable.
- Integration health requires `integration.read`; mutation/probe routes require
  `integration.manage`.
- Configuration and probe routes return explicit HTTP 501 errors instead of
  synthetic success.
- The visible integrations page is populated exclusively from
  `/api/v1/integrations/health` and includes loading, error and empty states.
- The former static catalog and credential modal were removed.
- Essential native playbooks are bootstrapped as `DRAFT`, without active
  bindings, with strict registered schemas and allowlisted simulated actions.
- Rollback support defaults to false unless the backend explicitly declares it.
- The backend/frontend definition contract now includes
  `automation_policy_i18n` consistently.

## Tenant and security properties

- Tenant identity continues to come only from the authenticated security
  context and `tenant_session`.
- Missing configuration is blocking; it is never replaced by a generic or lab
  connection.
- Secrets submitted to the unavailable legacy configuration route are not
  persisted, echoed or logged.
- No database schema or migration changed in this increment.
- `LIVE` remains outside the approved operational scope.

## Verification evidence

- Backend focused suite: `13 passed`.
- Backend suite independent of PostgreSQL: `164 passed, 2 deselected`.
- Frontend ESLint: passed with zero warnings.
- Frontend TypeScript project build: passed.
- Frontend Vitest: `15 passed` across seven files.
- Frontend production Vite build: passed.

The two deselected backend tests require PostgreSQL access from the test
process. Compose PostgreSQL is healthy but intentionally not exposed to the
host. They must be run inside the Compose network as part of the integration
gate.

## Known remaining work

- Implement the exact write-only `DeploymentSecretStorePort` API and encrypted
  local adapter from ADR 0018.
- Replace the synthetic network topology with persisted or explicitly empty
  data.
- Reconcile previously persisted invalid synthetic playbook versions and
  bindings through a reviewed data migration or administrative operation.
- Eliminate remaining repository-wide Ruff debt before release.
- Execute PostgreSQL/RLS, RabbitMQ/worker and browser E2E gates.

## Rollback

This increment has no migration. Rollback consists of reverting the application
commit. Existing integration, playbook and audit records are not deleted or
rewritten.
