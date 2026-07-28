# 04 — Technology Stack

## 1. Selection principles

Technology choices prioritize:

- Open-source availability.
- on-premise operation.
- mature security posture.
- strong ecosystem.
- replaceability.
- developer productivity.
- laptop demo feasibility.
- enterprise deployment path.
- observable and testable behavior.

Exact versions must be pinned in lock files and container manifests at implementation time. Upgrades require compatibility testing.

## 2. Host environment

### Windows 11

Used for laptop development and demonstration.

### WSL2

Provides the Linux integration layer used by Docker Desktop and shell tooling.

### Docker Desktop

Runs the development containers. Production deployments should use a supported Linux container runtime and Docker Compose or an orchestrator appropriate to scale.

### Ollama on host

Development endpoint:

```text
http://host.docker.internal:11434
```

Host-side health check:

```text
http://localhost:11434/api/tags
```

The application configuration must support a different endpoint in production.

## 3. AI inference

### Ollama

Role: local inference runtime.

Requirements:

- Bind only to required interfaces.
- restrict access with host firewall.
- no public exposure.
- models stored outside source control.
- health and model-availability checks.
- configurable timeout, context and concurrency.

### Gemma 4

Default development family. The exact tag is hardware-dependent.

Recommended configuration policy:

- Low-resource laptop: `gemma4:e4b`.
- Moderate GPU/RAM: `gemma4:12b`.
- Capable workstation: `gemma4:26b`.
- 31B only after hardware validation.

Configuration example:

```env
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=gemma4:e4b
AI_REQUEST_TIMEOUT_SECONDS=120
AI_MAX_CONCURRENT_REQUESTS=1
```

The architecture must not assume that every installation uses the same Gemma size.

## 4. Backend

### Python

Target: current supported stable Python release validated by the selected libraries. Pin the exact minor version in `.python-version`, containers and CI.

### FastAPI

Role: REST API, dependency integration, OpenAPI generation and transport validation.

### Pydantic

Role: boundary schemas and configuration.

### SQLAlchemy 2.x

Role: asynchronous PostgreSQL persistence implementation.

### Alembic

Role: versioned database migrations.

### HTTPX

Role: asynchronous calls to Ollama and HTTP integrations.

### Structured logging

Use Python standard logging with a structured JSON formatter or an approved lightweight library. Every log includes service, environment, correlation ID and tenant ID where authorized.

## 5. Database

### PostgreSQL

Role: system of record.

Required capabilities:

- UUID support.
- JSONB for bounded metadata.
- Row-Level Security.
- transactions.
- full-text search only for limited application data.
- robust backup and restore.
- read replicas in future scale-out.

Use PostgreSQL schemas deliberately; do not create one schema per tenant in the first release.

## 6. Search and telemetry

### OpenSearch

Role: high-volume telemetry search, aggregation and source evidence retrieval.

Rules:

- Access through an internal adapter.
- read-only credentials for search functions.
- separate write credentials when ingestion is required.
- allowlisted index patterns.
- query timeout and result limits.
- tenant filter injected by the adapter.
- no user-supplied raw DSL without validation.

### Wazuh

Role: initial SIEM/XDR event and alert source.

Cyrvanta must support the Wazuh deployment model selected for the lab without assuming Wazuh is permanent. All Wazuh-specific payloads are transformed into canonical models.

## 7. Messaging and cache

### RabbitMQ

Role: durable job queues, retries and dead letters.

Suggested logical exchanges:

- `cyrvanta.commands`
- `cyrvanta.events`
- `cyrvanta.deadletter`

Messages use versioned envelopes with tenant ID, correlation ID, event ID, timestamp and payload version.

### Redis

Role: cache, distributed locks, rate-limit state and ephemeral job progress.

Do not store irreplaceable incident data in Redis.

## 8. Automation

### n8n

Role: initial workflow execution adapter for demo and MVP.

Security restrictions:

- private network only.
- separate service account.
- only allowlisted workflow IDs.
- authenticated callbacks.
- secrets stored in n8n credentials or external secret manager.
- no direct analyst access unless explicitly authorized.
- avoid arbitrary command-execution nodes in approved production workflows.

## 9. Frontend

### React

Use a current stable React release supported by the chosen ecosystem and pinned at initialization.

### TypeScript

Strict mode mandatory.

### Vite

Preferred build tool for the single-page web application unless server-side rendering becomes a documented requirement.

### Routing

Use a mature React router.

### Server state

Use TanStack Query or equivalent approved query-state library.

### Forms

Use React Hook Form plus schema validation.

### Visual system

Use an accessible component foundation and project-owned design tokens. A library may accelerate primitives, but Cyrvanta must maintain its own visual identity.

### Charts

Use an enterprise-capable chart library with accessible fallbacks. Avoid encoding severity by color alone.

### Internationalization

Use i18next/react-i18next or equivalent.

Required locales:

- `es-UY` or configurable Spanish base.
- `en-US`.

Translation keys are stable and code-reviewed.

## 10. Reverse proxy

Use Nginx, Traefik or Caddy based on deployment requirements. The initial Compose environment may use Nginx.

Responsibilities:

- TLS termination where enabled.
- routing.
- security headers.
- request-size limits.
- rate-limiting support.
- WebSocket/SSE proxying.
- no exposure of internal service ports.

## 11. Authentication and cryptography

- Argon2id for local password hashing.
- standards-based JWT access tokens where appropriate.
- refresh tokens stored and rotated securely.
- LDAP/LDAPS adapter for Active Directory.
- cryptographically secure random identifiers and secrets.
- approved platform crypto libraries only.
- never implement custom cryptography.

## 12. Testing

Backend:

- pytest.
- pytest-asyncio.
- HTTPX test client.
- testcontainers or isolated Compose services.
- property-based testing where useful.

Frontend:

- Vitest.
- React Testing Library.
- Playwright for end-to-end tests.

Security and quality:

- Ruff.
- mypy or Pyright strict configuration.
- ESLint.
- Prettier.
- dependency scanning.
- secret scanning.
- container image scanning.
- SAST.

## 13. Documentation

- Markdown as source.
- Mermaid for maintainable diagrams where supported.
- OpenAPI generated and reviewed.
- ADRs under `docs/adr`.
- runbooks under `docs/runbooks`.
- bilingual user-facing documentation introduced after core specifications.

## 14. Local container groups

To conserve laptop resources, Docker Compose profiles should be used:

```text
core:
  postgres, redis, rabbitmq, api, worker, frontend

security:
  wazuh, opensearch/indexer, dashboards

automation:
  n8n

observability:
  optional metrics/logging stack
```

Ollama stays on the host in development and is not part of the default Compose profile.

## 15. Deferred technologies

Do not add initially unless justified by measured need:

- Kubernetes.
- Kafka.
- service mesh.
- GraphQL.
- separate vector database.
- Elasticsearch in addition to OpenSearch.
- multiple backend microservices.
- custom model training platform.
- complex data lake.
- blockchain or immutable ledger products.

PostgreSQL vector extensions may be evaluated later for bounded RAG use, but MITRE ATT&CK lookup should begin with structured relational and deterministic search.
