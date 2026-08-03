# Evidencia de validación — Fases 21-A y 23

**Fecha:** 2026-08-01  
**Alcance:** motor nativo `SIMULATED`, n8n opcional, pulso operativo real y UI
responsive.  
**LIVE:** deshabilitado; requiere aprobación operativa separada.

## Resultado verificado

- Alembic quedó en `0020_native_playbook_engine` sobre PostgreSQL real.
- Upgrade, downgrade vacío, re-upgrade y rechazo de downgrade con historia se
  probaron en una base aislada y posteriormente se eliminó esa base temporal.
- Las cuatro tablas nuevas aplicaron RLS real: cada tenant observó únicamente
  su fila, un `INSERT` cruzado fue rechazado y el rol de aplicación no pudo
  actualizar ni borrar attempts/outcomes.
- El backup previo a `0020` quedó en
  `C:\tmp\cyrvanta-pre-0020-20260801.dump` y `pg_restore --list` pudo leerlo.
- El flujo nativo completo `SIMULATED` atravesó API, autorización durable,
  RabbitMQ y worker reales. Terminó `SUCCEEDED`, con dos pasos, un attempt y un
  outcome, sin efecto externo.
- La cancelación nativa se probó contra PostgreSQL real con linaje durable
  sintético: terminó `CANCELLED`, registró una auditoría y rechazó un segundo
  intento con estado observado obsoleto.
- OpenAPI expone
  `POST /api/v1/playbook-executions/{execution_id}/cancel` con `If-Match`
  obligatorio. La operación admite `playbook.cancel` o el permiso histórico
  `response.cancel`, bloquea bindings externos y exige que todos los pasos
  activos sean cancelables.
- Un outcome tardío se conserva append-only después de cancelar y no puede
  reactivar ni reemplazar el estado `CANCELLED`. Se verificó con cancelación
  concurrente durante un connector simulado: ejecución y step permanecieron
  cancelados, con un único outcome y auditoría de llegada tardía.
- Una caída inyectada después del claim dejó estado durable `RUNNING/CLAIMED`;
  una nueva instancia reconstruyó el progreso, reutilizó la misma idempotency
  key y el mismo attempt, persistió un único outcome y cerró `SUCCEEDED`.
- RabbitMQ recibió un envelope sintético inválido; el worker lo rechazó y lo
  conservó en `cyrvanta.traceability.v1.dlq` con código sanitizado
  `invalid_envelope`.
- El adaptador n8n registró un dispatch ambiguo como outcome append-only
  `UNKNOWN` y devolvió la ejecución a `QUEUED` para retry, sin realizar una
  llamada externa en la prueba.
- Ruff no reportó hallazgos; MyPy validó 126 archivos fuente; Pytest aprobó
  148/148 pruebas backend.
- Vitest aprobó 13/13 pruebas frontend; ESLint terminó sin warnings y el build
  de producción de Vite finalizó correctamente.
- Backend, frontend, reverse proxy, PostgreSQL, RabbitMQ y Redis quedaron
  saludables. Worker y scheduler quedaron activos. n8n permanece en su perfil
  opcional y `N8N_ENABLED=false` sigue siendo el valor predeterminado de
  Cyrvanta.

## Seguridad y aislamiento

- El tenant procede del contexto autenticado o del envelope interno firmado;
  no se acepta desde bodies de administración.
- Los artefactos portables rechazan campos extra, claves con apariencia de
  secreto, código/shell, schemas remotos, DAG inválido y acciones no
  registradas.
- Los eventos nativos usan una allowlist de IDs, estado, digest y códigos
  sanitizados; no contienen artefactos, inputs, outputs, aliases ni secretos.
- Las claves internas dispatch/callback se derivan por propósito desde la clave
  maestra de instalación y se entregan mediante leases de un solo uso. La API
  key externa de n8n continúa siendo write-only por configuración de despliegue.
- `PLAYBOOK_LIVE_ENABLED=false` y el runner rechaza cualquier ejecución no
  sintética.

## Evidencia pendiente antes del cierre integral

- Conservar una prueba de paridad concurrente NATIVE/n8n que demuestre ausencia
  de doble efecto bajo dos redeliveries simultáneos. La selección exclusiva por
  binding y el cierre fail-closed de n8n deshabilitado ya tienen pruebas.
- Resolver el GATE de identidad de plataforma antes de permitir reemplazo,
  prueba o rotación global de la API key externa de n8n desde backend/UI. La
  pantalla actual prepara el handoff en memoria y nunca persiste ni transmite
  el valor; conceder una mutación global a `tenant-admin` violaría el contrato
  multitenant de Fase 5.
- Ejecutar inspección visual real a 320 px, escritorio/4K y zoom 200 %. El
  conector del navegador no pudo iniciar por un error de ACL del runtime de
  Windows; las pruebas de componentes y CSS no sustituyen esta evidencia.
- LIVE y cualquier retiro de n8n continúan fuera del alcance autorizado.

## Rollback

El rollback operativo es cerrar los kill switches y no crear nuevos dispatch.
El downgrade de `0020` sólo está permitido sin historia nativa ni bindings
`NATIVE`; con evidencia, aborta deliberadamente y preserva la auditoría.
