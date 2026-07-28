# ADR 0009 — Arquitectura de adaptadores multi-SIEM

- Estado: Aceptado
- Fecha: 2026-07-28

## Contexto

La base declaraba Wazuh reemplazable, pero su salud y configuración estaban
mezcladas con servicios de plataforma y no existía un puerto, capacidades,
registro, persistencia o modelo canónico ejecutable.

## Decisión

Crear `Security Integrations` con puerto SIEM, modelos canónicos, capacidades,
errores y registro de fábricas. Registrar solo Wazuh, encapsulando índice y
payload en infraestructura. Persistir configuración cifrada, cursores y salud
en tablas genéricas con RLS.

La composición desde variables de entorno se conserva para el laboratorio. La
API de salud mantiene compatibilidad. Los conectores futuros solo se documentan.

## Consecuencias

El núcleo y la IA no necesitan estructuras Wazuh. Una operación no común falla
según capacidades. Un segundo conector puede añadirse sin alterar el dominio.

La ejecución durable de polling, backoff y DLQ y la administración CRUD quedan
pendientes de contratos de jobs/API; el servicio de sincronización ya define
tenant, cursor, lote e idempotencia.

## Reversión

Se puede retirar el registro sin cambiar incidentes. La migración
`0006_integrations` elimina únicamente las tres tablas nuevas y sus permisos.

