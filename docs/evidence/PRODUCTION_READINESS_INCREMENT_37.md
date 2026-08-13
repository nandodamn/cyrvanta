# Production Readiness Increment 37 — Truthful approval dependency

Date: 2026-08-13

## Objective

Ensure the playbook dependency API reports the tenant-approved governance requirement rather
than inferring approval from an action connector's technical impact label.

## Finding and implementation

`connection-dependencies` exposed `requires_approval`, but calculated it as true only for
actions whose descriptor impact was HIGH or CRITICAL. The implemented real actions are
technically MEDIUM while their playbook definitions require SINGLE approval. The endpoint
could therefore report that approval was not required even though the governed execution path
correctly required it.

The service now loads the exact tenant-scoped definition for the requested version and derives
the flag from its persisted `AUTOMATIC | SINGLE | FOUR_EYES` mode. SINGLE and FOUR_EYES both
report approval required; AUTOMATIC does not. A missing or unknown mode fails closed as an
invalid playbook instead of guessing.

## Verification status

Parameterized unit tests were added for all three approved modes and a resolved internal real
action binding. Per operator instruction, Codex did not execute tests, builds, services,
Docker, probes, migrations, playbooks, or external connections. Targeted Ruff static analysis,
source formatting, and diff validation passed.

## Contract and rollback

No endpoint, DTO, database, event, permission, secret, or LIVE contract changed. The existing
response field now reflects its approved source of truth. Rollback is the single implementation
commit, but would restore a misleading approval projection and is not recommended.
