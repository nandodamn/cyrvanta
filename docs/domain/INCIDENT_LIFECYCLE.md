# Ciclo de vida del incidente

**Estado:** DRAFT — requiere aprobación antes de diseñar persistencia o API.

## Objetivo

Definir un flujo conceptual auditable sin fijar nombres físicos, endpoints ni
schemas de eventos.

## Estados candidatos

| Estado | Significado | Entrada permitida desde | Salida candidata |
|---|---|---|---|
| `new` | Incidente creado y aún no reconocido | creación/correlación | `triaged`, `closed` |
| `triaged` | Clasificación inicial y prioridad revisadas | `new`, `reopened` | `investigating`, `closed` |
| `investigating` | Investigación activa | `triaged`, `contained` | `contained`, `resolved`, `closed` |
| `contained` | Impacto limitado; investigación puede continuar | `investigating` | `investigating`, `resolved` |
| `resolved` | Causa/impacto y acciones concluidos | `investigating`, `contained` | `closed`, `reopened` |
| `closed` | Revisión final completada | estados autorizados | `reopened` |
| `reopened` | Nueva evidencia invalida el cierre/resolución | `resolved`, `closed` | `triaged`, `investigating` |

Los nombres y transiciones son candidatos. Debe decidirse si `false_positive`,
`duplicate` y `accepted_risk` son estados, resoluciones o clasificaciones; se
recomienda que sean motivos de cierre para no mezclar flujo con resultado.

## Invariantes propuestas

- Un incidente pertenece exactamente a un tenant.
- Toda lectura o mutación requiere tenant y permiso efectivos.
- Cada transición valida estado esperado y control de concurrencia.
- Toda transición registra actor/proceso, instante UTC, razón y versión previa.
- Cerrar exige motivo; ciertos motivos pueden exigir comentario o evidencia.
- Reabrir conserva historial y justificación; nunca borra el cierre anterior.
- Evidencia y mappings históricos no se reescriben silenciosamente.
- IA y correlación pueden proponer cambios, pero la política determina si se
  aplican y quién puede aplicarlos.
- Una ejecución automática no implica por sí sola que el incidente esté
  resuelto o cerrado.

## Comandos conceptuales

- Crear, reconocer/triage, comenzar investigación.
- Asignar, reasignar y desasignar.
- Adjuntar referencia de alerta o evidencia seleccionada.
- Añadir comentario o entrada de timeline.
- Cambiar clasificación/severidad con explicación.
- Marcar contención, resolver, cerrar y reabrir.
- Relacionar, fusionar o marcar duplicado.
- Solicitar análisis, riesgo, recomendación o playbook.

Cada comando requiere una especificación de precondiciones, permisos,
idempotencia, auditoría y conflicto antes de convertirse en contrato.

## Eventos candidatos

`IncidentCreated`, `IncidentTriaged`, `IncidentAssigned`,
`IncidentEvidenceLinked`, `IncidentStatusChanged`, `IncidentResolved`,
`IncidentClosed`, `IncidentReopened`, `IncidentRelated` e
`IncidentMergeProposed`.

Son nombres conceptuales, no envelopes RabbitMQ aprobados.

## Concurrencia

Se propone control optimista para mutaciones. La versión esperada debe impedir
que dos analistas sobrescriban decisiones. La estrategia para comentarios y
timeline append-only puede ser distinta. Todo conflicto debe ser visible y no
resolverse con last-write-wins silencioso.

## Decisiones pendientes

- Estados y motivos finales, SLA y temporizadores.
- Quién puede crear manualmente, fusionar, cerrar y reabrir.
- Asignación individual, por equipo o ambas.
- Severidad versus score de riesgo y autoridad para modificarlos.
- Requisitos mínimos de cierre y política de falsos positivos.
- Semántica de eliminación/retención.
- Relación alerta-incidente: única, múltiple o versionada.
- Impacto de fusionar incidentes sobre evidencia, mappings y auditoría.
