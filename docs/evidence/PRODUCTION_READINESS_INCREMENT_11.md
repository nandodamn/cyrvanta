# Production Readiness Increment 11 — Tenant-scoped playbook administration

Date: 2026-08-11

## Objective

Apply explicit tenant predicates to the Playbook Administration application service so
definition, version, binding, action-binding, and execution metadata queries do not rely on
PostgreSQL RLS as their sole tenant-isolation control.

## Scope

Explicit tenant predicates now protect:

- definition list/count, lookup, bootstrap, creation, and governance updates;
- version lookup, duplicate detection, validation, publication, dry-run, and latest-version
  projection;
- engine binding list/count, creation, probing, activation, deactivation of alternate bindings,
  and enriched-definition projection;
- native action-binding duplicate detection and readiness checks;
- latest execution metadata shown for a definition.

The `_locked_version` and `_native_actions_ready` helpers now require tenant context. Enriched
definition queries bind related records to the definition's own persisted tenant id.

## Contract impact

- Domain: none.
- Database schema and migrations: none.
- API and DTOs: none.
- Events and queues: none.
- Permission semantics: none.
- LIVE automation: unchanged and disabled.

## Regression guard

A new AST-based unit test walks every SQLAlchemy `select(...)` of tenant-owned administration
models and requires the corresponding model's `tenant_id` predicate. It also verifies tenant
propagation into query helpers and enriched projections.

Verification results:

```text
Focused playbook administration/governance suite: 15 passed.
AST tenant-filter test after final formatting correction: 2 passed.
Backend host regression excluding the separately verified PostgreSQL alert-triage test:
190 passed, 3 dependency deprecation warnings.
Ruff critical rules E9/F for changed module and test: passed.
Ruff full check for the new test: passed after automatic import ordering.
```

The large pre-existing administration module still reports 53 legacy Ruff style/import
placement findings outside this increment's security scope. They do not include syntax or
undefined-name failures and remain tracked as production-readiness cleanup rather than being
mixed into this isolation change.

## Security and rollback

Cross-tenant identifiers now fail closed in application-generated SQL even if RLS is
misconfigured or a privileged connection bypasses policy enforcement. Existing RLS remains the
second barrier. Rollback is a code-only commit reversion; no data rollback is required.
