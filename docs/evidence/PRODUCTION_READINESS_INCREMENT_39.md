# Production Readiness Increment 39 — Authorized minimized egress

Date: 2026-08-13

## Objective

Make the three explicitly authorized external playbooks transmit the same real, tenant-scoped,
minimized incident material and nothing beyond the approved field set.

## Finding and implementation

`notify-critical-incident` and `create-security-ticket` previously transmitted current incident
identity and state but omitted risk and analysis. `incident-report-email` included those values,
but its report snapshot also carried operational metadata outside the explicitly authorized
egress set.

All SMTP and allowlisted HTTPS actions now resolve one dedicated egress snapshot. It checks the
tenant-scoped incident's optimistic version, computes the real grounded analysis, and exposes
only:

- incident ID, code, title, status, severity, and classification;
- risk score;
- grounded analysis mode and Spanish/English summaries.

Priority, version, timestamps, raw evidence, telemetry, MITRE detail, recommendations, secrets,
credentials, and free proposal parameters are excluded. The richer on-platform report endpoint
keeps its existing internal snapshot and is not used for external delivery.

## Safety and activation

This change does not activate a connection, binding, approval, LIVE switch, or automatic
execution. Destination and credential resolution remain tenant-scoped, verified, write-only, and
fail closed. Existing SMTP TLS and HTTPS allowlist checks remain unchanged.

## Verification status

Unit coverage was added to assert the exact external key set and exclusion of richer internal
fields. Per operator instruction, Codex did not execute tests, builds, services, Docker, probes,
migrations, playbooks, or external connections. Targeted Ruff formatting/static analysis and diff
whitespace validation passed.

## Rollback

Rollback is the implementation commit for this increment. It would restore inconsistent and
over-broad external payloads and is not recommended.
