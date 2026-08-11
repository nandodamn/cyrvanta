# Production Readiness Increment 06 — Dependency validation fail-closed

Date: 2026-08-11

## Objective

Prevent playbook connection-dependency validation from swallowing an invalid artifact and
returning an empty or partial list as if validation had completed successfully.

## Governing contracts

- `docs/specifications/PHASE_21A_IMPLEMENTATION_CONTRACT.md`
- `docs/adr/0017-cyrvanta-native-playbook-engine.md`

## Implemented behavior

- Invalid portable artifacts and unavailable registered actions now raise the approved
  `PLAYBOOK_INVALID` conflict instead of being discarded by `except Exception: pass`.
- The existing connection-dependencies route translates that conflict to HTTP 409 using the
  established problem boundary.
- Resolver results remain tenant-scoped and preserve their explicit `not_resolved` and
  blocking fields.
- Unexpected infrastructure errors are no longer converted into apparent successful partial
  results; they propagate to the normal server error boundary and observability pipeline.

No migration, endpoint path, response DTO, permission, event, or database contract changed.

## Verification performed

```text
python -m ruff check backend/tests/unit/test_playbook_dependency_validation.py
Result: All checks passed.

python -m pytest \
  backend/tests/unit/test_playbook_dependency_validation.py \
  backend/tests/unit/test_playbook_administration_contract.py -q
Result: 7 passed.

python -m pytest backend/tests \
  --ignore=backend/tests/unit/test_alert_triage.py -q
Result: 174 passed, 3 dependency deprecation warnings.
```

The alert-triage test remains excluded only because PostgreSQL is not exposed to the host.

## Rollback

Revert this increment's commit. No data rollback is required. Restoring silent partial
success is not suitable for production.
