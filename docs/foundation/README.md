# Cyrvanta — Foundation Documentation

**Product type:** Multitenant AI-assisted Security Operations Platform  
**Working name:** Cyrvanta  
**Document set version:** 0.1.0  
**Status:** Architecture foundation  
**Primary deployment target:** On-premise / private infrastructure  
**Development target:** Windows 11 laptop, Docker Desktop + WSL2, Ollama on host  
**Primary local model:** Gemma 4 via Ollama  
**Languages:** Spanish and English

## Purpose

This directory contains the mandatory foundation documents that govern every design and implementation decision in Cyrvanta.

No AI coding agent or human developer may start implementation before reading these documents in this order:

1. `01_PROJECT_VISION.md`
2. `02_SYSTEM_ARCHITECTURE.md`
3. `03_DEVELOPMENT_RULES.md`
4. `04_TECHNOLOGY_STACK.md`
5. `AI_DEVELOPER_MASTER_PROMPT.md`

## Rule of precedence

When documents conflict, apply this precedence:

1. Security and tenant isolation requirements.
2. `03_DEVELOPMENT_RULES.md`.
3. `02_SYSTEM_ARCHITECTURE.md`.
4. Module-specific specifications created later.
5. Implementation convenience.

The agent must stop and report the conflict instead of silently choosing a different architecture.

## Current architectural decisions

- Multitenant from the first database migration.
- Local and LDAP/Active Directory authentication.
- Bilingual user interface and API-ready localization.
- Human-approved and configurable automatic response modes.
- Wazuh and OpenSearch are replaceable integrations, not the product core.
- PostgreSQL is the system of record for business and control-plane data.
- OpenSearch stores and searches high-volume security telemetry.
- Ollama runs on the Windows host during laptop development.
- Docker containers reach Ollama through `host.docker.internal:11434`.
- Gemma 4 is accessed through an internal AI provider abstraction.
- All security-relevant decisions are auditable.
- AI output is advisory by default and never treated as trusted executable input.

## Next documentation wave

The next deliverables must be generated in this order:

1. Domain model and bounded contexts.
2. PostgreSQL logical and physical data model.
3. REST API and event contracts.
4. Authentication, authorization and tenant isolation.
5. Wazuh/OpenSearch integration.
6. AI engine and MITRE ATT&CK enrichment.
7. Playbooks and response automation.
8. React design system and dashboard UX.
9. Testing and security verification.
10. Docker, deployment, observability and CI/CD.
