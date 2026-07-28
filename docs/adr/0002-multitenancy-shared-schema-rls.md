# ADR 0002 — Multitenancy con esquema compartido y RLS

- Estado: Aceptado por Foundation
- Fecha: 2026-07-27
- Alcance: primera migración y siguientes

## Contexto

Cyrvanta debe aislar tenants desde el inicio sin imponer una base o esquema por
tenant durante el MVP.

## Decisión

PostgreSQL utilizará una base y un esquema compartidos. Todo registro propiedad
de tenant llevará `tenant_id`. El aislamiento combinará contexto autenticado,
servicios y repositorios tenant-scoped, PostgreSQL Row-Level Security,
constraints compuestas, claves Redis, mensajes RabbitMQ y consultas OpenSearch
con tenant.

El diseño físico, las políticas RLS y los roles de base de datos quedan
pendientes de Fase 2; este ADR no define tablas.

## Consecuencias

- Las operaciones cross-tenant son explícitas, privilegiadas y auditadas.
- No existirán consultas públicas no acotadas sobre datos tenant-owned.
- Cada feature requiere pruebas positivas y negativas A/B.
- Migraciones y jobs deben establecer contexto seguro antes de acceder a datos.

## Alternativas descartadas

Base por tenant y esquema por tenant para la primera versión.
