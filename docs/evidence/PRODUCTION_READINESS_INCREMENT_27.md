# Production Readiness Increment 27 — Reproducible frontend dependency chain

Date: 2026-08-11

## Objective

Remove known frontend dependency vulnerabilities and make the production image resolve the
reviewed lockfile from immutable base images.

## Initial finding

The committed dependency graph reported 12 vulnerable package groups: 1 critical, 6 high,
3 moderate, and 2 low. The affected graph included Vitest, Vite, React Router, ESLint, and
transitive build dependencies. Although most are build-time packages, they remain part of
the trusted production supply chain.

## Implementation

- React Router is pinned to 7.18.2.
- Vite 8.2.1, Vitest 4.1.10, ESLint 9.39.5, and their compatible direct toolchain packages
  are pinned in `package.json` and `package-lock.json`.
- The lockfile's safe transitive resolutions include the corrected `brace-expansion` and
  `js-yaml` releases.
- The Node build image and nginx runtime image are pinned to observed SHA-256 digests.
- Docker copies both npm manifests and uses `npm ci --ignore-scripts`.
- Vite 8's functional `manualChunks` contract preserves the existing vendor separation.
- A regression test protects immutable bases, lockfile use, corrected direct versions, and
  the Vite 8 chunk contract.
- TypeScript explicitly includes Node types for build configuration and file-based tests.

## Verification

```text
No-cache final multi-stage image build: passed
npm ci --ignore-scripts: 260 packages installed; 0 vulnerabilities
npm audit --json: 0 vulnerabilities across 282 dependency records
ESLint: passed with zero warnings
TypeScript project check: passed
Vitest: 13 files passed, 22 tests passed
Vite production build: passed without chunk-size warnings
Largest emitted JavaScript chunk: 166.83 kB (45.37 kB gzip)
nginx configuration test in final image: passed
Final image contains no Node executable or /app/node_modules: confirmed
```

## Contract and security impact

No domain, database, API, event, permission, tenant, credential, secret, or LIVE automation
contract changed. The final image still contains only nginx and static artifacts; the Node
toolchain remains confined to the discarded build stage.

## Rollback

Rollback is the single increment commit. Reverting would restore known vulnerable build
dependencies and non-reproducible `npm install`, so a forward-reviewed dependency change is
preferred if an unforeseen compatibility issue is found.
