# Fase 23 — pulso operativo real y UI responsive

**Estado:** APROBADO PARA IMPLEMENTACIÓN  
**Fecha:** 2026-08-01  
**Implementación autorizada:** sí — ratificación humana del 2026-08-01

## 1. Objetivo

Eliminar métricas estáticas presentadas como actividad viva y garantizar que el
dashboard sea utilizable desde 320 px, zoom 200 % y pantallas 4K.

## 2. Contrato API propuesto

`GET /api/v1/operations/activity-24h`

- tenant exclusivo del contexto autenticado;
- exige simultáneamente `incident.read` y `alert.read`;
- consulta PostgreSQL con RLS mediante la sesión tenant-scoped;
- ventana móvil exacta `[now UTC - 24 h, now UTC]`;
- 12 buckets contiguos de dos horas, orden ascendente;
- no acepta parámetros en v1 y no consulta Redis ni datos estáticos.

Respuesta estricta propuesta:

```json
{
  "window_start": "date-time UTC",
  "window_end": "date-time UTC",
  "updated_at": "date-time UTC",
  "source_mode": "EMPTY | SIMULATED | LIVE | MIXED",
  "totals": { "alerts": 0, "incidents": 0 },
  "series": [
    {
      "bucket_start": "date-time UTC",
      "bucket_end": "date-time UTC",
      "alerts": 0,
      "incidents": 0
    }
  ]
}
```

Alertas usan `observed_at`; incidentes usan `detected_at`. La consulta cuenta
todos los registros del tenant dentro de la ventana, sin la paginación del
catálogo. `source_mode` es `EMPTY` sin registros, `SIMULATED` si todos son
sintéticos, `LIVE` si ninguno lo es y `MIXED` si coexisten. Nunca se inventan
valores para rellenar una serie.

## 3. UI propuesta

- refetch periódico cada 60 segundos mientras la vista está montada;
- muestra `updated_at` y la ventana consultada;
- estados separados de loading, error y vacío;
- vacío: “Sin actividad registrada” / “No activity recorded”;
- badge visible para `SIMULATED` y `MIXED`;
- barras con valor y etiqueta accesibles, derivadas sólo de `series`;
- los totales de la tarjeta proceden exclusivamente de `totals`;
- sin badge de vista preliminar ni números decorativos estáticos.

## 4. Responsividad propuesta

- viewport soportado desde 320 px y hasta 4K;
- `overflow-x` global prohibido; tablas/listas extensas usan contenedor interno;
- navegación compacta en móvil;
- grids usan `minmax(0, 1fr)` y colapsan por breakpoints;
- controles alcanzables, con targets mínimos de 42 px;
- verificación a 320, 640, 900, 1440 y 3840 px, además de zoom 200 %.

## 5. Seguridad, auditoría y rollback

Es una consulta read-only y no genera auditoría por lectura ordinaria. No expone
IDs, payloads, secretos ni telemetría raw; sólo conteos tenant-scoped. RLS y
permisos backend son obligatorios. Rollback: retirar el endpoint y volver a un
estado vacío explícito; nunca restaurar cifras estáticas.

## 6. Criterios de aceptación

1. pruebas de agregación para vacío, límites de ventana y modos de fuente;
2. prueba de permiso dual y aislamiento tenant real;
3. frontend prueba loading/error/empty/live/simulated;
4. actualización periódica verificada con reloj controlado;
5. ausencia de contenido estático y overflow global;
6. lint, typecheck, tests y build verdes.

## 7. GATE

Superado por ratificación humana explícita el 2026-08-01. Se autoriza el
endpoint tenant-scoped y la UI descrita en este documento.

