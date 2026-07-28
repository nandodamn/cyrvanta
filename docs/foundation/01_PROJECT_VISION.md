# 01 — Project Vision

## 1. Product identity

**Working product name:** Cyrvanta  
**Category:** AI-assisted Security Operations, incident intelligence and response orchestration  
**Product form:** Enterprise web platform deployable on-premise, in a private cloud, or in a controlled hybrid environment  
**Primary users:** SOC analysts, incident responders, SOC managers, tenant administrators, security engineers and auditors

The working name is provisional until trademark, corporate-name and domain-name clearance is completed in target jurisdictions.

## 2. Vision

Cyrvanta transforms fragmented security alerts into explainable, prioritized and actionable incidents while preserving organizational control over data, infrastructure, models and automated responses.

The platform must reduce analyst overload by correlating telemetry, enriching findings with MITRE ATT&CK, producing bilingual natural-language explanations, recommending playbooks and—when expressly configured—executing approved response actions.

## 3. Problem statement

Security operations teams face:

- Excessive alert volume and duplicated signals.
- Fragmented telemetry across SIEM, EDR, NDR, firewalls, identity systems and applications.
- Slow manual correlation and investigation.
- Inconsistent incident classification and prioritization.
- Knowledge concentrated in a small number of senior analysts.
- Limited explainability in AI-based products.
- Data-sovereignty restrictions that prevent sending sensitive telemetry to public AI services.
- High licensing and ingestion costs in proprietary platforms.
- Difficulty integrating response workflows without vendor lock-in.

## 4. Product goals

Cyrvanta shall:

1. Ingest or query alerts and telemetry from Wazuh/OpenSearch first, while supporting future adapters.
2. Correlate related alerts into incidents using deterministic rules, statistical techniques and LLM-assisted reasoning.
3. Map observed behavior to MITRE ATT&CK tactics, techniques and sub-techniques.
4. Assign explainable risk and confidence scores.
5. Generate concise Spanish and English incident summaries.
6. Recommend response actions and playbooks.
7. Support both:
   - **Human-in-the-loop mode:** actions require analyst approval.
   - **Automatic mode:** narrowly scoped, policy-approved actions may execute automatically.
8. Maintain strict tenant isolation.
9. Support local authentication and LDAP/Active Directory.
10. Provide complete auditability for human, system and AI actions.
11. Operate without sending security data outside the controlled environment.
12. remain modular so Wazuh, OpenSearch, Ollama or the automation engine can be replaced.

## 5. Non-goals for the first commercial release

Cyrvanta is not initially intended to:

- Replace every SIEM, EDR, NDR or SOAR product.
- Perform endpoint prevention without an external enforcement component.
- Train a foundation model from scratch.
- Provide unrestricted autonomous cyber-response.
- Store all raw telemetry in PostgreSQL.
- Depend on one security vendor.
- Use AI output as authoritative evidence without deterministic validation.
- Provide offensive-security automation.

## 6. Primary personas

### 6.1 Tier 1 SOC analyst

Needs fast triage, clear explanations, related alerts, affected assets, recommended next steps and safe escalation.

### 6.2 Tier 2/3 analyst

Needs raw evidence, correlation rationale, MITRE mapping, query history, enrichment sources, timelines and control over playbooks.

### 6.3 Incident response lead

Needs incident ownership, task coordination, containment status, evidence preservation, decisions and audit history.

### 6.4 SOC manager

Needs operational metrics, analyst workload, MTTD, MTTR, automation effectiveness, false-positive trends and tenant-level reporting.

### 6.5 Tenant administrator

Needs users, roles, integrations, data-retention policies, language, automation policy, LDAP settings and secrets management.

### 6.6 Platform administrator

Needs infrastructure health, tenant provisioning, global policy, version management, backups, observability and licensing controls.

### 6.7 Auditor

Needs immutable records of access, configuration changes, AI analyses, approvals, actions, evidence and exports.

## 7. Core use cases

### UC-01 Alert ingestion and normalization

Receive alert metadata from Wazuh/OpenSearch, normalize it into a canonical alert model and preserve source references.

### UC-02 Incident correlation

Group related alerts by tenant, asset, identity, indicators, temporal proximity, tactic sequence and behavioral similarity.

### UC-03 AI-assisted triage

Create an evidence-bounded analysis that includes summary, hypothesis, confidence, risk, missing evidence and recommended investigation steps.

### UC-04 MITRE ATT&CK mapping

Map evidence to tactics, techniques and sub-techniques; show the evidence supporting each mapping and the mapping confidence.

### UC-05 Response recommendation

Select or propose a playbook based on incident type, tenant policy, affected assets, severity and confidence.

### UC-06 Human approval

Present action impact, target, rollback information and evidence to an authorized analyst before execution.

### UC-07 Controlled automatic response

Execute only preapproved actions that satisfy tenant policy, risk thresholds, confidence thresholds, maintenance windows and target restrictions.

### UC-08 Investigation assistant

Allow analysts to ask bounded questions about an incident. The assistant may use authorized incident data and ATT&CK content but may not access another tenant.

### UC-09 Reporting

Generate operational, executive and audit reports in Spanish or English.

### UC-10 Administration

Configure tenants, users, LDAP, integrations, retention, scoring, playbooks, notification channels and AI policy.

## 8. Product principles

### 8.1 Evidence before explanation

Every material AI conclusion must reference the evidence used.

### 8.2 Deterministic controls around probabilistic models

The LLM may interpret and summarize; authorization, tenant isolation, action execution and policy enforcement remain deterministic.

### 8.3 Human control by default

Automatic response is disabled by default and enabled per tenant, action type and target scope.

### 8.4 Open integration

External systems connect through versioned adapters and stable contracts.

### 8.5 Replaceable AI provider

Business logic must not depend directly on an Ollama-specific SDK or Gemma-specific output format.

### 8.6 Privacy and sovereignty

Security data remains within the selected deployment boundary unless an administrator explicitly configures an external provider.

### 8.7 Bilingual by design

User-facing text must not be hardcoded. Spanish and English are first-class locales.

## 9. Success metrics

The system should measure:

- Mean time to detect and acknowledge.
- Mean time to investigate and respond.
- Percentage of alerts correlated into incidents.
- Duplicate-alert reduction.
- Analyst acceptance rate of AI recommendations.
- False-positive rate and reopened incidents.
- Percentage of actions executed automatically, approved or rejected.
- Response-action failure and rollback rate.
- AI response latency and structured-output validation rate.
- Tenant-specific search and ingestion latency.
- Availability, error budget and recovery time.

## 10. Release strategy

### Demo release

A controlled single-laptop demonstration with synthetic or lab telemetry, one or more logical tenants, Wazuh/OpenSearch integration, Gemma 4 analysis, MITRE mapping, incident dashboard and one safe playbook.

### MVP

Deployable on a customer-controlled server, multitenant, local + LDAP authentication, complete incident workflow, audit log, configurable response approval and documented backup/restore.

### Enterprise release

High availability, external secret manager, SSO extensions, scalable workers, complete observability, disaster recovery, signed artifacts, supply-chain controls, stronger policy engine and multiple integration adapters.

## 11. Demo narrative

The reference demonstration shall show:

1. A test endpoint produces several suspicious events.
2. Wazuh detects and indexes alerts.
3. Cyrvanta retrieves and normalizes them.
4. The correlation engine groups them into one incident.
5. Gemma 4 produces an evidence-bounded bilingual analysis.
6. The MITRE engine maps techniques and displays the attack sequence.
7. The risk engine calculates a score with visible factors.
8. The dashboard displays affected entities and recommended actions.
9. The analyst approves a safe containment simulation or ticketing action.
10. The platform records every step in the audit trail.
