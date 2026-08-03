# Fase 22 — Feedback y memoria gobernada

**Etapa estratégica:** 8  
**Estado:** APROBADO PARA IMPLEMENTACIÓN — base local validada  
**Fecha:** 2026-08-01  
**Implementación autorizada formalmente:** sí — ratificación humana explícita del 2026-08-01

## 1. Objetivo

Definir cómo Cyrvanta puede conservar feedback humano y resultados
operacionales útiles sin convertirlos en aprendizaje autónomo, excepciones
implícitas o decisiones no auditadas.

La memoria solo puede influir cuando tiene procedencia verificable, revisión
humana, vigencia explícita y una explicación visible de su efecto. PostgreSQL
continúa como sistema de registro y la IA nunca aprueba, activa ni ejecuta una
memoria.

## 2. Alcance aprobado

Incluye:

- taxonomía de feedback y outcomes;
- feedback humano append-oriented;
- candidatos de memoria derivados de evidencia ya persistida;
- revisión, aprobación, corrección, expiración y desactivación;
- influencia observacional o recomendada, nunca autorización;
- métricas con ventana, tamaño de muestra y versión de definición;
- procedencia desde incidente, finding, claim, decisión, ejecución o resultado;
- API y UI bilingüe para registrar, revisar y explicar;
- permisos, separación de funciones, RLS, auditoría y rollback;
- eventos durables e idempotencia mediante la infraestructura de Fase 15.

No incluye:

- reentrenamiento automático de modelos;
- modificación automática de políticas, riesgo o autorizaciones;
- aprendizaje desde fixtures, demos o datos sintéticos como si fueran reales;
- perfiles personales o inferencias sensibles sobre usuarios;
- excepciones automáticas a controles de seguridad;
- memoria compartida entre tenants;
- embeddings o vector stores como fuente de verdad;
- borrado silencioso de feedback o decisiones históricas;
- influencia `live` sin una aprobación operativa posterior.

## 3. Documentos rectores

- `docs/foundation/*`;
- `docs/audits/STRATEGIC_DIFFERENTIATORS_GAP_ANALYSIS.md`;
- `docs/roadmaps/STRATEGIC_DIFFERENTIATORS_IMPLEMENTATION_PLAN.md`;
- `docs/specifications/PHASE_15_EVENT_DELIVERY_TRACEABILITY.md`;
- `docs/specifications/PHASE_16_CANONICAL_SECURITY_MODEL_PROVENANCE.md`;
- `docs/specifications/PHASE_17_CLAIM_LEDGER.md`;
- `docs/specifications/PHASE_18_DETERMINISTIC_MULTI_SOURCE_CORRELATION.md`;
- `docs/specifications/PHASE_19_MITRE_RISK_EXPLAINABILITY.md`;
- `docs/specifications/PHASE_20_SAFE_DECISION_APPROVAL.md`;
- `docs/specifications/PHASE_21_N8N_WORKFLOWS_EXECUTION.md`;
- ADR 0010 a ADR 0015.

## 4. Estado actual y brecha

Cyrvanta ya conserva procedencia canónica, claims append-only, correlación,
riesgo versionado, decisiones, autorizaciones, ejecuciones y resultados. No
existe todavía dominio, persistencia, API, eventos, permisos ni UI de memoria.

Brechas materiales:

1. No hay taxonomía aprobada de verdadero/falso positivo ni outcome operativo.
2. No existe diferencia contractual entre feedback, métrica y memoria.
3. No están definidas privacidad, retención, vigencia ni corrección.
4. No hay quorum ni separación de autor/revisor para memoria influyente.
5. No se define cómo explicar una influencia sin alterar la evidencia original.
6. No hay protección contra aprendizaje desde fixtures o muestras pequeñas.
7. No existe rollback seguro de una memoria ya utilizada.

## 5. Principios no negociables aprobados

1. Feedback, revisiones e historial de estado son append-only.
2. Una corrección agrega un hecho nuevo y no sobrescribe el anterior.
3. Un candidato no influye hasta una aprobación humana vigente.
4. Autor y aprobador son actores distintos para toda memoria influyente.
5. La memoria nunca autoriza ni ejecuta acciones.
6. La memoria no cambia retrospectivamente findings, claims, riesgo o resultados.
7. Toda influencia produce una explicación con IDs y versiones reproducibles.
8. Datos sintéticos pueden probar el flujo, pero no alimentar métricas reales.
9. Métricas sin tamaño de muestra y ventana son inválidas.
10. Todo acceso y efecto se limita por tenant en servicio, repositorio y RLS.

## 6. Conceptos de dominio aprobados

### 6.1 Feedback

Observación humana inmutable sobre un objeto autoritativo existente. Debe
referenciar exactamente un recurso tenant-owned, actor, instante, motivo y
correlation ID.

### 6.2 Outcome normalizado

Clasificación humana del resultado observado. Taxonomía inicial recomendada:

- `TRUE_POSITIVE`;
- `FALSE_POSITIVE`;
- `BENIGN_TRUE_POSITIVE`;
- `INCONCLUSIVE`;
- `ACTION_EFFECTIVE`;
- `ACTION_INEFFECTIVE`;
- `ACTION_PARTIAL`;
- `NOT_ASSESSED`.

La taxonomía debe separar la validez de una detección de la efectividad de una
acción. No se permite inferir una desde la otra.

### 6.3 Candidato de memoria

Propuesta acotada y versionada derivada de uno o más feedbacks, outcomes o
hechos autoritativos. No tiene efecto por sí misma.

### 6.4 Revisión de memoria

Hecho append-only emitido por un revisor humano. Puede recomendar aprobación,
rechazo, corrección o desactivación con motivo redactado.

### 6.5 Versión de memoria aprobada

Snapshot inmutable con alcance, condiciones, evidencia, versión, vigencia y
límites. Una versión posterior supersede; nunca modifica la versión anterior.

### 6.6 Registro de influencia

Explica dónde se consultó una memoria aprobada, si coincidió, qué valor aportó y
qué resultado habría existido sin ella. No puede ocultar la salida base.

### 6.7 Definición de métrica

Contrato versionado para una métrica observacional. Fija población, filtros,
ventana, numerador, denominador, tamaño mínimo y tratamiento de sintéticos.

## 7. Ciclos de vida aprobados

Candidato de memoria:

```text
DRAFT → IN_REVIEW → APPROVED → ACTIVE → EXPIRED
                    ├───────→ REJECTED
                    └───────→ DISABLED
ACTIVE → SUPERSEDED
```

Reglas propuestas:

- `APPROVED` requiere revisor distinto del autor;
- `ACTIVE` requiere vigencia futura y evidencia no sintética suficiente;
- `EXPIRED`, `DISABLED`, `REJECTED` y `SUPERSEDED` no vuelven a `ACTIVE`;
- una corrección crea una nueva versión candidata;
- expiración se materializa por scheduler y emite evento durable;
- desactivación de emergencia requiere motivo y auditoría, no borrado.

## 8. Influencia permitida

Nivel recomendado para la primera implementación: `OBSERVATIONAL_ONLY`.

Una memoria activa puede:

- aparecer como contexto explicado en UI;
- priorizar una recomendación no vinculante;
- aportar un factor versionado dentro de límites aprobados;
- alimentar métricas observacionales.

No puede:

- cerrar, reabrir o reasignar incidentes;
- validar o retractar claims;
- cambiar una autorización;
- saltar aprobación humana;
- habilitar respuesta automática;
- alterar resultados persistidos;
- escribir directamente en módulos propietarios de otros bounded contexts.

Una influencia futura sobre riesgo o decisión requiere una enmienda formal a
las fases propietarias y una nueva aprobación humana.

## 9. Privacidad y retención aprobadas

- Prohibir secretos, credenciales, payload raw y chain-of-thought.
- Evitar texto libre cuando baste una taxonomía y motivo acotado.
- No crear perfiles conductuales personales en la primera versión.
- Conservar referencias a evidencia en lugar de duplicarla.
- Separar retención del feedback, versiones e influencia auditada.
- La expiración de influencia no elimina la evidencia histórica.
- Exportación y eliminación legal requieren un proceso posterior aprobado.

La retención exacta permanece como decisión material abierta; no se codificará
un TTL hasta aprobarla.

## 10. Modelo lógico aprobado

Sin fijar aún nombres físicos, se requieren conceptos persistentes para:

1. feedback inmutable;
2. candidato de memoria;
3. versiones inmutables del candidato;
4. revisiones append-only;
5. historial append-only de activación/expiración/desactivación;
6. registros append-only de influencia;
7. definiciones versionadas de métricas;
8. observaciones o snapshots reproducibles de métricas.

Todas las relaciones tenant-owned requieren UUID, `tenant_id`, FK compuestas,
RLS habilitada y forzada. PostgreSQL es autoritativo; OpenSearch puede recibir
proyecciones no sensibles, nunca gobernar vigencia o aprobación.

## 11. API aprobada

Capacidades mínimas:

- registrar feedback sobre un recurso autorizado;
- listar feedback y su procedencia;
- proponer un candidato de memoria;
- solicitar revisión;
- registrar decisión de revisión;
- activar, desactivar o superseder según permiso;
- consultar versiones activas y explicación de influencia;
- consultar métricas con ventana y tamaño de muestra.

Toda mutación exige `Idempotency-Key`, correlation ID, actor autenticado y
auditoría. Tenant nunca se acepta desde el body como autoridad.

## 12. Eventos aprobados

- `security.feedback.recorded`;
- `security.memory_candidate.proposed`;
- `security.memory_candidate.review_requested`;
- `security.memory_candidate.reviewed`;
- `security.memory_version.activated`;
- `security.memory_version.expired`;
- `security.memory_version.disabled`;
- `security.memory.influence_recorded`.

Los payloads exactos se fijan en la sección 25.

## 13. Permisos aprobados

- `feedback.read`;
- `feedback.create`;
- `memory.read`;
- `memory.propose`;
- `memory.review`;
- `memory.activate`;
- `memory.disable`;
- `memory.metrics.read`.

Recomendación: `memory.propose` y `memory.review` deben estar separados;
`memory.activate` no puede ser ejercido por el autor de la versión.

## 14. Seguridad y multitenancy

- RLS real y forzada con rol de aplicación.
- Pruebas cross-tenant para cada lectura y mutación.
- Referencias polimórficas resueltas mediante puertos allowlisted, no nombres de
  tabla aportados por el cliente.
- Motivos y etiquetas con límites estrictos y redacción.
- Listados paginados y acotados.
- Protección contra IDOR por recurso fuente, candidato, versión e influencia.
- Ninguna memoria global en la primera versión.
- Fail closed si la versión está expirada, desactivada o no puede verificarse.

## 15. IA y autonomía

La IA puede sugerir un candidato estructurado con schema estricto. Esa salida:

- se marca como `AI_SUGGESTED`;
- no cuenta como aprobación ni evidencia independiente;
- requiere validación determinística y revisión humana;
- conserva modelo/configuración y referencias, nunca prompts sensibles;
- no modifica políticas, memoria activa ni decisiones.

No existe aprendizaje autónomo ni fine-tuning dentro de esta fase.

## 16. UI e i18n

La UI propuesta debe mostrar en español e inglés:

- fuente, autor, estado, vigencia y versión;
- evidencia que sustenta el candidato;
- historial completo de revisiones y cambios de estado;
- indicador visible de dato sintético;
- explicación “resultado base / influencia / resultado presentado”;
- tamaño de muestra y ventana de cada métrica;
- acciones permitidas según rol, con confirmación para desactivar.

Nunca se mostrará una memoria expirada como recomendación vigente.

## 17. Observabilidad y auditoría

Auditar:

- creación de feedback y candidato;
- solicitud y decisión de revisión;
- activación, expiración, supersesión y desactivación;
- consulta o exportación privilegiada;
- cada influencia aplicada o descartada;
- cambios de definición de métricas.

Logs y métricas conservan IDs, versiones, tenant, correlation ID, outcome,
ventana y tamaño de muestra; no duplican comentarios sensibles ni evidencia.

## 18. Pruebas obligatorias

### Dominio

- taxonomía válida e inválida;
- ciclos de vida y transiciones terminales;
- separación autor/revisor/activador;
- expiración y supersesión;
- sintéticos excluidos de influencia real;
- explicación reproducible.

### Datos y seguridad

- append-only real mediante permisos y triggers/constraints aprobados;
- RLS y pruebas cross-tenant reales;
- FK compuestas e IDOR negativo;
- idempotencia concurrente;
- motivos y payloads sobredimensionados rechazados.

### Integración

- outbox/inbox y redelivery sin duplicados;
- scheduler de expiración;
- memoria desactivada deja de influir inmediatamente;
- módulo consumidor caído falla cerrado;
- métricas reproducibles con ventana y muestra conocidas.

### UI

- i18n español/inglés;
- historial y explicación visibles;
- permisos negativos;
- accesibilidad y alternativa textual;
- sintéticos claramente identificados.

## 19. Rollback aprobado

1. Kill switch de influencia separa lectura histórica de uso activo.
2. Desactivar una versión agrega un evento; no elimina historia.
3. Los consumidores deben poder ignorar el puerto de memoria y volver al
   resultado base determinístico.
4. Migraciones son aditivas y su downgrade falla si existe evidencia no
   exportada.
5. Rollback de UI no revierte estados autoritativos.

## 20. Decisiones materiales ratificadas

Ratificadas explícitamente por instrucción humana el 2026-08-01:

1. **Taxonomía:** usar las ocho categorías de la sección 6.2.
2. **Influencia inicial:** `OBSERVATIONAL_ONLY`.
3. **Quorum:** autor distinto de revisor; activador distinto del autor.
4. **Vigencia máxima inicial:** 90 días, renovable mediante nueva revisión.
5. **Muestra mínima:** 20 casos reales antes de proponer una tendencia; mostrar
   igualmente métricas inferiores como “muestra insuficiente”.
6. **Sintéticos:** excluidos de memoria activa y métricas reales.
7. **Privacidad:** sin perfiles personales ni texto libre no acotado.
8. **Retención:** conservar feedback y revisiones durante la retención del
   incidente fuente; conservar auditoría según política corporativa pendiente.
9. **Corrección:** nueva versión; nunca `UPDATE` del snapshot aprobado.
10. **Ámbito:** solo tenant; no memoria global ni entre tenants.
11. **IA:** solo sugerencia estructurada, sin aprobación ni activación.
12. **Consumidores iniciales:** UI y explicación; ningún cambio automático de
    riesgo, decisión o ejecución.

Cambiar cualquiera de estas decisiones puede alterar entidades, permisos,
retención, eventos o límites y requiere una enmienda formal y ADR.

## 21. Criterios de salida de especificación

La fase puede pasar a `APROBADO PARA IMPLEMENTACIÓN` cuando:

1. se aprueban las doce decisiones materiales;
2. se fijan contratos exactos de entidades, tablas, API y eventos;
3. se aprueban permisos y separación de funciones;
4. privacidad y retención tienen responsable y política;
5. se registra un ADR aceptado;
6. existe plan de migración, pruebas RLS y rollback;
7. se confirma que Etapa 7 está operativamente cerrada o se documenta la
   dependencia pendiente sin debilitar el fail-closed.

## 22. Puerta de implementación

GATE superado por ratificación humana explícita el 2026-08-01. La base local
implementada sigue los contratos exactos siguientes; cualquier cambio material
requiere una enmienda y ADR.

## 23. Contrato físico exacto

La migración inicial crea ocho tablas tenant-owned:

1. `feedback_entries`: `id`, `tenant_id`, `resource_type`, `resource_id`,
   `actor_user_id`, `outcome`, `reason`, `is_synthetic`, `idempotency_key`,
   `correlation_id`, `occurred_at`, `created_at`.
2. `memory_candidates`: `id`, `tenant_id`, `kind`, `source_type`,
   `created_by_user_id`, `idempotency_key`, `correlation_id`, `created_at`.
3. `memory_candidate_versions`: `id`, `tenant_id`, `candidate_id`, `version`,
   `title_es`, `title_en`, `statement_es`, `statement_en`, `conditions`,
   `evidence_refs`, `is_synthetic`, `valid_from`, `valid_until`, `created_at`.
4. `memory_reviews`: `id`, `tenant_id`, `version_id`, `reviewer_user_id`,
   `decision`, `reason`, `created_at`.
5. `memory_state_events`: `id`, `tenant_id`, `version_id`, `actor_user_id`,
   `from_status`, `to_status`, `reason`, `occurred_at`, `correlation_id`.
6. `memory_influences`: `id`, `tenant_id`, `version_id`, `consumer_type`,
   `consumer_id`, `matched`, `base_fingerprint`, `presented_fingerprint`,
   `explanation`, `idempotency_key`, `correlation_id`, `occurred_at`.
7. `memory_metric_definitions`: `id`, `tenant_id`, `code`, `version`,
   `definition_sha256`, `window_days`, `minimum_sample_size`, `active`,
   `created_at`.
8. `memory_metric_snapshots`: `id`, `tenant_id`, `definition_id`,
   `window_start`, `window_end`, `sample_size`, `numerator`, `denominator`,
   `value`, `sufficient_sample`, `input_fingerprint`, `created_at`.

Invariantes:

- UUID y `tenant_id` en todas las tablas;
- FK tenant-compuestas y RLS habilitada/forzada;
- unique `(tenant_id, idempotency_key)` donde existe idempotencia;
- unique `(tenant_id, candidate_id, version)` para versiones;
- unique `(tenant_id, version_id, reviewer_user_id)` para revisión;
- unique `(tenant_id, code, version)` y digest SHA-256 para métricas;
- feedback, versiones, revisiones, estados, influencias y snapshots son
  `SELECT, INSERT` para el rol de aplicación, sin `UPDATE` ni `DELETE`;
- `memory_candidates` es identidad estable e inmutable;
- `memory_metric_definitions.active` solo admite update por columna autorizado;
- JSONB debe ser objeto o array según contrato y se valida también en servicio;
- `valid_until` no supera 90 días desde `valid_from`;
- una tendencia requiere al menos 20 feedbacks reales distintos.

## 24. Contrato API exacto

- `POST /api/v1/feedback` — `feedback.create`, `Idempotency-Key` obligatorio.
- `GET /api/v1/feedback` — `feedback.read`, paginado y filtrable por recurso.
- `POST /api/v1/memory-candidates` — `memory.propose`, idempotente.
- `GET /api/v1/memory-candidates` — `memory.read`, paginado.
- `GET /api/v1/memory-candidates/{candidate_id}` — `memory.read`.
- `POST /api/v1/memory-versions/{version_id}/review-request` —
  `memory.propose`.
- `POST /api/v1/memory-versions/{version_id}/reviews` — `memory.review`.
- `POST /api/v1/memory-versions/{version_id}/activate` — `memory.activate`.
- `POST /api/v1/memory-versions/{version_id}/disable` — `memory.disable`.
- `GET /api/v1/memory/active` — `memory.read`; nunca devuelve expiradas.
- `POST /api/v1/memory/context/evaluate` — `memory.read`; registra influencia
  observacional y devuelve base, coincidencias y explicación.
- `GET /api/v1/memory/metrics` — `memory.metrics.read`.

Todos los bodies usan `extra=forbid`, límites explícitos y no aceptan tenant.
Errores de dominio se traducen a 404/409; permiso o tenant no se distinguen de
recurso inexistente cuando hacerlo evitaría IDOR.

## 25. Contrato de eventos exacto

Todos usan `EventEnvelopeV1`, schema version 1 y payloads sin texto sensible:

- `security.feedback.recorded`: feedback ID, resource type/ID, outcome,
  `is_synthetic`;
- `security.memory_candidate.proposed`: candidate ID, version ID, kind,
  source type;
- `security.memory_candidate.review_requested`: candidate/version IDs;
- `security.memory_candidate.reviewed`: version ID, review ID, decision;
- `security.memory_version.activated`: version ID, valid from/until;
- `security.memory_version.expired`: version ID, expiration instant;
- `security.memory_version.disabled`: version ID, stable reason code;
- `security.memory.influence_recorded`: version ID, consumer type/ID, matched,
  base and presented fingerprints.

Redelivery no duplica registros gracias a idempotency keys o IDs de evento
únicos. Ningún consumidor inicial modifica riesgo, decisión o ejecución.

## 26. Reglas exactas de separación y activación

1. El creador del candidato no puede revisar ni activar su versión.
2. El revisor no puede ser el activador cuando también creó el candidato.
3. `AI_SUGGESTED` requiere revisión humana y nunca activa automáticamente.
4. `REJECTED`, `EXPIRED`, `DISABLED` y `SUPERSEDED` son terminales.
5. `ACTIVE` requiere revisión `APPROVE`, vigencia válida y datos no sintéticos.
6. `TREND` requiere muestra mínima real de 20; `CASE_NOTE` no representa una
   tendencia y solo aporta contexto observacional.
7. El scheduler agrega `EXPIRED`; no modifica eventos previos.
8. El kill switch de memoria hace que evaluación devuelva solo el resultado
   base y registre que la influencia fue omitida.

## 27. Configuración exacta

- `MEMORY_INFLUENCE_ENABLED=false` por defecto;
- `MEMORY_MAX_VALIDITY_DAYS=90`;
- `MEMORY_MINIMUM_SAMPLE_SIZE=20`;
- `MEMORY_MAX_REASON_LENGTH=1000`;
- `MEMORY_MAX_EXPLANATION_LENGTH=2000`.

Solo `MEMORY_INFLUENCE_ENABLED=true` habilita evaluación observacional. Nunca
habilita autorización o ejecución.

## 28. Implementación y rollback

La implementación se realiza como módulo `governed_memory` dentro del monolito
modular, con dominio independiente de FastAPI/SQLAlchemy. La migración es
aditiva. El downgrade bloquea si cualquiera de las ocho tablas contiene filas.
Desactivar la navegación o el módulo no elimina evidencia. El kill switch
restaura inmediatamente el resultado base determinístico.
