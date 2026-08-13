# Production Readiness Increment 28 — Native dispatch concurrency exclusion

Date: 2026-08-13

## Objective

Prevent simultaneous redelivery of one native playbook execution from invoking its action
connector more than once while preserving crash recovery and immutable execution history.

## Finding and implementation

The native runner used row locks while creating executions and step attempts, but released
those locks before calling the connector. A concurrent redelivery could therefore reuse the
same attempt before its first invocation completed. Reusing the idempotency key was necessary
but did not by itself prove absence of a simultaneous double effect.

Native dispatch now acquires a non-blocking PostgreSQL transaction advisory lease derived
from both tenant ID and execution ID. Exactly one worker can own an execution across claim,
connector invocation, and durable completion. A concurrent delivery returns a no-op and does
not call the runner, mutate state, or convert the active execution into a failure. PostgreSQL
releases the lease automatically on commit, rollback, connection loss, or process crash.

The existing immutable binding still selects exactly one of `NATIVE | N8N`. n8n retains its
existing `QUEUED` row-lock transition before network dispatch.

## Verification

```text
Focused native/hybrid tests: 17 passed
Deterministic two-delivery concurrency test: one runner call, second delivery no-op
Backend tests not requiring PostgreSQL: 221 passed
Global Ruff: passed
Global mypy: no issues in 130 source files
```

The complete suite additionally collected and passed 221 tests before the one existing
PostgreSQL-backed alert-triage test failed to connect because Docker Desktop was offline.
Runtime PostgreSQL proof with two independent connections, deployment health, and the
frontend increment 27 runtime check remain pending until the Docker daemon is available.
They are not represented as passed by this increment.

## Contract, security, and operational impact

No domain entity, migration, API, DTO, event payload, permission, tenant resolution, secret,
or LIVE contract changed. The lease key includes tenant and execution identity and contains
no secret. The advisory lock lives only in the infrastructure adapter; domain and application
layers remain database-independent.

Each active native execution now retains one PostgreSQL pool connection for its bounded run.
This is an intentional correctness tradeoff and must be included in later pool/load sizing.

## Rollback

Rollback is code-only through this increment commit. Reverting would restore the identified
simultaneous-redelivery race and is not recommended.
