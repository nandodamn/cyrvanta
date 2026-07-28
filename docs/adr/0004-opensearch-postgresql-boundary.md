# ADR 0004 — Límite PostgreSQL/OpenSearch

- Estado: Aceptado por Foundation
- Fecha: 2026-07-27
- Alcance: persistencia y búsqueda

## Contexto

La telemetría de seguridad tiene volumen y patrones de búsqueda distintos de
los datos transaccionales y de control.

## Decisión

PostgreSQL será el sistema de registro de negocio y control. OpenSearch
almacenará y consultará telemetría de gran volumen. PostgreSQL conservará
referencias, evidencia seleccionada, snapshots mínimos, hashes y metadatos
necesarios para trazabilidad, pero no copiará telemetría completa.

OpenSearch solo será accesible mediante un adaptador interno que imponga
tenant, patrones de índice permitidos, rango temporal, límites, timeout,
paginación segura y validación de consultas.

## Consecuencias

- El dominio no depende del DSL ni de tipos OpenSearch.
- La caída de OpenSearch no impide consultar incidentes ya persistidos.
- Deben definirse consistencia, expiración de referencias y preservación de
  evidencia antes del modelo físico.
- La estrategia índice-por-tenant versus filtro obligatorio queda pendiente.

## Alternativas descartadas

Guardar toda la telemetría en PostgreSQL y permitir DSL arbitrario al usuario.
