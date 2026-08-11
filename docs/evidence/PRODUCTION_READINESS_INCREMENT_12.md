# Production Readiness Increment 12 — Evidence-backed playbook details

Date: 2026-08-11

## Objective

Remove fabricated playbook capabilities from the administration projection and detailed UI.
The catalog must show only persisted backend facts and explicit unavailable states.

## Findings corrected

The detailed modal contained a frontend map that claimed specific parameters, MITRE tactics,
LDAP/Active Directory mutations, Redis token revocation, EDR isolation, ITSM delivery, audit
steps, and operational rollback. These claims were not supplied by the selected immutable
playbook version or its binding.

The backend also projected incident scopes, MITRE techniques, and automation-policy narratives
from static code maps rather than a persisted, versioned contract.

## Implementation

- Removed the frontend action-detail fallback map and its generic T1078 fallback.
- Removed unconditional “ready for production” and “rollback enabled and operational” labels.
- Removed static backend maps for incident types, MITRE codes, automation policy, and rollback.
- The backend now returns empty/`None` metadata until an approved physical contract persists it.
- The modal now renders only API fields: publication, version, engine binding, simulation mode,
  impact, approval mode, required parameters, credential aliases, mappings, incident scope,
  automation policy, rollback evidence, and last execution.
- Missing values use explicit bilingual unavailable states.
- The modal uses a responsive auto-fit grid, wrapping tags, bounded width, and no table overflow.
- Added dialog semantics and an accessible close label.
- Replaced the hardcoded Spanish details button with an i18n key.

No endpoint, DTO, database column, event, permission, or LIVE behavior changed.

## Verification

Backend:

```text
Focused governance and administration tests: 17 passed.
Host regression excluding the separately verified PostgreSQL alert-triage test:
190 passed, 3 dependency deprecation warnings.
Ruff E9/F critical rules for the changed backend module and test: passed.
```

Frontend final semantic implementation:

```text
ESLint: passed with zero warnings.
TypeScript project typecheck: passed.
Vitest: 8 files, 16 tests passed.
Vite production build: passed.
Main JS bundle: 513.59 kB minified / 147.85 kB gzip.
```

The first frontend run passed lint and typecheck but failed the new modal assertion after a
PowerShell text path converted newly added Spanish accents to `?`. The strings were regenerated
with Unicode-safe source material, verified byte-wise, and the complete chain then passed.

Vite's existing chunk-size warning remains and is tracked for the later bottleneck assessment.

## Security and rollback

The UI can no longer persuade an operator that an unmodeled action, mapping, connector, or
compensation is operational. LIVE remains disabled. Rollback is a code-only commit reversion;
restoring static capability claims is not suitable for production.
