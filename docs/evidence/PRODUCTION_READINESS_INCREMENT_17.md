# Production Readiness Increment 17 - Future capability resolution fails closed

Date: 2026-08-11

## Objective

Prevent unimplemented future connectors from being represented as resolvable capabilities and
make capability metadata statically type-safe.

## Implementation

- Removed local-user, local-firewall, Defender, Palo Alto, ServiceNow and MISP capabilities from
  the resolvable catalog. Their placeholder modules remain simulation-only and unregistered.
- Added a `TypedDict` contract for capability policy metadata.
- Narrowed the tenant integration `capabilities_snapshot` as untrusted JSON before membership
  checks; only string items in a list are considered declared capabilities.
- Added parameterized regressions proving eight future capabilities return
  `capability_not_registered`, disclose no connector type and do not access tenant persistence.

Existing supported catalog entries for Wazuh, OpenSearch, Ollama, optional n8n and the laboratory
SMTP sink remain unchanged. No endpoint, DTO, schema, migration, event, permission or secret
contract changed. LIVE remains disabled.

## Verification

```text
Focused Ruff: passed.
Resolver mypy: passed with no issues.
Resolver/fail-closed tests: 14 passed.
Backend suite excluding the separately verified PostgreSQL alert-triage test:
206 passed, 3 dependency deprecation warnings.
Full backend mypy after this increment: 1 remaining error in playbook administration
(down from 9 errors before increment 17).
```

The first resolver mypy run retained one error because JSON returned by
`capabilities_snapshot.get()` still had type `object`. The value is now explicitly narrowed to a
list of strings, after which focused mypy passed.

## Security and rollback

An arbitrary active integration row can no longer make a future, unimplemented connector appear
available through the resolution endpoint. Unknown or unavailable capabilities fail before
database access and expose no candidate connector. Rollback is a code-only commit reversion; it
would restore misleading capability availability and is not recommended without an approved and
registered connector adapter.
