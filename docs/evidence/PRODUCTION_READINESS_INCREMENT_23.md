# Production Readiness Increment 23 — Lazy route boundaries

Date: 2026-08-11

## Objective

Reduce the JavaScript required for login and the primary dashboard by loading four already
modularized administration pages only when their routes are visited.

## Implementation

The API keys, governed memory, playbook library, and verified integrations pages now use
React lazy imports. A translated, accessible `role="status"` fallback is rendered while a
route chunk loads. The protected-route hierarchy and every route path remain unchanged.

No API, domain, data, event, permission, tenant-isolation, or LIVE execution contract changed.

## Measured result

The application chunk decreased from 159.24 kB (38.00 kB gzip) to 121.89 kB (30.99 kB gzip),
a 23.5% raw reduction. The deferred route assets are:

```text
Verified integrations: 2.64 kB (0.93 kB gzip)
API keys: 4.23 kB (1.58 kB gzip)
Playbook library: 13.71 kB (3.73 kB gzip)
Governed memory: 19.99 kB (4.77 kB gzip)
```

The shared vendor chunks remain stable and no Vite size warning is emitted. Pages still
embedded in `App.tsx` remain candidates for later extraction based on browser timing data.

## Verification

```text
ESLint: passed with zero warnings
TypeScript: passed
Vitest final suite: 12 files passed, 20 tests passed
Vite production build: passed, 118 modules transformed
```

The dedicated boundary regression verifies the four dynamic imports, absence of equivalent
static imports, and the accessible Suspense fallback.

## Rollback

Rollback replaces the four lazy imports with their prior static imports and removes the
Suspense wrapper. No data, deployment configuration, or service rollback is required.
