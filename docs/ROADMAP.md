# Roadmap de Cyrvanta

**Estado:** DRAFT — sujeto a aprobación humana.

## Diferenciadores estratégicos

- Auditoría: `docs/audits/STRATEGIC_DIFFERENTIATORS_GAP_ANALYSIS.md`.
- Plan: `docs/roadmaps/STRATEGIC_DIFFERENTIATORS_IMPLEMENTATION_PLAN.md`.
- Contrato aprobado e implementado de Etapa 1:
  `docs/specifications/PHASE_15_EVENT_DELIVERY_TRACEABILITY.md`.
- Contrato aprobado e implementado de Etapa 2:
  `docs/specifications/PHASE_16_CANONICAL_SECURITY_MODEL_PROVENANCE.md`.
- Contrato aprobado e implementado de Etapa 3:
  `docs/specifications/PHASE_17_CLAIM_LEDGER.md`.
- Contrato aprobado e implementado de Etapa 4:
  `docs/specifications/PHASE_18_DETERMINISTIC_MULTI_SOURCE_CORRELATION.md`.
- Contrato aprobado e implementado de Etapa 5:
  `docs/specifications/PHASE_19_MITRE_RISK_EXPLAINABILITY.md`.
- Contrato aprobado e implementado de Etapa 6:
  `docs/specifications/PHASE_20_SAFE_DECISION_APPROVAL.md`.
- Propuesta de contrato de Etapa 7 pendiente de aprobación:
  `docs/specifications/PHASE_21_N8N_WORKFLOWS_EXECUTION.md`.

Las decisiones D-001 a D-012 están aprobadas. Las Etapas estratégicas 1 a 6
están implementadas y validadas. La correlación determinista multi-fuente de
Etapa 4 conserva el paquete aprobado de 18 decisiones.
Retención y polling periódico Wazuh conservan puertas operativas independientes.
La Etapa 5 está implementada y validada conforme al ADR 0013. La Etapa 6 está
implementada y validada conforme al ADR 0014.
La Etapa 7 está especificada como propuesta; ADR 0015 permanece `Propuesto` y
no autoriza implementación ni modo `live`.

Cada fase requiere aprobación de sus especificaciones y criterios antes de
autorizar contratos o implementación de la siguiente.

| Fase | Resultado | Puerta de salida |
|---|---|---|
| 0 | Gobernanza, trazabilidad, ADR y backlog | Documentos coherentes y revisados |
| 1 | Dominio conceptual, contextos, incidentes y autorización | Aprobación humana del lenguaje e invariantes |
| 2 | Modelo lógico/físico PostgreSQL, RLS, retención y migraciones | Revisión de datos y threat model |
| 3 | OpenAPI, eventos, IA y contratos de adaptadores | Contratos versionados aprobados |
| 4 | Bootstrap backend/frontend/Compose/CI | Stack base arranca y pasa checks |
| 5 | Tenants, identidad local, RBAC, RLS y auditoría | Pruebas negativas cross-tenant |
| 6 | LDAP/AD | Contratos y pruebas con directorio de laboratorio |
| 7 | Integraciones y adaptador OpenSearch | Búsqueda acotada y tenant-safe |
| 8 | Adaptador Wazuh | Fixtures y contract tests |
| 9 | Gestión de incidentes | Ciclo completo auditado |
| 10 | Correlación | Explicación y evaluación reproducible |
| 11 | MITRE ATT&CK | Catálogo versionado y mappings históricos |
| 12 | `AIProvider`, Ollama y Gemma 4 | Schemas, redacción y pruebas de inyección |
| 13 | Riesgo y recomendaciones | Resultado determinístico explicable |
| 14 | Playbooks y n8n | Aprobación, idempotencia y kill switches |
| 15 | Aplicación React bilingüe | Accesibilidad y autorización real en backend |
| 16 | Reporting | Métricas definidas y verificables |
| 17 | Hardening y observabilidad | Scans, backup/restore y runbooks |
| 18 | Demo on-premise | Flujo sintético reproducible y no destructivo |

## Decisiones previas a Fase 2

- Aprobar glosario, límites de tenant y pertenencia de usuarios.
- Aprobar ciclo de incidente, evidencia, auditoría y retención.
- Obtener y versionar la fuente oficial de requisitos AGESIC.
- Resolver autenticación, vinculación local/LDAP y administración de plataforma.
- Aprobar volúmenes, RPO/RTO y clasificación de datos.
