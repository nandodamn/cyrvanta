# ADR 0008 — Listados buscables y acotados

- Estado: Aceptado
- Fecha: 2026-07-27

## Contexto

Los listados principales podían crecer hasta dificultar el uso del dashboard.
Alertas, incidentes y auditoría tenían un límite técnico sin navegación ni
búsqueda; usuarios no tenía un límite en backend. Limitar únicamente el DOM no
evita transferencias o consultas excesivas.

## Decisión

- Usuarios, incidentes, alertas y auditoría aceptan `limit`, `offset` y `q`.
- `limit` queda entre 1 y 100; la interfaz ofrece 10, 25 o 50 elementos.
- `offset` queda limitado a 10.000 y `q` a 100 caracteres.
- La búsqueda se ejecuta dentro del tenant autenticado y escapa comodines SQL.
- El orden incluye un identificador como desempate para mantener páginas
  estables.
- La respuesta continúa siendo una lista para conservar compatibilidad.
- El frontend solicita una fila adicional para determinar si existe una página
  siguiente, pero nunca la muestra.
- Catálogos pequeños y acotados, como integraciones y permisos, no incorporan
  paginación hasta que su especificación permita crecimiento dinámico.

## Seguridad y multitenancy

Los parámetros no contienen ni establecen tenant. Los servicios siguen usando
`tenant_session`, RLS y los permisos existentes. Los límites reducen consultas
accidentales o abusivas; no sustituyen rate limiting.

## Consecuencias

Sin un contrato de conteo no se presenta un total potencialmente incorrecto:
la interfaz muestra cantidad visible y número de página. Para saltos directos a
una página o totales exactos se necesitará una respuesta paginada versionada.

## Reversión

Los parámetros son opcionales y no requieren migraciones. La interfaz puede
retirar los controles y los endpoints continuarían respondiendo listas
acotadas.
