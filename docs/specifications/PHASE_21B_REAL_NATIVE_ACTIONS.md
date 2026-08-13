# PHASE 21-B — Acciones nativas reales y acotadas

Estado: `DRAFT — REQUIERE APROBACIÓN EXPRESA`

## Objetivo

Extender Cyrvanta Playbook Engine para ejecutar acciones finales reales. El tenant puede ser
de laboratorio y los datos pueden ser de prueba, pero el motor, la aprobación, la persistencia,
la auditoría y los efectos del playbook no usan simuladores ni códigos `simulate-*`.

## Primera entrega autorizable

La primera acción real será `incident.status.transition` versión `1.0.0` y el primer playbook
será `contain-and-document-incident` versión `1.0.0`.

El playbook:

1. recibe el incidente exclusivamente desde la autorización tenant-scoped;
2. valida que el estado vigente admite transición a `contained`;
3. valida la versión optimista del incidente registrada en la propuesta;
4. exige aprobación humana independiente;
5. cambia realmente el estado del incidente a `contained` mediante el servicio de aplicación;
6. genera auditoría y eventos mediante los mecanismos existentes;
7. devuelve sólo identificadores, estado final, versión y recibo, nunca evidencia sensible.

No ejecuta shell, código aportado por usuario, consultas libres, webhooks ni egress.

## Contrato del conector

- `action_code`: `incident.status.transition`
- `action_version`: `1.0.0`
- `connector_type`: `INTERNAL`
- modos: `LIVE`
- impacto: `MODERATE`
- `egress`: `NONE`
- credenciales: prohibidas
- reintento: seguro únicamente con la misma clave de idempotencia y versión esperada
- cancelación: no aplicable después del commit atómico
- parámetros permitidos: `target_status=contained` y `reason_code=PLAYBOOK_CONTAINMENT`
- parámetros libres: prohibidos

## Fronteras de seguridad

- `PLAYBOOK_LIVE_ENABLED=false` continúa siendo el valor predeterminado.
- La habilitación requiere configuración global, habilitación tenant-scoped, binding NATIVE
  activo y permiso `automation.live.enable`.
- El requester no puede aprobar su propia propuesta.
- La autorización expira, se consume una sola vez y conserva fingerprint e idempotencia.
- El tenant procede del contexto autenticado y se comprueba en servicio, repositorio y RLS.
- El incidente, propuesta, aprobación, autorización, ejecución y auditoría deben pertenecer al
  mismo tenant.
- Una versión, estado o fingerprint divergente falla cerrado sin efecto parcial.
- n8n no participa en esta acción.

## API, datos y eventos

No se crean endpoints ni tablas. Se reutilizan los contratos aprobados de propuestas,
aprobaciones, autorizaciones, ejecuciones y transición de incidentes. La ejecución conserva
los eventos y auditorías existentes y agrega el código de acción al resultado seguro.

## Interfaz

- La UI mostrará `Ejecución real` / `Live execution`; nunca `Simulado` para este binding.
- Antes de aprobar mostrará el incidente, estado actual, estado objetivo, impacto y efecto.
- El botón de ejecución sólo aparece con autorización activa y configuración LIVE completa.
- Los playbooks simulados heredados no se ofrecerán en el recorrido principal de cliente.

## Criterios de aceptación manual

1. Un tenant de laboratorio ingresa datos de prueba por los contratos normales.
2. Cyrvanta crea y analiza un incidente mediante los servicios reales.
3. Un usuario propone `contain-and-document-incident`.
4. Un usuario distinto aprueba.
5. El motor NATIVE cambia el incidente a `contained` una sola vez.
6. La UI muestra resultado real, timeline y auditoría tenant-scoped.
7. Repetir la misma ejecución no duplica el efecto.
8. Requester autoaprobando, tenant cruzado, versión obsoleta, autorización vencida o LIVE
   deshabilitado fallan cerrado.

## Rollback

Desactivar el binding o `PLAYBOOK_LIVE_ENABLED` impide nuevas ejecuciones. No se revierte
automáticamente un incidente contenido; una reapertura requiere la transición humana ya
aprobada y su justificación auditable.

## Cambio respecto de PHASE 21-A

Al aprobarse, este contrato sustituye exclusivamente la prohibición absoluta de LIVE para la
acción interna aquí definida. El resto de conectores continúa `SIMULATED` o deshabilitado hasta
contar con su propio contrato y aprobación operacional.
