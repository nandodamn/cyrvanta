# Production Readiness Increment 21 — Secure integration defaults

Date: 2026-08-11

## Objective

Make an unconfigured Cyrvanta installation fail closed for external integrations and remove
an unused frontend proposal helper that embedded a private target and LIVE execution mode.

## Scope and decisions

- OpenSearch, Wazuh, and Ollama now default to `simulated`.
- n8n now defaults to `disabled` with `N8N_ENABLED=false` semantics.
- The default n8n allowlist contains only the five workflows approved in the Phase 21A
  implementation contract and `.env.example`.
- The native playbook engine remains enabled by default, while dispatch and LIVE execution
  remain disabled.
- The unused `createResponseProposal` frontend helper was removed. It included a hard-coded
  private IP, a legacy workflow choice, and `execution_mode: "live"`.
- The explicit synthetic demo helper remains available and continues to use demo mode.

No `.env` file was read, changed, or copied. Explicit deployment configuration still takes
precedence over code defaults. No secret values were added to source control or test output.

## Contract impact

- Domain: none.
- Database schema or migration: none.
- API, DTOs, events, and queues: none.
- Permissions and tenant isolation: none.
- LIVE automation: unchanged and disabled by default.

## Verification

Focused backend verification:

```text
ruff check config.py test_secure_configuration_defaults.py
All checks passed.

mypy config.py
Success: no issues found in 1 source file.

pytest test_secure_configuration_defaults.py -q
2 passed.
```

Focused frontend verification:

```text
vitest run tests/no_implicit_live_proposal.test.ts
1 file passed, 1 test passed.
```

Global backend verification:

```text
ruff check backend/src backend/tests
All checks passed.

mypy backend/src
Success: no issues found in 130 source files.

pytest backend/tests --ignore=test_alert_triage.py
217 passed, 3 dependency deprecation warnings.

pytest tests/unit/test_alert_triage.py inside disposable Compose container
1 passed, 2 read-only pytest-cache warnings.
```

The split execution is required because PostgreSQL is intentionally not exposed to the host.
The PostgreSQL-backed test used the existing internal Compose network, a read-only source
mount, and dependencies installed only under the disposable container's `/tmp` directory.

Global frontend verification:

```text
eslint: passed with zero warnings
TypeScript: passed
Vitest: 11 files passed, 19 tests passed
Vite production build: passed
```

Vite reports that the main JavaScript chunk is 512.58 kB (147.60 kB gzip), above its 500 kB
warning threshold. Route-level code splitting remains an explicit performance-hardening task.

## Security and rollback

The change reduces accidental external connectivity and prevents an unused UI helper from
constructing a LIVE-looking response request. Tenant scoping, approval governance, and audit
behavior are unchanged. Rollback is code-only; no data or migration rollback is required.
