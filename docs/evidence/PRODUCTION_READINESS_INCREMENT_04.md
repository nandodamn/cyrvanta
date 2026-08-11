# Production Readiness Increment 04 — n8n binding fail-closed

Date: 2026-08-11

## Objective

Prevent the playbook administration API from fabricating a synchronized n8n binding or
activating an unverified/drifted binding.

## Governing contracts

- `docs/specifications/PHASE_21_N8N_WORKFLOWS_EXECUTION.md`
- `docs/specifications/PHASE_21A_IMPLEMENTATION_CONTRACT.md`
- `docs/adr/0015-versioned-playbooks-n8n-execution.md`
- `docs/adr/0017-cyrvanta-native-playbook-engine.md`
- `docs/adr/0018-native-default-optional-n8n-secret-lifecycle.md`

## Implemented behavior

- The definition-level toggle no longer creates `local-demo` n8n identifiers, webhook
  paths, key IDs, observed digests, or verification timestamps.
- Selecting n8n without a separately created and reconciled binding now fails with
  `PLAYBOOK_BINDING_UNAVAILABLE`.
- A toggle no longer changes `sync_status`, copies the desired digest into the observed
  digest, or invents a verification timestamp.
- Activation requires `SYNCHRONIZED`, a real verification timestamp, and matching desired
  and observed digests.
- Drift fails with `PLAYBOOK_BINDING_DRIFTED`.
- The generic probe no longer treats the mere presence of `N8N_API_KEY` and `N8N_ENABLED`
  as proof that a workflow exists or matches the approved artifact. Until a real
  reconciliation result is connected, n8n probing remains unavailable and inactive.

No migration, API shape, event name, permission, secret value, or historical row changed.

## Secret lifecycle governance gap

The approved contract requires write-only replace/test/rotate operations for the n8n API
key and metadata-only operations for internal dispatch/callback keys. The current product
supports an external environment/secret-manager handoff and purpose-separated one-use
internal key derivation, but it has no approved physical tenant-scoped catalog for mutable
n8n configuration or secret metadata. Implementing tables, columns, endpoints, DTOs, or
rotation-window persistence would cross the repository specification gate. This gap must be
resolved by an approved physical contract before those persistence operations are coded.

## Security and multitenancy

Existing tenant-scoped queries, RLS, audit writes, and permissions are unchanged. The change
removes false-positive synchronization and activation paths and does not expose credentials,
workflow internals, or cross-tenant identifiers.

## Verification performed

```text
python -m ruff check backend/tests/unit/test_n8n_binding_fail_closed.py
Result: All checks passed.

python -m pytest \
  backend/tests/unit/test_n8n_binding_fail_closed.py \
  backend/tests/unit/test_playbook_administration_contract.py \
  backend/tests/unit/test_n8n_reconciliation_security.py -q
Result: 15 passed.

python -m pytest backend/tests \
  --ignore=backend/tests/unit/test_alert_triage.py -q
Result: 173 passed, 3 dependency deprecation warnings.

```

Whole-file Ruff on `administration_service.py` still reports 54 pre-existing findings,
primarily long catalog strings, historical import placement, and one broad exception. These
were not introduced by this increment and are not reported as passing.

## Rollback

Revert this increment's commit. No data rollback is required. Restoring the former
`local-demo` synchronization behavior is not suitable for production.
