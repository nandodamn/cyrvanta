# ADR 0014 — Decisión segura y doble aprobación

**Estado:** Aceptado
**Fecha:** 2026-07-29

## Contexto

La automatización provisional aceptaba `approved: bool`, que no demostraba una
decisión persistida, permisos, separación de funciones, quorum, vigencia ni
coincidencia de los parámetros aprobados.

Cyrvanta necesita preparar ejecución durable sin permitir que React, IA, n8n o
un valor aportado por el cliente se conviertan en autoridad.

## Decisión

Adoptar el contrato de
`docs/specifications/PHASE_20_SAFE_DECISION_APPROVAL.md`:

- propuesta inmutable con fingerprint de inputs materiales;
- política determinística y versionada;
- aprobaciones append-only;
- solicitante distinto de los aprobadores;
- doble aprobación para alto impacto;
- acciones críticas denegadas inicialmente;
- modo automático desactivado;
- autorización breve, revocable y de un solo uso;
- RLS y claves tenant-scoped;
- auditoría y eventos durables;
- bloqueo de ejecución live basada en `approved: bool`.

n8n permanece como adaptador futuro. La Etapa 6 no ejecuta acciones.

## Consecuencias

### Positivas

- La autorización puede explicarse y reproducirse.
- Se impide autoaprobación y reutilización silenciosa.
- Cambios materiales invalidan la decisión.
- Etapa 7 recibe una capacidad acotada en lugar de un booleano.
- La demo continúa sin presentar simulación como contención real.

### Costos

- Se requieren actores distintos para completar aprobaciones.
- Aumenta el número de estados y registros persistentes.
- La expiración, revocación y concurrencia requieren pruebas específicas.

## Alternativas descartadas

- Confiar en `approved: true`.
- Guardar el quorum en n8n.
- Permitir que la IA decida.
- Habilitar respuesta automática por defecto.
- Usar un token bearer reutilizable expuesto al navegador.

## Rollback

Deshabilitar la creación de propuestas y revocar autorizaciones no consumidas.
Decisiones y auditoría se conservan. No se reabre ejecución live provisional.
