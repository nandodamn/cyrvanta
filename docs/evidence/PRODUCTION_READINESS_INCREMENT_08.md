# Production Readiness Increment 08 — Native action-binding tenant filter

Date: 2026-08-11

## Objective

Add explicit service-layer tenant filtering to native action-binding lookup during both
pre-dispatch validation and action execution, in addition to PostgreSQL RLS.

## Governing contracts

- `docs/foundation/02_SYSTEM_ARCHITECTURE.md`
- `docs/specifications/PHASE_21A_IMPLEMENTATION_CONTRACT.md`
- `docs/adr/0017-cyrvanta-native-playbook-engine.md`

## Implemented behavior

- `_validate_action_bindings` now requires `NativeActionBindingModel.tenant_id` to match the
  authenticated execution tenant.
- `_execute_action` repeats the explicit tenant predicate when locking and resolving the
  connector binding immediately before execution.
- Existing tenant sessions, PostgreSQL RLS, action allowlist, simulated-only connector type,
  active state, verification timestamp, configuration digest, and credential checks remain
  in force.

No migration, API, DTO, event, permission, binding state, or execution result changed.

## Verification performed

```text
python -m ruff check \
  backend/src/cyrvanta/modules/playbooks/infrastructure/native_engine.py \
  backend/tests/unit/test_native_engine_tenant_filters.py
Result: All checks passed.

python -m pytest \
  backend/tests/unit/test_native_engine_tenant_filters.py \
  backend/tests/unit/test_native_playbook_engine.py -q
Result: 12 passed.

python -m pytest backend/tests \
  --ignore=backend/tests/unit/test_alert_triage.py -q
Result: 186 passed, 3 dependency deprecation warnings.
```

An earlier command referenced non-existent `test_native_engine.py` and therefore ran no
tests; it was corrected immediately to `test_native_playbook_engine.py`. The excluded
alert-triage test still requires PostgreSQL access not exposed to the host.

## Rollback

Revert this increment's commit. No data rollback is required. Removing the explicit tenant
predicates would reduce defense in depth and is not recommended.
