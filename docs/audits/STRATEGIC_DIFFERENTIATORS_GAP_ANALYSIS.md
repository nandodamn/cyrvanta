# Auditoría de diferenciadores estratégicos

**Fecha:** 2026-07-28
**Estado:** AUDITADO — describe el código del commit base `c25446d`; no aprueba
contratos nuevos.
**Alcance:** correlación multi-SIEM, clasificación epistemológica, decisión
segura, memoria operacional, Decision Graph, explicabilidad y trazabilidad.

## Criterio de clasificación

Una capacidad solo se considera implementada cuando participa en el flujo real,
persiste su estado cuando corresponde, aplica permisos y aislamiento por tenant,
audita mutaciones, maneja errores y tiene pruebas. Una pantalla, mock o
documento por sí solos no constituyen implementación.

Estados: `NOT_IMPLEMENTED`, `DOCUMENTED_ONLY`, `UI_ONLY`, `MOCK_ONLY`,
`PARTIAL`, `IMPLEMENTED_NOT_INTEGRATED`, `IMPLEMENTED_WITH_GAPS` y
`PRODUCTION_READY`.

## Resumen ejecutivo

| Capacidad | Estado | Prioridad | Conclusión |
|---|---|---:|---|
| Correlación multi-SIEM | `PARTIAL` | P0 | La abstracción de conectores existe, pero la correlación persistida es sintética. |
| Hechos, inferencias y recomendaciones | `DOCUMENTED_ONLY` | P0 | El análisis mezcla resumen, score y recomendaciones; no existen claims trazables. |
| Decisión y automatización segura | `PARTIAL` | P0 | Hay allowlist, kill switch de despliegue e idempotencia básica, pero no política, aprobación ni ejecución persistentes. |
| Memoria operacional | `NOT_IMPLEMENTED` | P2 | No existe dominio, persistencia, API, worker ni UI. |
| Cyrvanta Decision Graph | `NOT_IMPLEMENTED` | P2 | No existe proyección navegable; hay relaciones dispersas. |
| Trazabilidad de evento a resultado | `PARTIAL` | P0 transversal | Existen auditoría, timeline y correlation ID HTTP, pero la cadena no llega a un resultado persistente. |
| Explicabilidad | `PARTIAL` | P1 | Hay textos explicativos aislados, sin servicio ni contrato común de procedencia. |

Ninguna de estas capacidades está actualmente en estado `PRODUCTION_READY`.

## Base reutilizable verificada

- Monolito modular con tenant obtenido del contexto autenticado.
- RLS para tablas tenant-owned, permisos deny-by-default y auditoría persistente.
- Correlation ID HTTP en `shared/http.py`.
- Puerto `SIEMConnector`, registro de conectores y adaptador Wazuh.
- `CanonicalFinding`, `CanonicalExternalIncident`, `CanonicalEvidence`,
  entidades, procesos, archivos e indicadores canónicos.
- Persistencia de integraciones, sincronización y salud.
- Alertas, incidentes, relación incidente-alerta, timeline y correlation runs.
- Catálogo allowlisted de workflows n8n y acceso indirecto al editor.
- Fake connector limitado a pruebas y datos demo identificados en frontend.
- Línea base observada: 37 pruebas backend, 4 frontend y build de producción.
- No existe una prueba E2E de la cadena estratégica completa.

## 1. Correlación multi-SIEM

**Estado:** `PARTIAL`
**Esfuerzo:** XL
**Prioridad:** P0

### Evidencia existente

- Documentos: ADR 0009, arquitectura multi-SIEM y contratos canónicos.
- Código: `modules/integrations/`, adaptador Wazuh, fake connector y servicio de
  incidentes.
- Tablas: `integrations`, `integration_sync_state`,
  `integration_health_history`, `alert_references`, `incident_alerts` y
  `correlation_runs`.
- API: salud de integraciones, alertas, incidentes y escenario demo.
- Pruebas: capacidades, tenant, rechazo cross-tenant, deduplicación,
  normalización Wazuh, errores canónicos y fake ausente de producción.

### Flujo real

Wazuh puede producir hallazgos canónicos y sincronización valida tenant y
deduplica un lote. Ese flujo no alimenta un motor general de correlación. El
único `correlation_run` creado por el producto pertenece al escenario sintético
`credential-attack`.

### Gaps y riesgos

- No hay selección de candidatos multi-fuente.
- No hay resolución persistente de activos, identidades o equivalencias.
- No se persisten miembros, factores, score, confianza, validación ni versiones
  completas.
- No hay reglas configurables, métricas de precisión o regresión.
- El worker conecta RabbitMQ, pero no consume trabajos.
- No hay API/UI de explicación y validación.
- Agregar conectores antes de estabilizar el contrato canónico multiplicaría
  transformaciones incompatibles.

### Recomendación

Reutilizar el puerto actual. Formalizar procedencia, resolución de entidades,
semántica de correlación y reglas iniciales. Implementar un motor determinista
versionado antes del apoyo opcional de IA.

## 2. Hechos, inferencias y recomendaciones

**Estado:** `DOCUMENTED_ONLY`
**Esfuerzo:** L
**Prioridad:** P0

`DOMAIN_MODEL.md` exige procedencia y `AnalysisResponse` entrega resumen,
confianza, score, técnicas y recomendaciones. No hay tablas, endpoints, eventos,
workers, UI o pruebas específicos para claims epistemológicos.

### Gaps y riesgos

- Una inferencia puede mostrarse como hecho.
- Las recomendaciones no enlazan evidencia, regla, modelo ni prompt.
- No hay validación, rechazo, supersesión o contradicción.
- No hay procedencia reproducible ni versionado.
- No existe representación accesible por categoría.
- Falta decidir la semántica bilingüe del contenido persistido.

### Recomendación

Definir un ledger append-oriented con taxonomía cerrada, evidencia obligatoria
según categoría y separación entre creación, validación y presentación. No
guardar cadenas privadas de razonamiento.

## 3. Motor de decisión y automatización segura

**Estado:** `PARTIAL`
**Esfuerzo:** XL
**Prioridad:** P0

### Evidencia existente

- API de catálogo, administración y ejecución de playbooks.
- Workflow allowlisted, bandera global, booleano `approved`, idempotency key,
  adaptador n8n, auditoría y pruebas de fallo cerrado.

### Flujo real

Una solicitud autorizada entrega `approved`, workflow e idempotency key. El
servicio invoca n8n o devuelve un resultado simulado. No existe registro
transaccional de propuesta, evaluación, aprobación, autorización, ejecución y
resultado.

### Gaps y riesgos

- El cliente aporta `approved`; no representa una aprobación independiente.
- No hay política versionada por tenant, acción, target u horario.
- No existe doble control o separación de funciones.
- No hay evaluación persistente de impacto, reversibilidad o suficiencia.
- No existen playbook/version/approval/execution/result durables.
- El kill switch no es global y por tenant con auditoría.
- La idempotencia en memoria no resiste reinicios o concurrencia.
- No hay callback autenticado persistente, timeout, retry, DLQ o rollback.
- Un estado del adaptador podría confundirse con resultado confirmado.

### Recomendación

Diseñar una máquina de estados persistente y deny-by-default. Separar propuesta,
evaluación determinista, aprobación, autorización breve, ejecución y resultado
confirmado. Mantener n8n como adaptador reemplazable.

## 4. Memoria operacional

**Estado:** `NOT_IMPLEMENTED`
**Esfuerzo:** XL
**Prioridad:** P2

Audit, timeline e incidentes serían fuentes futuras. No hay clases, tablas,
endpoints, eventos, workers, UI o pruebas de memoria.

### Gaps y riesgos

- No existen vigencia, revisión, expiración o corrección.
- No se normalizan outcomes ni verdadero/falso positivo.
- No están aprobadas privacidad y retención de perfiles.
- Una memoria alimentada por fixtures produciría conclusiones falsas.
- Una coincidencia histórica podría convertirse indebidamente en excepción.

### Recomendación

Posponer la influencia automática. Comenzar con feedback inmutable y métricas
observacionales cuando ya existan decisiones y resultados. Toda memoria
influyente requiere aprobación, vigencia, procedencia y explicación visible.
No reentrenar modelos automáticamente.

## 5. Cyrvanta Decision Graph

**Estado:** `NOT_IMPLEMENTED`
**Esfuerzo:** L después de completar sus fuentes; XL si se adelanta
**Prioridad:** P2

Hay relaciones aisladas entre incidentes, alertas, timeline, correlation runs y
audit. No existen proyección, API, UI, exportación o pruebas de grafo.

### Gaps y riesgos

- Tablas genéricas tempranas duplicarían agregados.
- Un grafo mutable como fuente principal debilitaría invariantes.
- No puede representar claims, decisiones y resultados aún inexistentes.
- Faltan límites de tamaño, profundidad y consulta.
- Una visualización sin alternativa textual incumpliría accesibilidad.

### Recomendación

Implementarlo como read model derivado de fuentes autoritativas en PostgreSQL.
No añadir una base de grafos sin mediciones. Incluir vista textual/tabular y
límites de profundidad, nodos y período.

## 6. Trazabilidad completa

**Estado:** `PARTIAL`
**Esfuerzo:** L transversal
**Prioridad:** P0 transversal

### Evidencia existente

- `audit_events`, timeline append-oriented y correlation ID HTTP.
- Procedencia externa en modelos canónicos.
- Versiones en incidentes y correlation runs.
- Auditoría de mutaciones importantes actuales.

### Gaps y riesgos

- No existe envelope implementado con event ID, causation ID y versión.
- RabbitMQ no publica ni consume trabajo funcional.
- El correlation ID no atraviesa integración, análisis, decisión, n8n y callback.
- No se persiste la cadena análisis-recomendación-aprobación-ejecución-resultado.
- Audit no sustituye registros de negocio ni demuestra causalidad.
- No hay exportación integral o prueba de reconstrucción.

### Recomendación

Aplicar envelope versionado, outbox transaccional, inbox/idempotencia,
referencias estables y causation ID en todas las etapas. La reconstrucción usa
registros de negocio; Audit es evidencia complementaria.

## 7. Explicabilidad transversal

**Estado:** `PARTIAL`
**Esfuerzo:** M después del modelo de claims
**Prioridad:** P1

Hay explicaciones locales en correlation runs, análisis demo y reportes. No
existe servicio común, procedencia consolidada o tratamiento uniforme de
contradicciones y datos faltantes.

Las explicaciones deben ser proyecciones deterministas de claims, factores,
versiones y evidencia. El LLM puede redactar una versión bilingüe, pero no ser
la fuente de verdad.

## Deuda técnica condicionante

1. Worker RabbitMQ sin consumidores y scheduler limitado a heartbeat.
2. Falta de outbox/inbox y semántica de entrega.
3. Dominio y autorización todavía `DRAFT`.
4. MITRE estático, reducido y sin importación STIX.
5. Análisis de IA y riesgo no persistentes y demostrativos.
6. Automatizaciones sin registros durables.
7. Ausencia de observabilidad y E2E.
8. Frontend concentrado principalmente en `App.tsx`.

## Decisiones que bloquean contratos

1. Ownership de usuario multi-tenant y administrador de plataforma.
2. Evidencia, integridad, clasificación y retención.
3. Taxonomía final de claims y validación.
4. Reglas, ventanas, thresholds y resolución de entidades.
5. Riesgo reproducible y relación riesgo/confianza.
6. Permisos y separación de funciones.
7. Acciones, impacto, targets, rollback y doble control.
8. Kill switch global/tenant y break-glass.
9. Eventos, reintentos, orden, DLQ y consistencia.
10. Memoria, privacidad, expiración e influencia.
11. Volumen, latencia, SLA, RPO/RTO y exportación.
12. Estrategia OpenSearch por tenant y acceso a evidencia.

Los nombres del prompt adjunto siguen siendo candidatos, no contratos.
