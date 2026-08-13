# Production Readiness Increment 31 — Authoritative active sessions

Date: 2026-08-13

## Objective

Ensure deactivation and password-change revocation take effect immediately and one refresh
token cannot be rotated concurrently more than once.

## Finding and implementation

Access-token decoding previously trusted the signed user/tenant claims without revalidating
that the user remained active. Refresh rotation used separate Redis `GET` and `DELETE`
operations, allowing two requests to consume the same token. A password change or deactivation
could also race with issuance of a replacement token.

Every authenticated request now resolves the signed tenant context and verifies the exact
tenant-owned user is still active. Permission queries independently require the same active
user and explicit tenant equality across role joins.

Refresh issuance and rotation now use Redis Lua transactions. Session records carry a
per-user generation; administrative revocation increments it before deleting indexed tokens.
A rotation succeeds only when the old record and generation still match, then consumes the
old token and creates the replacement atomically. Legacy four-field local sessions are read as
generation zero. Logout uses atomic `GETDEL`.

## Verification

```text
Focused authentication/session/token tests: 11 passed
Inactive user context: HTTP 401
Two rotations of one refresh record: first accepted, second rejected
Administrative revocation: generation increment occurs before token deletion
Ruff for changed files: passed
Mypy for changed sources: passed
```

Runtime Redis concurrency and full E2E login remain pending until Docker Desktop is available.
They are not represented as passed.

## Contract and security impact

No endpoint, DTO, database migration, permission name, tenant source, secret, or LIVE contract
changed. Refresh tokens remain opaque, stored only by SHA-256 digest, and returned only at
issuance. Redis remains an operational session store rather than a functional system of
record; PostgreSQL remains authoritative for user active state and tenant ownership.

## Rollback

Rollback is the single increment commit. It would restore delayed deactivation and the
refresh-token replay race and is not recommended.
