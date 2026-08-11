# Production Readiness Increment 20 - Authorization pre-consumption revalidation

Date: 2026-08-11

## Objective

Revalidate the persisted authorization, policy, incident, approval quorum, engine binding and
feature flags inside the transaction that consumes an authorization and creates a playbook
execution.

## Implementation

Before setting an authorization to `CONSUMED`, the service now requires:

- authorization `ACTIVE`, unconsumed, unrevoked and unexpired;
- proposal `AUTHORIZED` with the same persisted fingerprint;
- the exact proposal policy version present, `ACTIVE` and not killed;
- the global automation kill switch open;
- the incident present with unchanged version and synthetic classification;
- the linked approval request still `APPROVED` and unexpired;
- persisted approval count equal to or above the deterministically recalculated quorum;
- exactly one active synchronized engine binding;
- desired and observed binding digests both equal to the released artifact digest;
- Native enabled globally and for the tenant, or n8n enabled when the immutable binding selects
  n8n.

All new reads are explicitly tenant-scoped. Idempotent replay of an already-created execution is
still returned before new consumption checks and cannot create a second effect. No schema,
migration, endpoint, DTO or event contract changed. LIVE remains disabled.

## Verification

```text
Focused Ruff: passed.
Focused service mypy: passed.
Focused pre-consumption/execution tests: 13 passed.
Global backend Ruff: passed with zero findings.
Global backend mypy: passed; no issues in 130 source files.
Backend suite excluding the separately verified PostgreSQL alert-triage test:
215 passed, 3 dependency deprecation warnings.
git diff --check: passed.
```

## Known contractual gap

The historical proposal fingerprint includes the command `Idempotency-Key`, but that key is not
persisted separately on `action_proposals`. Therefore the service can verify exact equality between
authorization and proposal fingerprints and can independently revalidate all other persisted
material, but it cannot reconstruct the complete original fingerprint from database fields alone.
A physical fix requires an approved migration/contract; no column was invented in this increment.

Current approver permission membership is also not yet recomputed at consumption time. Actor
identity and separation were enforced when decisions were written, while current quorum is
recounted here. Permission revalidation needs an explicit query/authorization contract and remains
tracked.

## Security and rollback

Changes to policy, incident version, quorum, binding, digest or engine availability now fail before
the authorization is consumed. Rollback is a code-only commit reversion with no data rollback.
