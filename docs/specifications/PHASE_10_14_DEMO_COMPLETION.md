# Phases 10–14 — Demo completion contract

Status: approved for implementation by the instruction to finish the complete demo before
human testing. This contract deliberately avoids production-final APIs and schemas.

## Scope

Complete a safe, on-premise demonstration path for OpenSearch/Wazuh intake, MITRE
enrichment, Ollama analysis, deterministic risk, n8n automation, reporting, platform
health, and automated acceptance. External systems are replaceable ports.

## Adapter contracts

- `TelemetrySearchPort`: bounded health and evidence search. The adapter injects the
  authenticated tenant identifier, allowlists index patterns, caps result count, and
  never accepts raw user DSL.
- `AlertSourcePort`: reads Wazuh-compatible alert documents and maps them to the existing
  canonical alert shape. Source payloads remain untrusted.
- `ThreatKnowledgePort`: returns catalog entries by stable ATT&CK external identifier.
- `AIProviderPort`: health and structured incident analysis. The Ollama URL/model are
  configuration. Evidence is delimited, minimized, and never interpreted as instructions.
- `AutomationPort`: submits only configured workflow identifiers with an idempotency key
  and authenticated callback secret.
- `ReportRendererPort`: produces a bounded, tenant-scoped incident report from persisted
  system-of-record data.

## Demo operating modes

Every external adapter supports explicit `disabled`, `simulated`, or `live` mode.
Development defaults to `simulated`; production defaults must be `disabled` unless
explicitly configured. Simulation is visibly labelled and cannot be mistaken for live
telemetry or a successful real integration.

## Persisted demo records

The implementation may add provisional, versioned records for:

- integration health observations;
- ATT&CK catalog subset and incident mappings;
- structured analysis results and deterministic risk;
- allowlisted playbooks, approvals, and execution status;
- generated report metadata.

All tenant-owned records require `tenant_id`, PostgreSQL RLS, optimistic concurrency where
mutable, and audit events. No raw high-volume telemetry is copied into PostgreSQL.

## AI result

The provider result is parsed against a strict schema: bilingual summary fields, confidence,
evidence references, proposed ATT&CK technique identifiers, and recommendations. Technique
identifiers not present in the local catalog are rejected. Deterministic risk is computed
outside the model from severity, confidence, and bounded evidence factors. AI never
authorizes or executes actions.

## Automation

The demo playbook is recommendation-only by default. Execution requires the
`response.execute` permission, an enabled allowlisted workflow, an explicit approval record,
an idempotency key, and no kill switch. Simulation records the requested and completed
states without invoking commands. Live callbacks require a configured secret.

## Reporting

The initial report is an HTML download suitable for printing to PDF. It includes tenant,
incident, timeline, simulated/live provenance, ATT&CK mappings, deterministic risk,
analysis provenance, and generation timestamp. It excludes secrets and raw telemetry.

## Acceptance

- Static checks, unit tests, migration/RLS checks, frontend tests/build, and Compose health pass.
- Demo bootstrap and scenario generation are idempotent.
- The full-access demo user can view every demo module and exercise safe lifecycle actions.
- Unauthenticated access fails; cross-tenant access and stale versions fail.
- External outages degrade explicitly without false success.
- No human test begins until the automated acceptance script reports all mandatory checks.

