# Production Readiness Increment 19 - Decision service tenant defense in depth

Date: 2026-08-11

## Objective

Require an explicit tenant predicate in every tenant-owned query used by proposal, policy,
approval, authorization and decision read-model flows, in addition to PostgreSQL forced RLS.

## Implementation

- Scoped incident, requester, policy and idempotent-proposal lookup during proposal creation.
- Scoped proposal lists, counts and detail lookup.
- Scoped approval request, proposal, actor, existing-decision and quorum-count queries.
- Scoped authorization revocation and its related proposal lookup.
- Scoped policy evaluation, approval request, decision and authorization projections used to
  produce a response.
- Added an AST regression that covers at least 18 tenant-owned `select()` statements and fails if
  the selected model lacks an explicit tenant predicate.

No schema, migration, endpoint, DTO, event, state transition or permission changed. RLS remains
enabled and forced as the physical isolation boundary. LIVE remains disabled.

## Verification

```text
Focused Ruff: passed.
Focused DecisionService mypy: passed.
Focused decision tests: 7 passed.
Global backend Ruff: passed with zero findings.
Global backend mypy: passed; no issues in 130 source files.
Backend suite excluding the separately verified PostgreSQL alert-triage test:
207 passed, 3 dependency deprecation warnings.
git diff --check: passed.
```

The new test initially required Ruff import ordering; the mechanical fix was applied before the
successful focused and global gates.

## Security and rollback

The decision subsystem no longer depends solely on ambient RLS session state for tenant
isolation. IDs from another tenant remain undisclosed and cannot affect list totals, quorum or
authorization projections even if a privileged test session bypasses RLS. Rollback is a code-only
commit reversion with no data rollback.
