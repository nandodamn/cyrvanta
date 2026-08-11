# Production Readiness Increment 09 — PostgreSQL and local deployment verification

Date: 2026-08-11

## Objective

Close the host-network test gap against PostgreSQL and deploy the verified `main` revision to
the local Compose environment without enabling LIVE automation.

## PostgreSQL-backed test

The runtime image intentionally excludes test dependencies and sources. A disposable
Compose-run container was therefore created with:

- the backend source mounted read-only;
- pytest installed only inside the disposable container;
- the normal internal Compose network and service environment;
- pytest temporary output under `/tmp`;
- no image, source, or persistent-volume mutation.

Result:

```text
python -m pytest tests/unit/test_alert_triage.py -q
1 passed, 2 read-only pytest-cache warnings.
```

The warnings concern `.pytest_cache` on the deliberately read-only source mount, not the
test or PostgreSQL transaction.

Combined with the host regression from Increment 08, all current backend tests have now been
executed in an environment where their required dependencies are reachable:

- 186 passed in the host regression excluding alert triage;
- 1 passed separately against PostgreSQL inside Compose.

## Local deployment

Fresh images were built for backend, worker, scheduler, and frontend. The initial combined
build command reached its 180-second client timeout after producing the images but before
service recreation completed. Image timestamps were inspected, and a second `compose up`
without `--build` successfully recreated the application services.

Observed after recreation:

```text
backend: healthy
frontend: healthy
reverse-proxy: healthy
postgres: healthy
rabbitmq: healthy
redis: healthy
opensearch: healthy
wazuh-manager: healthy
n8n: healthy (optional service previously started)
worker: running
scheduler: running
GET http://localhost:8080/api/v1/health -> 200 {"status":"ok"}
GET http://localhost:8080/login -> 200
```

Backend startup logs show Alembic initialization, successful application startup, and health
checks returning 200. No LIVE switch was enabled.

## Container inventory note

`cyrvanta-opensearch-dashboards-1` remains an exited historical container, but
`opensearch-dashboards` is not present in the current `docker compose config --services`.
It is therefore an orphan from an older topology, not a required service failure. It was not
deleted automatically because removal is operational cleanup and the current request did not
require destructive container deletion.

## Rollback

The prior stopped application containers were replaced by Compose and the current named
images now reference the verified source. Data-service volumes were preserved. Application
rollback would require rebuilding a selected earlier Git revision; no database downgrade or
data deletion was performed.
