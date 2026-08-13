# Production Readiness Increment 36 — Immutable schema-upgrade path

Date: 2026-08-13

## Objective

Keep existing installations operable after strict playbook schemas become mandatory without
mutating an already published immutable version or silently bypassing human publication.

## Finding and implementation

The strict runtime gate correctly blocks older open schemas, but the essential catalog seed
previously stopped as soon as any LIVE-classified version existed. An installation containing
an older published version therefore had no automatic way for the existing configuration menu
to expose a successor carrying the current schemas.

Catalog reconciliation now:

- loads all versions tenant-scoped for collision-free numbering and orders them deterministically;
- considers a definition current only when a non-retired DRAFT or APPROVED version contains
  both exact current schemas;
- creates one DRAFT successor with the next semantic patch version when no current version
  exists;
- never edits or republishes an older immutable version;
- records the system-generated version in tenant audit with `initial_seed` or `schema_upgrade`
  as the reason and no invented human actor;
- stops creating successors once the current DRAFT exists, leaving validation and publication
  to the authorized operator.

The library already selects the latest version, so its existing configuration flow can validate
and publish that successor before recreating or activating bindings.

## Verification status

Unit tests were added for initial and patch version calculation, prerelease handling, exact
schema-current detection, eligible statuses, and audit creation. Per operator instruction,
Codex did not execute tests, builds, services, Docker, probes, migrations, playbooks, or
external connections. Targeted Ruff static analysis, source formatting, and diff validation
passed.

## Contract and rollback

No endpoint, DTO, event, permission, table, column, secret, or LIVE switch changed. This uses
the approved immutable version and DRAFT-to-publication lifecycle. Rollback is the single
implementation commit, but would leave upgraded installations without an operational successor
path and is not recommended.
