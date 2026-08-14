# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Cyrvanta is a multitenant, AI-assisted cybersecurity operations (SOC) platform: alert correlation, incident management, MITRE ATT&CK enrichment, and controlled response — without ceding control of data, infrastructure, or authorization decisions to the AI. Bilingual (Spanish/English) as a first-class requirement. On-premise deployable, vendor-independent via ports and adapters.

## Mandatory reading before changing code

`AGENTS.md` is binding for this whole repo. Before creating, modifying, renaming, or deleting files, read in this order:

1. `docs/foundation/README.md`
2. `docs/foundation/01_PROJECT_VISION.md`
3. `docs/foundation/02_SYSTEM_ARCHITECTURE.md`
4. `docs/foundation/03_DEVELOPMENT_RULES.md`
5. `docs/foundation/04_TECHNOLOGY_STACK.md`
6. `docs/foundation/AI_DEVELOPER_MASTER_PROMPT.md`
7. The approved specification for the affected module.
8. Related ADRs, contracts, migrations, and tests.

Precedence on conflicts: multitenancy/security isolation > approved AGESIC requirements > `03_DEVELOPMENT_RULES.md` > `02_SYSTEM_ARCHITECTURE.md` > later approved specs/ADRs > technical convenience. Stop and surface material contradictions instead of silently changing architecture. Documents marked `DRAFT` are proposals, not implementation authorization — if a decision is missing, record the gap, don't invent it.

## Non-negotiable architectural constraints

- Modular monolith, Clean Architecture, Ports and Adapters. The domain layer must not depend on FastAPI, SQLAlchemy, RabbitMQ, Redis, OpenSearch, Wazuh, Ollama, or n8n.
- Tenant identity comes from the authenticated security context, never from a request body.
- Isolation is enforced at every layer: services, repositories, PostgreSQL RLS, OpenSearch, Redis, messaging, and audit.
- PostgreSQL is the system of record/control; OpenSearch holds high-volume telemetry; Redis is not a system of record.
- React never talks directly to infrastructure services (DB, OpenSearch, Wazuh, Ollama, n8n) — only through the API.
- Long-running work is async, and preserves tenant, correlation ID, and idempotency.
- AI output is untrusted data: strict schema + deterministic validation required. AI never authorizes or executes actions. Auto-response is off by default.
- Every mutating or security-relevant operation produces an audit record.
- All UI text goes through i18n keys (Spanish + English).
- Ollama is configured by URL, never a hardcoded model tag (current family: Gemma).

## Change protocol (from AGENTS.md)

Before implementing: state objective, acceptance criteria, governing docs, affected files, domain/data/API/event impact, security, multitenancy, audit, tests, rollback.

After implementing: report files changed, decisions, migrations/contracts, commands actually run, real results, tests, isolation/security controls, docs, limitations, next chronological task. Never claim a test passed without having run it.

## Commands

Local stack (Docker, profile-based via `COMPOSE_PROFILES` in `.env`):

```bash
make up          # docker compose --profile core up -d --build
make down
make logs
make migrate     # alembic upgrade head, inside backend container
make bootstrap TENANT="Demo" EMAIL="admin@example.test" PASSWORD="..."
```

App: `http://localhost:8080`. API: `/api/v1/health`, `/api/v1/ready`, `/api/v1/version`, OpenAPI at `/api/docs` (non-production only).

Backend (`backend/`, Python 3.12, run inside the container or a local venv with `pip install -e .[dev]`):

```bash
ruff check .              # lint
ruff format --check .     # format check
mypy                      # strict mode
pytest                    # all tests
pytest tests/unit/test_x.py::test_name   # single test
pytest tests/security     # isolation/security tests only
```

Frontend (`frontend/`, npm):

```bash
npm run lint          # eslint --max-warnings 0
npm run format:check  # prettier --check
npm run typecheck     # tsc -b
npm test              # vitest run
npx vitest run src/SomeFile.test.tsx   # single test file
```

Combined pre-PR check: `make check` (runs `backend-check` + `frontend-check`, i.e. lint+format+typecheck+tests for both sides).

## Architecture

**Backend** (`backend/src/cyrvanta/`) is a modular monolith. Each module under `modules/` (`identity`, `incident`, `claims`, `correlation`, `decision`, `directory`, `governed_memory`, `ai_analysis`, `integrations`, `operations`, `platform`, `playbooks`, `risk`, `threat_knowledge`) follows the same internal layering:

- `domain/` — entities and invariants, framework-free.
- `application/` — services, schemas, use-case orchestration (e.g. `claims/application/correlation.py`, `service.py`).
- `infrastructure/` — SQLAlchemy models and adapters to external systems.
- `presentation/` — FastAPI routers.

`shared/` holds cross-module `domain/`, `application/`, and `infrastructure/` building blocks (base entities, tenant context, common dependencies). Top-level entrypoints in `backend/src/cyrvanta/`: `main.py` (API), `worker.py` (async job processing), `scheduler.py`, plus one-off operational scripts (`bootstrap_admin.py`, `bootstrap_directory_demo.py`, `import_attack.py`, `sync_wazuh_findings.py`, `traceability_probe.py`). DB schema changes go through Alembic (`backend/alembic/`).

**Frontend** (`frontend/src/`) is a flat React 18 + TypeScript app (Vite, no nested `pages/`/`components/` split yet) — top-level page components (`PlaybookLibraryPage.tsx`, `GovernedMemoryPage.tsx`, `VerifiedIntegrationsPage.tsx`, `ApiKeysPage.tsx`, etc.), `AuthContext.tsx` for auth state, `api.ts` for backend calls, `i18n.ts` for es/en localization (react-i18next), routed from `App.tsx`. Data fetching via `@tanstack/react-query`, forms via `react-hook-form` + `zod`.

**Infrastructure topology** (`docker-compose.yml`, profile-gated): `core` profile — `postgres`, `redis`, `rabbitmq`, `backend`, `worker`, `scheduler`, `frontend`, `reverse-proxy`. `security`/`live-demo` profiles add `opensearch`, `opensearch-dashboards`, `wazuh-manager`, `ldap`. `automation`/`live-demo` adds the n8n-based playbook engine. The browser only ever reaches the `reverse-proxy`; every other service is internal to the `cyrvanta_net` Docker network. Ollama runs on the host (`http://host.docker.internal:11434` in dev), never bundled as a container dependency, and is accessed through an `AIProvider` port so the inference location can change without touching the API.

Further reading: `docs/ROADMAP.md`, `docs/IMPLEMENTATION_BACKLOG.md`, `docs/domain/` (approved conceptual base), `docs/adr/` (architectural decisions).
