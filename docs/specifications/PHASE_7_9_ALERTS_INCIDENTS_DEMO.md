# Fases 7–9 — Alertas, incidentes y escenario demo

**Estado:** IMPLEMENTATION BASELINE — autorizado para demo local el 2026-07-27  
**Versión:** 0.1.0  
**Alcance:** referencias de alertas, incidentes, timeline y datos sintéticos  
**Fuera de alcance:** telemetría raw en PostgreSQL, ejecución ofensiva y
automatización sin aprobación

## 1. Decisiones de dominio

- Una alerta de origen puede relacionarse con cero o un incidente activo en el
  demo. La relación se puede revisar posteriormente, pero nunca cruza tenants.
- PostgreSQL conserva una referencia normalizada y un snapshot mínimo; el
  evento raw permanece en OpenSearch.
- Un incidente pertenece exactamente a un tenant y usa control optimista
  mediante `version`.
- Estados aprobados para el demo:
  `new`, `triaged`, `investigating`, `contained`, `resolved`, `closed`,
  `reopened`.
- Transiciones permitidas:
  - `new` → `triaged`, `closed`
  - `triaged` → `investigating`, `closed`
  - `investigating` → `contained`, `resolved`, `closed`
  - `contained` → `investigating`, `resolved`
  - `resolved` → `closed`, `reopened`
  - `closed` → `reopened`
  - `reopened` → `triaged`, `investigating`
- `false_positive`, `duplicate`, `accepted_risk`, `resolved` y `other` son
  motivos de cierre, no estados.
- Cerrar o reabrir exige razón.
- Toda transición y mutación crea timeline y auditoría en la misma transacción.

## 2. AlertReference

Campos aprobados para el demo:

- UUID, tenant, fuente y ID externo;
- instante observado;
- título y categoría normalizados;
- severidad: `informational`, `low`, `medium`, `high`, `critical`;
- asset/identity/indicadores resumidos y minimizados;
- referencia opaca al documento raw;
- hash SHA-256 opcional del snapshot;
- provenance: `synthetic`, `wazuh` u otro adaptador registrado;
- `is_simulated`, siempre visible en API/UI;
- timestamps de creación y actualización.

La clave idempotente es tenant + fuente + ID externo.

## 3. Incident

Campos aprobados para el demo:

- UUID y tenant;
- código humano tenant-scoped;
- título y descripción;
- estado, severidad y prioridad;
- clasificación;
- responsable interno opcional;
- versión optimista;
- `is_simulated`;
- timestamps de detección, reconocimiento, resolución, cierre y actualización;
- motivo y comentario de cierre opcionales.

No existe eliminación de incidentes por API.

## 4. Timeline y evidencia

- El timeline es append-only.
- Conserva tipo, actor/proceso, resumen, instante efectivo/registrado,
  referencia al recurso y versión del incidente.
- Una referencia de alerta vinculada actúa como evidencia mínima; no concede
  acceso al documento raw.
- Comentarios y texto sintético se tratan como contenido no confiable.

## 5. Correlación demo

La primera correlación es determinística, versionada y explicable:

- mismo tenant;
- ventana temporal configurable;
- coincidencia de asset, identidad o indicador;
- familia de categoría compatible;
- umbral de severidad.

La salida registra regla/version, alertas incluidas y explicación. La
correlación puede crear o actualizar un incidente, pero nunca cerrarlo.

## 6. Contrato HTTP

Todas las rutas están bajo `/api/v1`.

| Método | Ruta | Permiso | Resultado |
|---|---|---|---|
| `GET` | `/alerts` | `alert.read` | Referencias tenant-scoped |
| `GET` | `/alerts/{id}` | `alert.read` | Referencia normalizada |
| `GET` | `/incidents` | `incident.read` | Incidentes tenant-scoped |
| `POST` | `/incidents` | `incident.create` | Creación manual |
| `GET` | `/incidents/{id}` | `incident.read` | Detalle |
| `PATCH` | `/incidents/{id}` | `incident.update` | Campos permitidos con versión |
| `POST` | `/incidents/{id}/transition` | permiso por transición | Cambio de estado |
| `POST` | `/incidents/{id}/assign` | `incident.assign` | Asignación |
| `GET` | `/incidents/{id}/timeline` | `incident.read` | Timeline |
| `POST` | `/incidents/{id}/timeline` | `incident.update` | Comentario |
| `POST` | `/demo/scenarios/credential-attack` | `incident.create` | Dataset sintético idempotente |
| `POST` | `/demo/reset` | `tenant.manage` | Retira solo datos simulados |

`tenant_id` no se acepta en cuerpos. Listados usan límites acotados. Un ID de
otro tenant responde como no encontrado.

## 7. Escenario sintético

El escenario `credential-attack-v1` representa defensivamente:

1. varios intentos fallidos de autenticación;
2. autenticación exitosa desde ubicación atípica;
3. elevación de privilegios simulada;
4. acceso anómalo a un recurso ficticio;
5. correlación en un incidente de severidad alta.

No genera tráfico ofensivo, no ejecuta comandos, no toca endpoints externos y
no contiene datos personales reales. Cada objeto lleva `is_simulated=true` y
provenance `synthetic`.

## 8. OpenSearch y Wazuh

- El dominio consume un puerto `TelemetrySearchPort`.
- El adaptador impone tenant, índice allowlisted, ventana temporal, límite y
  timeout.
- No se expone DSL OpenSearch al cliente.
- El adaptador Wazuh transforma fixtures o respuestas verificadas al DTO
  canónico.
- La ausencia de OpenSearch/Wazuh no impide ejecutar el escenario sintético ni
  consultar incidentes persistidos.

## 9. Permisos

Se usan los permisos existentes de Foundation:

`alert.read`, `incident.read`, `incident.create`, `incident.assign`,
`incident.update`, `incident.close`.

El rol demo administrador recibe el catálogo completo. Roles de solo lectura
reciben únicamente lectura explícita.

## 10. Pruebas obligatorias

- RLS y API A/B para alertas, incidentes, relaciones y timeline.
- Idempotencia del escenario sintético.
- Matriz completa de transiciones válidas e inválidas.
- Conflicto de versión devuelve 409.
- Cierre/reapertura sin razón falla.
- IDs cross-tenant no revelan existencia.
- `is_simulated` no puede eliminarse mediante API.
- No aparece telemetría raw en PostgreSQL.
- Caída de OpenSearch no rompe lectura de incidentes.
- Correlación produce la misma salida para los mismos inputs/version.
- Todas las mutaciones generan timeline y auditoría.
- UI española/inglesa distingue inequívocamente datos simulados.

## 11. Reversión

- La migración es aditiva y no modifica `0001`–`0003`.
- El escenario se puede retirar de forma selectiva mediante `demo/reset`.
- Los adaptadores pueden deshabilitarse sin perder incidentes.
- El reset nunca toca datos no simulados.
