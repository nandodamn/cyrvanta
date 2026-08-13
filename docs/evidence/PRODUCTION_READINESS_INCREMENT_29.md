# Production Readiness Increment 29 — Reverse-proxy boundary enforcement

Date: 2026-08-13

## Objective

Ensure browser and host traffic cannot bypass Cyrvanta's reverse-proxy security boundary.

## Finding and implementation

The backend service published port 8000 on every host interface. Requests could therefore
reach FastAPI directly and bypass the proxy's internal-route denial, rate limiting, request
metadata, and response security headers.

The direct host publication was removed. Backend port 8000 remains reachable only by services
on the private Compose network, including the reverse proxy and its health checks. The only
standard browser entry point remains reverse-proxy port 8080. Its nginx runtime image is now
pinned to the same reviewed SHA-256 digest used by the frontend runtime.

## Verification

```text
Reverse-proxy configuration tests: 2 passed
Ruff for changed test: passed
docker compose config --quiet: passed
Regression: docker-compose.yml contains no "8000:8000" host publication
```

Runtime port inspection and HTTP verification remain pending because Docker Desktop is
offline. They are not represented as passed.

## Contract and security impact

No API route, domain, database, event, permission, tenant, secret, or LIVE contract changed.
Container-internal health and service-to-service traffic retain `backend:8000`. Local users
access the application through `http://localhost:8080`.

## Rollback

Rollback is the single increment commit. Reintroducing the direct port would reopen the
documented security-control bypass and is not recommended.
