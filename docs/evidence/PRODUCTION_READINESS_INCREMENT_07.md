# Production Readiness Increment 07 — Playbook readiness and approval governance

Date: 2026-08-11

## Objective

Make the playbook-definition API fail closed when no engine binding, ATT&CK mapping, or
rollback implementation exists, and prevent approval governance from being weakened below
the predefined minimum.

## Governing contracts

- `docs/specifications/PHASE_21A_CYRVANTA_PLAYBOOK_ENGINE.md`
- `docs/specifications/PHASE_21A_IMPLEMENTATION_CONTRACT.md`
- `docs/adr/0017-cyrvanta-native-playbook-engine.md`
- `docs/adr/0018-native-default-optional-n8n-secret-lifecycle.md`

## Implemented behavior

- A definition with no persisted engine binding now projects `PENDING` and inactive instead
  of `SYNCHRONIZED` and active.
- Unknown definition codes no longer receive default incident type `all-incidents` or ATT&CK
  technique `T1078`.
- Rollback support, target, and guidance are not projected until a real compensation contract
  is persisted and bound. Current definitions therefore project rollback as unsupported.
- Approval modes use an explicit order: `AUTOMATIC < SINGLE < FOUR_EYES`.
- The API rejects attempts to set a mode below the predefined minimum with
  `PLAYBOOK_REVIEW_SEPARATION_REQUIRED`.
- Bootstrap reconciliation raises a policy that is too weak but preserves an operator-selected
  policy that is stricter than the predefined minimum.

No migration, endpoint, DTO, permission, event, or historical row changed.

## Security and multitenancy

All reads and mutations retain authenticated tenant context, RLS, and audit behavior. The
change prevents false activation and policy downgrades; it does not expose artifact inputs,
credentials, or cross-tenant metadata.

## Verification performed

```text
python -m py_compile \
  backend/src/cyrvanta/modules/playbooks/application/administration_service.py
Result: passed.

python -m ruff check backend/tests/unit/test_playbook_governance_projection.py
Result: All checks passed.

python -m pytest \
  backend/tests/unit/test_playbook_governance_projection.py \
  backend/tests/unit/test_essential_native_playbooks.py \
  backend/tests/unit/test_playbook_administration_contract.py -q
Result: 18 passed.

python -m pytest backend/tests \
  --ignore=backend/tests/unit/test_alert_triage.py -q
Result: 185 passed, 3 dependency deprecation warnings.
```

The alert-triage test remains excluded only because PostgreSQL is not exposed to the host.

## Rollback

Revert this increment's commit. No data rollback is required. Reintroducing active/synchronized
defaults, default T1078, unconditional rollback, or approval downgrades is not suitable for
production.
