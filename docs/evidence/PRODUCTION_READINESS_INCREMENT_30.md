# Production Readiness Increment 30 — Production configuration fail-closed

Date: 2026-08-13

## Objective

Prevent a production process from starting with development placeholders, insecure browser
transport, or an invalid installation encryption key.

## Finding and implementation

`ENVIRONMENT=production` previously enabled secure cookies by default but still accepted an
explicit insecure cookie override, placeholder database/RabbitMQ/JWT credentials, wildcard
CORS, HTTP browser origins, and a malformed 44-character encryption key.

Settings now reject those states during startup. Production requires secure session cookies,
explicit HTTPS frontend/CORS origins, non-placeholder database, RabbitMQ and JWT credentials,
non-default RabbitMQ credentials, and a URL-safe base64 installation key decoding to exactly
32 bytes. Development and test behavior is unchanged.

Validation errors contain only a category and never echo credential values or connection URLs.

## Verification

```text
Focused configuration/session/event tests: 24 passed
Valid production configuration: accepted
Eight unsafe production variants: rejected
Ruff for changed files: passed
Mypy for changed source: passed
```

## Contract and security impact

No domain, database, API, event, permission, tenant, or LIVE contract changed. This is a
startup configuration guard. Deployments marked production must supply their public HTTPS
origin even when TLS terminates at an upstream load balancer.

## Rollback

Rollback is the single increment commit. It would permit unsafe production startup again and
is not recommended.
