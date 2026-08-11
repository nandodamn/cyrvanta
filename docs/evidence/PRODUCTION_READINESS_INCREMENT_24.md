# Production Readiness Increment 24 — Local deployment verification

Date: 2026-08-11

## Objective

Deploy the secure-default and frontend-performance increments to the local Compose environment
and verify the application through its actual reverse-proxy path.

## Deployment

Backend, worker, scheduler, and frontend images were rebuilt from `main` at commit `c1686c2`.
The application containers were recreated while PostgreSQL, RabbitMQ, Redis, OpenSearch,
Wazuh, n8n, and every persistent volume were preserved. No LIVE switch was enabled and no
secret value was read or printed.

## Verification

Observed container state after recreation:

```text
backend: healthy
frontend: healthy
reverse-proxy: healthy
postgres: healthy
rabbitmq: healthy
redis: healthy
opensearch: healthy
wazuh-manager: healthy
n8n: healthy (optional service already running)
worker: running, worker_ready logged
scheduler: running, scheduler heartbeat logged
```

Application probes through the edge path:

```text
GET http://localhost:8080/api/v1/health -> 200 {"status":"ok"}
GET http://localhost:8080/login -> 200, application root present
```

Backend startup completed PostgreSQL/Alembic initialization and Uvicorn startup without an
error in the inspected log window. The containerized frontend build reproduced the measured
lazy chunks and emitted no chunk-size warning.

## Operational observations

`cyrvanta-opensearch-dashboards-1` remains an exited historical container. It is not required
by the active core profile and was not removed because deletion is an independent operational
cleanup action.

The backend image build resolved dependencies from compatible version ranges and downloaded
new package releases. Although the resulting deployment is healthy, deterministic dependency
locking remains a production-readiness requirement and a probable supply-chain/reliability
bottleneck.

## Rollback

Application rollback consists of rebuilding a selected earlier Git revision. Data-service
volumes were not replaced or migrated by this increment.
