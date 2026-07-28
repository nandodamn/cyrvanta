# ADR 0012 — Correlación determinista multi-fuente

**Estado:** Aceptado

**Fecha:** 2026-07-28

## Contexto

Cyrvanta ya conserva findings canónicos versionados y claims append-only, pero
la correlación existente pertenece únicamente al escenario demo y no procesa
`security.finding.normalized`.

Wazuh no aporta todavía valores normalizados para activo/cuenta y su categoría
continúa siendo una clasificación del proveedor. Presentar esos valores como
equivalencias universales rompería reproducibilidad y neutralidad.

## Decisión

- Correlation es un bounded context separado y solicita cambios a Incident
  Management mediante un puerto de aplicación.
- La primera versión usa matching exacto por `IP_ADDRESS`, buckets UTC fijos de
  diez minutos y reglas inmutables versionadas.
- Los selectores de señal son datos exactos de regla; no constituyen una
  taxonomía neutral ni acoplan el motor a imports de Wazuh.
- Los factores suman un score de correlación 0–100 separado de riesgo,
  confianza y severidad.
- `correlation_runs` evoluciona como única raíz histórica; los datos demo
  anteriores permanecen identificados como legado simulado.
- Match, miembros, factores, incidente, timeline, `DERIVED_FACT` y outbox se
  confirman dentro de una unidad de trabajo PostgreSQL.
- `PARTIAL` requiere allowlist completa; basis `INGESTED` se rechaza.
- No-match usa métricas, no persistencia ilimitada.
- No existe reapertura, cierre, fuzzy matching, IA o borrado automático.
- El escenario canónico v2 atraviesa la ingestión real y permanece marcado
  inequívocamente como simulado.

Los parámetros, límites, estados, permisos y criterios completos son los
aprobados en la sección 28 de
`docs/specifications/PHASE_18_DETERMINISTIC_MULTI_SOURCE_CORRELATION.md`.

## Consecuencias

La primera regla favorece reproducibilidad y seguridad frente a cobertura
semántica amplia. Activos, cuentas y otros tipos se habilitarán solo con perfiles
de normalización aprobados. Una taxonomía común, ventanas solapadas, replay y
roles analistas requieren contratos posteriores.

La entrega al menos una vez reutiliza outbox/inbox. Constraints PostgreSQL y
fingerprints convierten redelivery y concurrencia en un único efecto observable.

## Reversión

El consumidor puede desactivarse sin detener ingesta. Las reglas se retiran sin
reescribir historia. El downgrade se bloquea cuando existan matches, miembros o
factores. No se eliminan colas, incidentes, claims ni datos demo automáticamente.
