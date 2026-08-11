# Production Readiness Increment 13 — Draft playbooks fail closed in the UI

Date: 2026-08-11

## Objective

Prevent an unpublished playbook version from being presented or operated as an executable
capability while preserving the approved immutable-version workflow.

## Implementation

- A playbook can be activated or switched between Native and n8n only when its latest version
  is `PUBLISHED`; both controls are disabled for `DRAFT`.
- A missing engine binding is shown as “Engine not bound” / “Motor no vinculado”, not as
  Cyrvanta Native by default.
- The details modal does not render a DRAFT definition's purpose text as executable behavior.
  It shows an explicit bilingual notice that the draft is not a published capability.
- Approval-governance controls remain available because tightening definition governance is not
  execution and is valid before publication.

This change does not mutate existing definitions or immutable artifacts. It avoids silently
rewriting tenant customizations and respects the implementation contract: corrections require a
new version, validation, and publication.

## Verification

```text
ESLint: passed with zero warnings.
TypeScript project typecheck: passed.
Vitest full suite: 9 files, 17 tests passed.
Vite production build: passed.
Main JS bundle: 513.99 kB minified / 147.96 kB gzip.
Post-format focused DRAFT regression: 1 passed.
```

The first combined command used an incorrect relative path for Prettier from the frontend
directory. PowerShell continued and lint, typecheck, tests, and build all passed. Prettier was
then rerun with the correct path, followed by successful lint, typecheck, and focused DRAFT
regression. The known Vite chunk-size warning remains tracked.

## Security and rollback

The UI now matches backend publication preconditions and cannot invite an operator to activate
an immutable-version workflow that has not passed validation and publication. LIVE remains
disabled. Rollback is a code-only commit reversion; no data migration or data rollback exists.
