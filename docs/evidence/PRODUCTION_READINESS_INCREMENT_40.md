# Production Readiness Increment 40 — Unknown external outcomes

Date: 2026-08-13

## Objective

Prevent SMTP or HTTPS effects with an unconfirmed outcome from being reported as a definitive
failure or retried as if no external change occurred.

## Finding and implementation

The real connectors previously converted transport exceptions into
`PLAYBOOK_ACTION_FAILED`. A timeout or connection loss can occur after a remote SMTP server or
HTTP endpoint accepted the operation, so `FAILED` could provide false certainty.

SMTP, operating-system transport, and HTTP transport exceptions now return
`PLAYBOOK_ACTION_OUTCOME_UNKNOWN`. The NATIVE runner persists the attempt outcome and step as
`UNKNOWN`, propagates the same error to the execution, and does not continue the graph. Recovery
from a crash also recognizes a persisted UNKNOWN step and preserves the execution as UNKNOWN
instead of degrading it to FAILED. Definitive local validation, incident-version, and missing
resource errors remain FAILED.

This is deliberately fail-safe: an operator must reconcile the destination before deciding any
follow-up. No automatic retry is introduced for non-idempotent external effects.

## Verification status

Unit coverage was added for result and execution-state classification, and the existing recovery
contract now expects the explicit unknown-outcome error. Per operator instruction, Codex did not
execute tests, builds, services, Docker, probes, migrations, playbooks, or external connections.
Targeted Ruff formatting/static analysis and diff whitespace validation passed.

## Contract and rollback

No endpoint, DTO, database, event name, permission, connection, or secret contract changed. The
existing `UNKNOWN` state and error code are now used for their intended safety semantics. Rollback
is the implementation commit for this increment and would restore false-negative reporting.
