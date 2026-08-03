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
- Contrato aprobado e implementado localmente de Etapa 7:
  `docs/specifications/PHASE_21_N8N_WORKFLOWS_EXECUTION.md`.
- Contrato aprobado con implementación local base de Etapa 8:
  `docs/specifications/PHASE_22_GOVERNED_FEEDBACK_MEMORY.md`.
- Contrato aprobado con implementación local base de evolución de Etapa 7 para
  incorporar el motor nativo y conservar n8n como adaptador opcional:
  `docs/specifications/PHASE_21A_CYRVANTA_PLAYBOOK_ENGINE.md`.
- Contrato aprobado con implementación local base de pulso operativo real y UI
  responsive:
  `docs/specifications/PHASE_23_OPERATIONAL_PULSE_RESPONSIVE_UI.md`.

Las decisiones D-001 a D-012 están aprobadas. Las Etapas estratégicas 1 a 6
están implementadas y validadas. La correlación determinista multi-fuente de
Etapa 4 conserva el paquete aprobado de 18 decisiones.
Retención y polling periódico Wazuh conservan puertas operativas independientes.
La Etapa 5 está implementada y validada conforme al ADR 0013. La Etapa 6 está
implementada y validada conforme al ADR 0014.
La Etapa 7 está implementada y validada localmente conforme al ADR 0015:
workflow sintético, claim, callback, retry y outcomes append-only atravesaron
E2E real. `N8N_API_KEY` está en el secret store local; la API pública confirmó
los cinco digests exactos y los estados esperados sin exponer la clave: sólo
`simulate-user-block` activo y los workflows con credenciales pendientes o
legados inactivos. El modo `live` continúa sujeto a una aprobación operativa
separada.
La Etapa 8 tiene implementación local base según el ADR 0016 aceptado: ocho
tablas
append-only/RLS, API tenant-scoped, separación autor/revisor/activador, scheduler
de expiración, kill switch desactivado por defecto y UI bilingüe. Ruff, mypy,
108 pruebas backend, 10 pruebas frontend, build, rollback vacío y pruebas SQL
transaccionales de RLS/separación fueron satisfactorias. El cierre integral
permanece pendiente de un E2E API multi-actor con evidencia real aprobada y de
snapshots métricos sobre una muestra operativa; la influencia sigue en
`MEMORY_INFLUENCE_ENABLED=false`.

La evolución Fase 21-A, su contrato físico y los ADR 0017/0018 están aprobados.
Migración 0020, puertos, runner, registry simulado, API, biblioteca bilingüe,
binding híbrido y cancelación segura tienen implementación local validada. Recovery tras crash, DLQ, `UNKNOWN` y outcome tardío tienen evidencia E2E con
fallos inyectados. El cierre integral conserva pendiente la paridad concurrente
sin doble efecto y el GATE de identidad de plataforma para el ciclo operativo
write-only de la API key externa de n8n. La Fase 23 ya consume una
ventana tenant-scoped real de 24 horas y no inventa cifras; falta conservar la
evidencia visual a 320 px, 4K y zoom 200 % por indisponibilidad del conector del
navegador. La evidencia ejecutada está en
`docs/evidence/PHASE_21A_23_VALIDATION_2026-08-01.md`. `LIVE` y el retiro de n8n
requieren aprobaciones operativas separadas.

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
