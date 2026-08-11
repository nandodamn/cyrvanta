# Production Readiness Increment 10 — Explicit tenant scoping for playbook executions

Date: 2026-08-11

## Objective

Add explicit tenant predicates to the Playbook Execution application service so database RLS
remains a second isolation barrier rather than the only barrier.

## Scope

The following tenant-owned lookups now include `tenant_id` in their SQL predicates:

- execution idempotency and execution list/get/lock;
- action authorization and its proposal;
- playbook definition and immutable version;
- automation engine binding;
- active native step executions;
- dispatch attempts and callback updates;
- replay nonces and successful-result version validation.

Tenant context is also passed explicitly through the internal execution, binding, and nonce
helper methods. The tenant still originates from the authenticated security context for public
routes. Signed internal adapter callbacks first resolve the execution tenant through the
approved database function and then verify the purpose-separated tenant signature before
entering a tenant session.

## Contract impact

- Domain: none.
- Database schema or migration: none.
- API and DTOs: none.
- Events and queues: none.
- Permissions: none.
- LIVE automation: unchanged and not enabled.

## Verification

Focused verification:

```text
ruff check service.py test_playbook_execution_tenant_filters.py
All checks passed.

pytest test_playbook_execution.py test_playbook_execution_tenant_filters.py
       test_native_engine_tenant_filters.py -q
6 passed.
```

The first full host regression reached 187 passing tests, but one test failed during fixture
setup because the Windows global pytest temporary directory denied access. It was repeated
with an isolated explicit base directory under `C:\tmp`:

```text
pytest backend/tests -q --ignore=backend/tests/unit/test_alert_triage.py
       --basetemp=C:\tmp\cyrvanta-pytest-inc10-20260811
188 passed, 3 dependency deprecation warnings.
```

The PostgreSQL-backed alert-triage test remains covered by Increment 09 (`1 passed`) and was
not rerun because this increment does not change incident triage or database structure.

## Security and rollback

The change fails closed for cross-tenant identifiers even if session-level RLS is accidentally
misconfigured or bypassed by a privileged connection. Existing RLS policies remain active as
defense in depth. Rollback is the reversion of this code-only increment; no data rollback is
required.
