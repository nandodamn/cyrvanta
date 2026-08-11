# Production Readiness Increment 05 — Truthful playbook library projection

Date: 2026-08-11

## Objective

Remove frontend-only assertions that presented connector readiness, ATT&CK mappings, and
rollback support without backend evidence.

## Governing contracts

- `docs/specifications/PHASE_21A_CYRVANTA_PLAYBOOK_ENGINE.md`
- `docs/specifications/PHASE_21A_IMPLEMENTATION_CONTRACT.md`
- `docs/adr/0017-cyrvanta-native-playbook-engine.md`
- `docs/adr/0018-native-default-optional-n8n-secret-lifecycle.md`

## Implemented behavior

- Removed the static four-playbook integration map and its fabricated pending-credential
  banners.
- Activation and engine changes are submitted to the backend, which remains the authority
  for verified action bindings, synchronization, credentials, and kill switches.
- Removed the unconditional `T1078` fallback. Definitions without persisted mappings show
  an explicit bilingual no-supported-mappings state.
- Removed the unconditional rollback badge. It is rendered only when
  `rollback_supported=true` is returned by the backend.
- Simplified modal selection so it no longer receives a frontend-invented connector.
- Added a regression assertion that forbids `T1078` and rollback labels for a definition
  whose backend response contains no mappings and `rollback_supported=false`.

No backend, database, endpoint, DTO, permission, event, or secret contract changed.

## Security and multitenancy

The change removes client-side policy assertions and delegates authorization and readiness
to the authenticated tenant-scoped backend. It neither stores nor exposes credential
values.

## Verification performed

```text
npm --prefix frontend run lint
Result: passed with zero warnings.

npm --prefix frontend run typecheck
Result: passed.

npm --prefix frontend test -- --run
Result: 8 files passed, 16 tests passed.

npm --prefix frontend run build
Result: passed; main JavaScript chunk 518.10 kB (149.64 kB gzip).
```

The known chunk-size warning remains and is tracked for the bottleneck/performance stage.

## Rollback

Revert this increment's commit. No data rollback is required. The static connector map and
fabricated MITRE/rollback fallbacks must not be restored for production.
