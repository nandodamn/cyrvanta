# Production Readiness Increment 14 - Unsafe legacy rollback removal

Date: 2026-08-11

## Objective

Remove the legacy incident rollback path that performed unrelated bulk mutations and replace
fabricated response-history values with persisted evidence or an explicit unavailable state.

## Implementation

- Removed `IncidentService.execute_rollback` and its non-contract
  `POST /incidents/{incident_id}/rollback` route.
- Removed the frontend API client and control that invoked that route.
- Eliminated the bulk user reactivation by demo/synthetic email pattern and the blanket update
  of proposal and approval states. No replacement compensation action was invented because an
  approved compensation contract does not yet exist.
- Approval progress now uses the persisted `required_approvals` value and actual approval
  decisions.
- Response history now shows persisted actor identifiers, requester identifiers, targets and
  client IP values. Missing evidence is rendered as unavailable instead of a demo identity,
  loopback address or synthetic target.

No schema, migration, event contract or replacement endpoint was added. LIVE remains disabled.

## Verification

```text
Backend new regression and critical Ruff checks: passed.
Backend regression excluding the separately verified PostgreSQL alert-triage test:
191 passed, 3 warnings.
Frontend ESLint: passed with zero warnings.
Frontend TypeScript project typecheck: passed.
Frontend Vitest full suite: 10 files, 18 tests passed.
Frontend Vite production build: passed.
Main JS bundle: 512.58 kB minified / 147.60 kB gzip.
git diff --check: passed.
```

During verification, two test-harness issues were found and corrected: missing separators in
the added i18n keys and an unsupported `import.meta.url` scheme in the new source-regression
test. The complete verification chain passed after both corrections. The Vite chunk-size
warning remains tracked for the later bottleneck and capacity assessment.

## Security, tenancy and auditability

Removing the route prevents a single incident operation from reactivating users selected by a
global email pattern or rewriting every related governance record. Existing tenant-scoped read
models remain unchanged. The interface no longer represents invented identities or network
evidence as recorded audit data.

## Rollback

Rollback is a code-only commit reversion and has no data rollback. Restoring the removed route
is not recommended without a formally approved, tenant-scoped compensation specification,
authorization rules, immutable audit events and targeted tests.
