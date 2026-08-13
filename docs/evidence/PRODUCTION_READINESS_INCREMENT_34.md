# Production Readiness Increment 34 — Current validation required at runtime

Date: 2026-08-13

## Objective

Prevent a connection verified under older, more permissive validation from appearing ready
or reaching a real connector after destination rules become stricter.

## Finding and implementation

Connection configuration was validated when written, but previously stored active records
could retain their successful health state. Readiness queries trusted that state, and runtime
resolution decrypted the record without repeating current deterministic validation.

The current configuration validation is now versioned as `1.1` and enforced consistently:

- new or replaced configurations receive the current validation version;
- enabling or disabling while preserving the encrypted value cannot upgrade an old version;
- probe revalidates before any network operation, records invalid legacy configuration as
  unhealthy, and upgrades the version only after both validation and the real probe succeed;
- playbook credential resolution and single-connector resolution revalidate after decryption;
- capability resolution, dependency checks, binding creation and verification, publication
  readiness, and the native dispatcher require the current validation version.

Therefore an old connection cannot be presented as ready or used merely because it retains
an earlier `active` status. A valid legacy connection can be promoted through the existing
manual real-probe workflow; an invalid one must be replaced.

## Verification status

Unit tests were added for invalid legacy playbook resolution, invalid single-connector
resolution, network-free rejection during probe, successful version promotion, and coverage
of every readiness path. Per operator instruction, Codex did not execute tests, builds,
probes, services, Docker, migrations, playbooks, or external connections. Static diff
validation and local source formatting were performed only.

## Contract and rollback

No endpoint, DTO, event, permission, table, column, secret-storage, or LIVE contract changed.
The existing configuration schema-version field now carries the stricter validation version.
Rollback is the single implementation commit, but would restore stale-verification bypass and
is not recommended.
