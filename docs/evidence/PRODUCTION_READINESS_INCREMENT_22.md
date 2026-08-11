# Production Readiness Increment 22 — Frontend production chunking

Date: 2026-08-11

## Objective

Remove the production-build warning caused by a single 512.58 kB JavaScript bundle and
establish stable cache boundaries for the frontend's main dependency groups.

## Implementation

Vite/Rollup now emits separate chunks for:

- React and React Router;
- TanStack Query;
- forms and schema validation;
- internationalization;
- Cyrvanta application code.

The grouping uses only dependencies already pinned in `package.json`. No dependency, route,
API contract, permission, tenant behavior, or LIVE automation setting changed.

## Measured result

Before:

```text
index.js: 512.58 kB (147.60 kB gzip)
Vite warning: chunk larger than 500 kB
```

After:

```text
vendor-react: 172.45 kB (57.05 kB gzip)
application: 159.24 kB (38.00 kB gzip)
vendor-forms: 82.83 kB (22.88 kB gzip)
vendor-i18n: 49.28 kB (15.37 kB gzip)
vendor-query: 46.61 kB (14.36 kB gzip)
```

The largest chunk decreased by 66.4%, and Vite emitted no chunk-size warning. Stable vendor
boundaries also avoid invalidating all dependency bytes when only application code changes.

This increment does not claim route-level lazy loading or a lower total transfer for the first
authenticated navigation. Extracting the remaining pages from the monolithic `App.tsx` is a
separate, larger refactor to assess with real browser timings.

## Verification

```text
TypeScript: passed
ESLint: passed with zero warnings
Vitest: 11 files passed, 19 tests passed
Vite production build: passed, 117 modules transformed
Vite chunk-size warning: absent
```

## Security, operations, and rollback

Authentication, authorization, tenant context, CSP-relevant asset origin, and API traffic are
unchanged. The generated assets remain content-hashed. Rollback is the removal of the Rollup
`manualChunks` configuration; no data or service rollback is required.
