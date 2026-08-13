# Production Readiness Increment 32 — Fair and gated playbook dispatch

Date: 2026-08-13

## Objective

Prevent queued real playbook executions from starving behind earlier tenants or disabled
engines, while preserving tenant suspension and LIVE gates.

## Finding and implementation

The scheduler previously inspected only the first 25 tenants and allowed the first tenant
with a continuous backlog to consume the complete batch. Later tenants could therefore
remain queued indefinitely. The hybrid n8n path also checked `N8N_ENABLED` but did not
independently enforce the global dispatch switch when invoked from a durable event.

Pending discovery now:

- considers every active tenant;
- excludes engines disabled by their global, tenant allowlist, LIVE, dispatch, or kill
  switches;
- requires an active synchronized binding and a LIVE execution;
- interleaves candidates round-robin across tenants;
- bounds attempted dispatches to 1–500 per pass;
- revalidates tenant, execution, binding, and engine state before dispatch.

The n8n branch now fails closed unless all global n8n/LIVE/dispatch/kill-switch guards pass.

## Verification status

Unit tests were added for engine gates, tenant allowlists, round-robin ordering, active-tenant
discovery, and the n8n dispatch switch. Per operator instruction, Codex did not execute tests,
services, migrations, Docker, playbooks, or external connections. Static diff validation was
performed only.

## Contract and rollback

No endpoint, DTO, event, permission, secret, or database contract changed. Rollback is the
single implementation commit; it would restore possible tenant starvation and the incomplete
n8n dispatch gate and is not recommended.
