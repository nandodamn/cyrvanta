# Backlog de implementación

**Estado:** DRAFT. Los ítems `GATE` bloquean diseño físico o código.

## Diferenciadores estratégicos

- [x] Auditar capacidades contra el flujo real.
- [x] Ordenar implementación por dependencias.
- [x] GATE: aprobar D-001 a D-012 del plan estratégico.
- [x] Especificar envelope, outbox/inbox e idempotencia.
- [x] GATE: aprobar `PHASE_15_EVENT_DELIVERY_TRACEABILITY.md`.
- [x] Implementar Etapa 1.
- [x] Especificar Etapa 2 — modelo canónico y procedencia.
- [x] GATE: aprobar
  `PHASE_16_CANONICAL_SECURITY_MODEL_PROVENANCE.md`.
- [x] Fijar límites físicos, calidad, severidad y redacción iniciales con
  fixtures y datos Wazuh reales; retención continúa como GATE de gobierno.
- [x] Implementar Etapa 2 después de aprobar su contrato y pendientes
  físicos.
- [ ] GATE: aprobar retención por tenant y mínimos de plataforma.
- [ ] GATE: aprobar frecuencia, cursor durable y activación scheduler Wazuh.
- [x] Especificar Etapa 3 — ledger de claims.
- [x] GATE: aprobar `PHASE_17_CLAIM_LEDGER.md`.
- [x] Resolver límites, permisos humanos, retención y schema IA de Etapa 3.
- [x] Implementar Etapa 3 solo después de aprobar contrato y pendientes
  materiales.
- [x] Especificar Etapa 4 — correlación determinista multi-fuente.
- [x] Preparar paquete recomendado para resolver las decisiones materiales de
  Etapa 4 sin autorizar implementación.
- [x] GATE: aprobar
  `PHASE_18_DETERMINISTIC_MULTI_SOURCE_CORRELATION.md`.
- [x] Resolver ventanas, factores, límites, política de incidentes y
  persistencia física de Etapa 4.
- [x] Implementar Etapa 4 solo después de aprobar contrato y pendientes
  materiales.
- [x] Especificar Etapa 5 — MITRE ATT&CK, riesgo y explicabilidad.
- [x] Preparar paquete recomendado para resolver las decisiones materiales de
  Etapa 5 sin autorizar implementación.
- [x] GATE: aprobar
  `PHASE_19_MITRE_RISK_EXPLAINABILITY.md`.
- [x] Resolver catálogo baseline, mappings, factores, límites, permisos y
  persistencia física de Etapa 5.
- [x] Implementar Etapa 5 conforme al contrato aprobado y ADR 0013.
- [x] Registrar requisitos humanos de workflows n8n como código para Etapa 7.
- [x] GATE: aprobar modelo de decisión y doble aprobación de Etapa 6 antes de
  `request-dual-approval`.
- [x] Especificar Etapa 6 en
  `docs/specifications/PHASE_20_SAFE_DECISION_APPROVAL.md`.
- [x] Implementar y validar Etapa 6 conforme al ADR 0014.
- [x] Especificar Etapa 7 incorporando
  `N8N_WORKFLOWS_AS_CODE_REQUIREMENTS.md`.
- [x] GATE: aprobar
  `PHASE_21_N8N_WORKFLOWS_EXECUTION.md` y aceptar ADR 0015.
- [x] Implementar workflows n8n, scripts y callbacks únicamente después de
  aprobar Etapas 5, 6 y 7.
  - [x] Validar E2E sintético, claim previo al efecto, callback exacto y retry
    con outcomes append-only.
  - [x] Incorporar `N8N_API_KEY` al secret store local y validar
    diff/reconciliación mediante la API pública de n8n.
- [x] Preparar borrador de Etapa 8 en
  `PHASE_22_GOVERNED_FEEDBACK_MEMORY.md`.
- [x] GATE: aprobar decisiones materiales, especificación y ADR de Etapa 8.
- [x] Implementar la base local de Etapa 8 después de superar su GATE.
- [ ] Completar E2E API multi-actor y snapshots métricos con evidencia real.
- [x] Preparar propuesta Fase 21-A para `Cyrvanta Playbook Engine` nativo y n8n
  opcional.
- [x] GATE: aprobar las 20 decisiones de
  `PHASE_21A_CYRVANTA_PLAYBOOK_ENGINE.md` y aceptar ADR 0017.
- [ ] Cerrar integralmente el motor nativo después de superar su GATE:
  - [x] Publicar schema portable v1 y fixtures.
  - [x] GATE: ratificar `PHASE_21A_IMPLEMENTATION_CONTRACT.md` antes de crear
    migración, API, eventos o puertos nativos.
  - [x] Ampliar `engine_type` mediante la migración reversible `0020`.
  - [x] Implementar puerto, runner, action registry y conectores simulados.
  - [x] Implementar API, permisos, auditoría, eventos y biblioteca UI bilingüe.
  - [x] Implementar cancelación nativa segura con `If-Match`, auditoría y
    preservación append-only de outcomes tardíos.
  - [ ] GATE: definir identidad de plataforma y alcance global antes de permitir
    reemplazo, prueba o rotación de la API key externa de n8n desde UI.
  - [x] Validar recovery, retry seguro, DLQ y `UNKNOWN` con fallos inyectados.
  - [ ] Validar paridad concurrente sin doble efecto; selección exclusiva por
    binding, RLS real e idempotencia durable ya están verificadas.
  - [ ] Evaluar el retiro de n8n sólo mediante aprobación operativa separada.
- [x] GATE: aprobar `PHASE_23_OPERATIONAL_PULSE_RESPONSIVE_UI.md`.
- [ ] Cerrar Fase 23:
  - [x] Implementar endpoint tenant-scoped de actividad móvil real de 24 horas.
  - [x] Sustituir métricas estáticas por estados loading/error/empty y datos
    reales con etiqueta de fuente.
  - [x] Implementar layout responsive y pruebas de componentes.
  - [ ] Validar visualmente 320 px, escritorio/4K y zoom 200 % cuando el
    conector del navegador esté operativo.

## Gobernanza

- [ ] GATE: revisión humana de todos los documentos de Fase 0 y Fase 1.
- [ ] GATE: incorporar la consulta/requisitos oficiales de AGESIC con versión y
  trazabilidad.
- [x] Verificar o inicializar Git y configurar el remoto autorizado.
- [ ] Aprobar licencia, política de contribución y responsables.
- [ ] Fijar versiones de Python, Node, PostgreSQL, OpenSearch y demás imágenes.
- [ ] Decidir herramientas exactas de paquetes, tipado, proxy y secretos.
- [ ] Actualizar React Router cuando exista una versión sin los advisories
  documentados en ADR 0006 y repetir pruebas de navegación/redirect.

## Dominio

- [ ] GATE: aprobar glosario y terminología bilingüe.
- [x] GATE: usuarios multi-tenant mediante membresía explícita (D-001);
  contrato físico pendiente.
- [ ] GATE: aprobar ciclo de vida de incidentes y reglas de concurrencia.
- [ ] GATE: aprobar identidad local/LDAP y resolución de colisiones.
- [ ] GATE: aprobar modelo RBAC y alcance del administrador de plataforma.
- [ ] GATE: aprobar evidencia, cadena de custodia, auditoría y retención.
- [x] Definir riesgo, confianza y versionado mediante aprobación de
  `PHASE_19_MITRE_RISK_EXPLAINABILITY.md`.
- [x] Definir modos de respuesta y clasificación de impacto.

## Datos y contratos — no iniciar antes de los GATE

- [ ] Crear modelo lógico y ERD sin asumir nombres físicos prematuramente.
- [ ] Diseñar RLS y pruebas negativas.
- [ ] Diseñar retención, borrado y backup/restore.
- [ ] Aprobar catálogo físico y primera migración Alembic.
- [ ] Publicar OpenAPI 3.1 y RFC 7807.
- [ ] Publicar envelopes y eventos RabbitMQ.
- [ ] Publicar schemas de IA y contratos Wazuh/OpenSearch/n8n.

## Implementación

- [ ] Bootstrap reproducible de backend, frontend, Compose y CI.
- [ ] Implementar fases 5–18 según `docs/ROADMAP.md`.
- [ ] Mantener pruebas unitarias, componentes, contratos, API, RLS,
  cross-tenant, seguridad, frontend y E2E en cada incremento.
