# ADR 0021 — Polling Wazuh automático con cursor durable

**Estado:** Propuesto — pendiente de aprobación explícita

## Contexto

La ingesta real Wazuh funciona mediante un comando manual acotado y ya conserva
procedencia, revisiones, idempotencia y eventos. La especificación de Fase 16
dejó frecuencia, cursor durable y política operativa como gate separado. El
scheduler actual no ingiere telemetría.

## Decisión propuesta

- Adoptar la Fase 25 como contrato vinculante sólo después de aprobación.
- Polling deshabilitado por defecto y habilitable por integración verificada.
- Estado durable en `integration_sync_state`, sin cursores en API/UI.
- Reclamo concurrente con lease y `SKIP LOCKED`.
- Cursor confirmado únicamente después de lote completo.
- Intervalo 60 s, lote 100, lease 120 s y backoff máximo 15 min.
- Fallo cerrado ante configuración ausente, ambigua o no saludable.
- Ningún polling ejecuta decisiones o playbooks.

## Consecuencias

La plataforma podrá ingerir continuamente sin depender de un operador y podrá
recuperarse de reinicios sin perder o adelantar el cursor. Se añade estado
operativo, una migración, endpoints administrativos, UI y carga periódica
acotada sobre Wazuh/OpenSearch y PostgreSQL.

## Alternativas descartadas

- Cron sin cursor persistido: puede perder o repetir intervalos sin control.
- Cursor en Redis: Redis no es sistema de registro.
- Un loop por tenant sin lease: duplica trabajo con múltiples réplicas.
- Activación automática al guardar credenciales: produce egreso sin decisión
  operativa explícita.

## Activación

Este ADR permanece `Propuesto`. No autoriza migración, endpoints, scheduler ni
egreso hasta que el operador apruebe expresamente PHASE 25 y ADR 0021.
