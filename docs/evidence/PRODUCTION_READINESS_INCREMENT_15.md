# Production Readiness Increment 15 - Dispatcher tenant defense in depth

Date: 2026-08-11

## Objective

Require explicit tenant predicates in every tenant-owned query used by the native, hybrid and
n8n playbook dispatch paths, in addition to PostgreSQL forced RLS.

## Implementation

- Added explicit tenant filters to queued execution discovery and timeout reconciliation.
- Scoped execution, binding, released-version, attempt, outcome and native-step queries by the
  authenticated or scheduler-selected tenant.
- Changed the hybrid execution-to-binding join to include `tenant_id` as part of the join
  identity and constrained both sides to the selected tenant.
- Propagated `tenant_id` through native runner locking helpers so a helper cannot perform an ID-
  only lookup.
- Added an AST-based regression that fails when a tenant-owned `select()` in any of the three
  dispatchers lacks a tenant predicate. It covers 10 n8n, 2 hybrid and 14 native queries.

No schema, migration, DTO, endpoint, event name or state transition changed. The native engine
remains `SIMULATED` only and LIVE remains disabled.

## Verification

```text
Focused Ruff: passed.
Focused dispatcher/native tests: 19 passed.
Backend suite excluding the separately verified PostgreSQL alert-triage test:
195 passed, 3 dependency deprecation warnings.
git diff --check: passed.
```

The first focused command referenced a worktree-local `.venv` that does not exist; it executed no
product code. The installed environment from the main repository was then used successfully.
Initial coverage minima in the new AST test were one above the actual query counts; the minima
were corrected to the exact observed counts and all assertions passed.

The first full Pytest run completed 194 tests but one fixture failed during setup because Pytest's
default Windows temp root had a denied ACL. Re-running the complete host suite with a verified,
explicit `C:\tmp` base produced 195 passing tests.

Global quality gates also exposed pre-existing debt outside this increment: Ruff currently reports
64 findings and mypy reports 9 errors, principally in integration connectors and playbook
administration. These failures are recorded and are the next hardening target; they are not
reported as passing.

## Security and rollback

Forced RLS remains the physical isolation control. Explicit predicates and the composite hybrid
join add application-level defense in depth, reduce reliance on ambient session state and make
cross-tenant regressions statically visible. Rollback is a code-only commit reversion with no data
rollback.
