# Production Readiness Increment 35 — Typed playbook input and result schemas

Date: 2026-08-13

## Objective

Prevent malformed or loosely shaped data from crossing the authorization boundary into a
real playbook execution or being accepted as a successful LIVE result.

## Finding and implementation

The internal schema registry was allowlisted, but its runtime validator checked only required
and unexpected top-level property names. It did not enforce declared types, UUID format,
constants, bounds, array items, uniqueness, or nested object policy. The real execution path
also built inputs without validating them against the immutable released schema.

The implementation now:

- validates the supported schema subset recursively with a bounded depth;
- requires every object schema to close additional properties or type them explicitly;
- requires typed array items and enforces bounds and uniqueness;
- enforces UUID, integer-versus-boolean, constants, patterns, lengths, and numeric bounds;
- rejects free runtime `parameters` for the currently implemented native playbooks;
- validates portable input before consuming an authorization or creating an execution;
- keeps the authenticated actor as internal execution context rather than user-controlled
  portable input;
- rejects stored legacy schemas that are not recursively strict;
- accepts a LIVE result only when its typed receipt map contains exactly the released step IDs;
- removes the obsolete synthetic wording from the LIVE n8n claim audit detail.

## Verification status

Unit tests were added for malformed UUIDs, boolean-as-integer confusion, empty or duplicate
targets, free parameters, invalid evidence references, open nested schemas, result constants,
typed receipt values, exact released-step coverage, and validation-before-consumption order.
Per operator instruction, Codex did not execute tests, builds, services, Docker, probes,
migrations, playbooks, callbacks, or external connections. Static diff validation and local
source formatting and targeted Ruff static analysis were performed only; Ruff passed.

## Operational consequence and rollback

No endpoint, DTO, event, permission, table, column, secret, or LIVE switch changed. A version
persisted with an older structurally open schema now fails closed; because versions are
immutable, it must be superseded by a newly validated and published version. New versions
copy the strict current schema. Rollback is the single implementation commit, but would
restore acceptance of untyped execution data and is not recommended.
