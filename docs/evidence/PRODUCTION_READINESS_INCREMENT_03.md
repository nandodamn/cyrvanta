# Production Readiness Increment 03 — Evidence-grounded incident analysis

Date: 2026-08-11

## Objective

Remove the legacy incident-analysis fallback that presented a fixed credential-abuse
narrative, three ATT&CK techniques, a synthetic confidence, and a provisional risk as
grounded when the tenant had no persisted enrichment evidence.

## Governing contracts

- `docs/specifications/PHASE_17_CLAIM_LEDGER.md`
- `docs/specifications/PHASE_19_MITRE_RISK_EXPLAINABILITY.md`
- `docs/adr/0011-append-only-epistemological-claim-ledger.md`
- `docs/adr/0013-versioned-attack-risk-explainability.md`

## Implemented behavior

- Missing risk assessment now returns an explicit bilingual evidence-insufficient state.
- Missing evidence returns no ATT&CK techniques, recommendations, confidence, or risk score.
- The response uses `provider=none`, `model=not-applicable`,
  `mode=evidence-unavailable`, and `grounded=false`.
- Claims are not recorded for an ungrounded response.
- Persisted enrichment is projected only when it has a complete grounded bilingual
  explanation.
- Only persisted mappings in `SUPPORTED` or `VALIDATED` state are projected.
- The old hard-coded response recommendations are removed because Phase 19 explicitly
  leaves recommendations outside that decision and no persisted recommendation claim was
  being projected.
- The incident UI does not render `0/100` as if it were an assessed zero risk; it shows an
  explicit bilingual evidence-insufficient label and hides absent technique identifiers.

No schema, migration, endpoint, event, permission, or adapter contract changed.

## Security and multitenancy

The existing authenticated tenant context and tenant-scoped enrichment query are unchanged.
The change reduces false security assertions and prevents ungrounded claim creation. No raw
evidence, secret, prompt, or tenant identifier is added to logs or frontend state.

## Verification performed

Backend focused verification:

```text
python -m ruff format <changed Python files>
python -m ruff check <changed Python files>
Result: All checks passed.

python -m pytest \
  backend/tests/unit/test_operations_analysis_grounding.py \
  backend/tests/unit/test_operations.py \
  backend/tests/unit/test_attack_risk.py -q
Result: 15 passed.

python -m pytest backend/tests \
  --ignore=backend/tests/unit/test_alert_triage.py -q
Result: 167 passed, 3 dependency deprecation warnings.

```
The excluded alert-triage test requires PostgreSQL access that is not exposed to the host.


Frontend verification:

```text
npm --prefix frontend run lint
Result: passed with zero warnings.

npm --prefix frontend run typecheck
Result: passed.

npm --prefix frontend test -- --run
Result: 8 files passed, 16 tests passed.

npm --prefix frontend run build
Result: passed.
```

The production build still reports the pre-existing JavaScript chunk warning at 519.55 kB.
It does not fail the build and remains a performance-hardening item for the later bottleneck
assessment.

## Rollback

Revert this increment's commit. No data rollback is required because it adds no migration and
does not rewrite or delete historical claims, mappings, assessments, explanations, or events.
The former fabricated fallback must not be restored in production.
