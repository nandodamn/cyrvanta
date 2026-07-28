# ADR 0010 — Findings canónicos con revisiones de procedencia

**Estado:** Aceptado  
**Fecha:** 2026-07-28

## Contexto

Cyrvanta recibía findings Wazuh normalizados en memoria, pero no tenía
idempotencia durable, historial de cambios ni calidad de normalización. El
normalizador sustituía timestamps ausentes por la hora actual y el dominio
dependía de Pydantic.

`alert_references` ya es consumida por la API, incidentes y dashboard. Romperla
o renombrarla introduciría una migración funcional innecesaria.

## Decisión

- `CanonicalFinding` es una dataclass inmutable neutral de proveedor.
- `alert_references` conserva la identidad y proyección vigente.
- `finding_revisions` conserva revisiones append-only, procedencia, fingerprint,
  tiempos y calidad.
- La identidad externa incluye tenant, integración, tipo e ID de objeto.
- El mismo fingerprint no crea revisión ni evento.
- Un cambio de payload crea otra revisión y actualiza la proyección
  transaccionalmente.
- El timestamp externo puede ser nulo; `effective_time_basis` declara si el
  tiempo proviene de fuente, derivación o ingestión.
- PostgreSQL no conserva el documento raw.
- Una revisión nueva registra `security.finding.normalized` en el outbox.
- `integration_id` es una identidad lógica UUID sin FK temporal a
  `integrations`: la configuración Wazuh local actual es derivada y todavía no
  tiene CRUD durable aprobado. La FK podrá agregarse cuando toda integración
  activa tenga registro autoritativo.

## Parámetros v1

- Título: 500 caracteres.
- Descripción: 4000.
- ID externo: 512.
- Categoría: 120.
- Estado externo: 80.
- Regla: 200.
- Localizador de evidencia: 2048, sin usuario, contraseña, query ni fragment.
- Hasta 32 referencias de entidad y 32 incidencias de normalización.
- Severidad: `0–19 informational`, `20–39 low`, `40–59 medium`,
  `60–79 high`, `80–100 critical`.
- Completitud Wazuh: cinco dimensiones con igual peso — timestamp, regla,
  título, categoría y referencia de entidad/red.

La retención no se ejecuta en esta etapa; permanece bloqueada hasta aprobar la
política por tenant y los mínimos de plataforma.

## Consecuencias

- API y UI actuales mantienen compatibilidad.
- Wazuh ya no presenta un tiempo de ingestión como tiempo declarado por fuente.
- Se agrega almacenamiento acotado, índices y un evento por revisión real.
- Los consumidores futuros pueden correlacionar sin conocer Wazuh.
- Conectores futuros deben pasar el mismo kit contractual y solicitar cualquier
  nuevo esquema de evidencia permitido.

## Alternativas descartadas

- Sobrescribir un único finding: pierde historial y procedencia.
- Guardar payload raw en PostgreSQL: rompe el límite con OpenSearch.
- Renombrar `alert_references`: rompe consumidores actuales.
- Activar polling automático inmediatamente: un entorno sin datos o
  credenciales reales generaría ruido operativo. Se entrega un comando acotado
  y el scheduler queda sin activación automática.
