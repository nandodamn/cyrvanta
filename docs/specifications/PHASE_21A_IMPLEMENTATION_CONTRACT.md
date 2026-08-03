# Fase 21-A — contrato de implementación del Playbook Engine nativo

**Estado:** APROBADO PARA IMPLEMENTACIÓN  
**Fecha:** 2026-08-01  
**Implementación física autorizada:** sí — ratificación humana del 2026-08-01

## 1. Propósito y precedencia

Este addendum cierra las decisiones físicas que
`PHASE_21A_CYRVANTA_PLAYBOOK_ENGINE.md` dejó expresamente pendientes. No cambia
el ADR 0017 ni sustituye los contratos de Fase 21. En caso de contradicción,
prevalecen el aislamiento tenant, la seguridad, Foundation, Fase 21 y la
especificación 21-A aprobada, en ese orden.

Este contrato fue ratificado junto con la decisión de usar el motor nativo como
predeterminado y mantener n8n opcional globalmente y por playbook.

## 2. Alcance de la primera entrega

La primera entrega implementa:

- motor `NATIVE` para artefactos portable v1;
- acciones `notification.send`, `ticket.create`,
  `incident.report.generate`, `webhook.invoke_allowlisted` y
  `endpoint.isolate_simulated`;
- sólo modo `SIMULATED`; cualquier `LIVE` falla cerrado;
- condiciones declarativas del schema portable v1;
- ejecución asíncrona en los workers existentes;
- coexistencia contractual con bindings `N8N` sin reescribir su historia;
- motor nativo disponible por defecto, con activación efectiva gobernada por
  autorización, tenant, binding y kill switches.

`endpoint.isolate`, conectores destructivos, editor visual, loops, espera,
subplaybooks y plugins permanecen fuera de esta entrega.

## 3. Migración `0020_native_playbook_engine`

La revisión será `0020_native_playbook_engine`, con `down_revision =
"0019_governed_memory"`. No se modifica ninguna migración anterior.

### 3.1 Evolución de `playbook_definitions`

Se agregan `description_es varchar(2000)` y `description_en varchar(2000)`
nullable para preservar las definiciones históricas. Las definiciones nuevas
exigen ambos valores; `title_i18n.es/en` se persiste en `name_es/name_en`. El
código es inmutable y único por tenant. El rol de aplicación recibe `INSERT`,
pero no `UPDATE` ni `DELETE` en v1; una corrección de identidad requiere una
nueva definición.

### 3.2 Evolución de `playbook_versions`

Se agregan columnas nullable para no reinterpretar versiones históricas n8n:

| Columna | Tipo y regla |
|---|---|
| `portable_artifact` | jsonb objeto, máximo lógico 256 KiB |
| `portable_schema_version` | varchar(16), exactamente `1.0` cuando hay artefacto |
| `validated_sha256` | varchar(64), hexadecimal minúscula nullable |
| `validated_at` | timestamptz nullable |
| `validated_by_user_id` | uuid nullable, FK compuesta a users |

Las cinco columnas permanecen nulas en registros históricos. Una versión sólo
puede recibir binding `NATIVE` si tiene artefacto, schema `1.0`, validación
vigente y `validated_sha256 = artifact_sha256`. El estado físico conserva
`DRAFT | APPROVED | RETIRED`; la API presenta `APPROVED` como `PUBLISHED` para
el vocabulario portable. Validar no cambia el estado: actualiza únicamente los
tres campos de validación bajo comparación de digest. Publicar cambia `DRAFT`
a `APPROVED` y fija el aprobador/fecha.

Mapeo portable compatible: `execution_mode=SIMULATED` se persiste como
`classification=SYNTHETIC`; `LIVE` como `LIVE`; impacto `MEDIUM` se persiste
como `MODERATE`; los demás impactos conservan nombre. El artefacto canónico y
su digest son inmutables desde la inserción; una corrección crea otra versión.

El rol de aplicación recibe `INSERT` y sólo `UPDATE` de `validated_sha256`,
`validated_at`, `validated_by_user_id`, `status`, `approved_by_user_id` y
`approved_at`. No recibe `DELETE` ni permiso para actualizar el artefacto,
versión, schemas o digest.

`input_schema_ref` y `result_schema_ref` se resuelven únicamente desde el
registro interno allowlisted y versionado de Cyrvanta. No se permiten URLs,
filesystem ni resolución remota. Al crear la versión se copian los schemas
resueltos y estrictos a `input_schema` y `result_schema`; un ref desconocido o
un schema no estricto rechaza la operación. Cambiar el registro no altera una
versión ya creada.
### 3.3 Evolución de `automation_engine_bindings`

1. `engine_type` admite exactamente `NATIVE | N8N`.
2. `adapter_workflow_id`, `webhook_path` y `key_id` pasan a ser nullable.
3. Un check exige los tres campos no nulos para `N8N` y nulos para `NATIVE`.
4. `instance_code` permanece obligatorio; el adaptador local usa
   `cyrvanta-native`.
5. `desired_digest`, `observed_digest`, `sync_status`, `active` y
   `last_verified_at` conservan su semántica. Un binding nativo sólo queda
   `SYNCHRONIZED` si el artefacto, DAG, schemas y acciones registradas validan.
6. La activación sigue exigiendo `SYNCHRONIZED` y digest observado igual al
   deseado.
7. No se modifica ningún registro `N8N` existente.

### 3.4 `playbook_step_executions`

Proyección mutable y tenant-scoped:

| Columna | Tipo y regla |
|---|---|
| `id` | uuid PK, `gen_random_uuid()` |
| `tenant_id` | uuid NOT NULL, FK `tenants(id)` |
| `execution_id` | uuid NOT NULL |
| `step_id` | varchar(64) NOT NULL |
| `step_type` | varchar(16), `ACTION | CONDITION` |
| `action_code` | varchar(96), obligatorio sólo para `ACTION` |
| `action_version` | varchar(80), obligatorio sólo para `ACTION` |
| `status` | varchar(24), `PENDING | READY | CLAIMED | RUNNING | SUCCEEDED | FAILED | SKIPPED | CANCELLED | UNKNOWN` |
| `input_sha256` | varchar(64), hexadecimal minúscula |
| `result` | jsonb objeto nullable, máximo lógico 64 KiB |
| `error_code` | varchar(80) nullable |
| `claimed_at` | timestamptz nullable |
| `completed_at` | timestamptz nullable |
| `created_at` | timestamptz NOT NULL default `now()` |

Constraints: unique `(tenant_id, execution_id, step_id)`, unique
`(id, tenant_id)` y FK compuesta `(execution_id, tenant_id)` a
`playbook_executions`. Los estados terminales no pueden retroceder; la
aplicación actualiza sólo `status`, `result`, `error_code`, `claimed_at` y
`completed_at` bajo lock de la ejecución.

Índices: `(tenant_id, execution_id, created_at)` y parcial
`(tenant_id, status, created_at)` para estados no terminales.

### 3.5 `playbook_step_attempts`

Hechos append-only:

| Columna | Tipo y regla |
|---|---|
| `id` | uuid PK, `gen_random_uuid()` |
| `tenant_id` | uuid NOT NULL, FK `tenants(id)` |
| `step_execution_id` | uuid NOT NULL |
| `attempt_number` | smallint, entre 1 y 3 |
| `claim_id` | uuid NOT NULL |
| `idempotency_key` | varchar(128) NOT NULL |
| `input_sha256` | varchar(64), hexadecimal minúscula |
| `started_at` | timestamptz NOT NULL |
| `deadline_at` | timestamptz NOT NULL y posterior a `started_at` |
| `created_at` | timestamptz NOT NULL default `now()` |

Constraints: unique `(id, tenant_id)`, `(tenant_id, step_execution_id,
attempt_number)`, `(tenant_id, claim_id)` y `(tenant_id, idempotency_key)`; FK
compuesta al step. No se concede `UPDATE` ni `DELETE` al rol de aplicación.

### 3.6 `playbook_step_attempt_outcomes`

Hechos append-only que permiten conciliación tardía:

| Columna | Tipo y regla |
|---|---|
| `id` | uuid PK, `gen_random_uuid()` |
| `tenant_id` | uuid NOT NULL, FK `tenants(id)` |
| `attempt_id` | uuid NOT NULL |
| `outcome_event_id` | uuid NOT NULL |
| `sequence` | smallint, entre 1 y 32767 |
| `status` | varchar(24), `SUCCEEDED | FAILED | TIMED_OUT | UNKNOWN` |
| `result` | jsonb objeto nullable, máximo lógico 64 KiB |
| `result_sha256` | varchar(64) nullable; obligatorio si hay `result` |
| `error_code` | varchar(80) nullable |
| `safe_detail` | text nullable, máximo 2000 caracteres |
| `occurred_at` | timestamptz NOT NULL |
| `created_at` | timestamptz NOT NULL default `now()` |

Constraints: unique `(id, tenant_id)`, `(tenant_id, outcome_event_id)` y
`(tenant_id, attempt_id, sequence)`; FK compuesta al intento. Se admiten
outcomes posteriores a `UNKNOWN`, pero una proyección terminal exitosa o fallida
no retrocede. No se concede `UPDATE` ni `DELETE` al rol de aplicación.

### 3.7 `native_action_bindings`

Configuración no secreta tenant-scoped:

| Columna | Tipo y regla |
|---|---|
| `id` | uuid PK, `gen_random_uuid()` |
| `tenant_id` | uuid NOT NULL, FK `tenants(id)` |
| `action_code` | varchar(96) NOT NULL |
| `action_version` | varchar(80) NOT NULL |
| `connector_type` | varchar(32), `SIMULATED | HTTP_ALLOWLISTED` |
| `credential_key_id` | varchar(120) nullable; referencia opaca, nunca valor |
| `configuration` | jsonb objeto NOT NULL, sin material secreto |
| `configuration_sha256` | varchar(64), hexadecimal minúscula |
| `active` | boolean NOT NULL default false |
| `created_by_user_id` | uuid NOT NULL |
| `last_verified_at` | timestamptz nullable |
| `created_at` | timestamptz NOT NULL default `now()` |

Constraints: unique `(id, tenant_id)` y `(tenant_id, action_code,
action_version)`. Existe exactamente una configuración seleccionable por acción
y versión dentro del tenant. `HTTP_ALLOWLISTED` exige
`credential_key_id`; `SIMULATED` lo prohíbe. La configuración sólo admite claves
registradas por el conector y rechaza nombres sensibles. No almacena headers de
autorización, tokens, passwords, cookies, certificados privados ni valores de
credenciales.

La aplicación puede insertar y actualizar únicamente `credential_key_id`,
`configuration`, `configuration_sha256`, `active` y `last_verified_at`; no puede
borrar. Toda mutación usa lock, auditoría y comparación del digest previo.

### 3.8 RLS y privilegios

Las cuatro tablas nuevas habilitan y fuerzan RLS con la policy estándar basada
en `app.current_tenant_id`. Todas las FK entre recursos tenant-owned son
compuestas con `tenant_id`.

El rol de aplicación recibe:

- `SELECT, INSERT` y el `UPDATE` columnar descrito para la proyección de steps;
- `SELECT, INSERT` y ningún `UPDATE/DELETE` para attempts y outcomes;
- `SELECT, INSERT` y `UPDATE` columnar para action bindings; ningún `DELETE`.

No se agregan policies permisivas globales ni bypass RLS.

## 4. Contratos de aplicación

### 4.1 `PlaybookEnginePort`

Interfaz asíncrona estable, sin tipos de FastAPI, SQLAlchemy o RabbitMQ:

- `validate(context, version, binding) -> EngineValidationResult`;
- `dry_run(context, version, binding, inputs) -> EngineDryRunResult`;
- `dispatch(context, execution) -> EngineDispatchReceipt`;
- `health(context, binding) -> EngineHealthResult`.

`context` contiene `tenant_id`, `correlation_id`, `causation_id` y deadline.
Los resultados contienen sólo estado tipado, identificadores opacos, digest y
códigos sanitizados. El puerto no recibe valores secretos.

### 4.2 `ActionConnectorPort`

- `describe() -> ActionDescriptor`;
- `validate_configuration(configuration) -> ValidationResult`;
- `probe(context, binding) -> ProbeResult` no destructivo;
- `execute(context, input, idempotency_key, credential_handle) -> ActionResult`.

El `credential_handle` no permite leer/exportar el valor y sólo puede usarse una
vez por el conector autorizado. Cada descriptor fija schemas, impacto, modos,
timeout, retry seguro, egress y campos sensibles.

### 4.3 `CredentialResolverPort`

`resolve(tenant_id, alias, purpose, action_code) -> CredentialHandle` exige
coincidencia de tenant, propósito y acción. La resolución y el fallo se auditan
sin registrar valores.

### 4.4 Runner

El runner valida nuevamente feature flag, tenant, binding, digest, autorización,
modo, deadline y kill switches antes de cada efecto. Persiste claim e intento
antes de invocar el conector. Un timeout sin confirmación produce `UNKNOWN`, no
éxito. Retry usa la misma clave de idempotencia estable por step y sólo ocurre si
el descriptor declara retry seguro.

## 5. API v1 exacta de la primera entrega

Todos los endpoints usan el tenant del contexto autenticado, JSON estricto con
`extra=forbid`, payload máximo 256 KiB salvo ejecución/input máximo 64 KiB, UTC y
UUID. Listas usan `limit` 1..100 (default 25) y `offset` 0..10000 (default 0),
orden descendente por `created_at`, y responden `{items,total}`.

### 5.1 Definiciones y versiones

- `GET /api/v1/playbook-definitions` — `playbook.view`.
- `POST /api/v1/playbook-definitions` — `playbook.author`; body exacto:
  `code` (1..120, slug), `title_i18n.es/en` (1..200),
  `description_i18n.es/en` (1..2000). Responde 201.
- `GET /api/v1/playbook-definitions/{definition_id}` — `playbook.view`.
- `POST /api/v1/playbook-definitions/{definition_id}/versions` —
  `playbook.author`; body `{artifact}` conforme al schema portable v1; calcula
  digest en backend y responde 201 con id, version, estado `DRAFT` y digest.
- `POST /api/v1/playbook-versions/{version_id}/validate` —
  `playbook.review`; body vacío; responde resultado y errores sanitizados.
- `POST /api/v1/playbook-versions/{version_id}/publish` —
  `playbook.publish`; exige `If-Match: <artifact_sha256>`, validación vigente y
  separación de funciones para `HIGH|CRITICAL`; body vacío.
- `POST /api/v1/playbook-versions/{version_id}/dry-run` —
  `playbook.execute`; body `{inputs}` máximo 64 KiB; nunca produce efecto.

Versiones publicadas son inmutables. No hay `PUT`, `PATCH` ni `DELETE` de
versiones en v1.

### 5.2 Acciones y bindings

- `GET /api/v1/playbook-actions` — `playbook.view`; metadatos y schemas sin
  secretos.
- `GET /api/v1/playbook-bindings` — `playbook.view`.
- `POST /api/v1/playbook-bindings` — `automation.binding.manage`; unión
  discriminada por `engine_type`. `NATIVE` acepta exactamente
  `{playbook_version_id,engine_type,instance_code}`. `N8N` acepta exactamente
  `{playbook_version_id,engine_type,instance_code,adapter_workflow_id,`
  `webhook_path,key_id}`. `key_id` es una referencia, nunca el secreto.
- `POST /api/v1/playbook-bindings/{binding_id}/probe` —
  `automation.binding.manage`; body vacío, operación no destructiva.
- `POST /api/v1/native-action-bindings` — `automation.binding.manage`; body
  `{action_code,action_version,connector_type,credential_key_id,configuration}`.
  El valor de la credencial no es un campo válido.

### 5.3 Ejecuciones

Los endpoints existentes de ejecución se conservan. Se agrega:

- `POST /api/v1/playbook-executions/{execution_id}/cancel` —
  `playbook.cancel`; exige `If-Match` con el status observado y sólo acepta una
  cancelación si todos los pasos activos declaran cancelación segura.

La creación continúa mediante una autorización durable y `Idempotency-Key`.
No se habilita un endpoint que ejecute artefactos arbitrarios por ID.

### 5.4 Respuestas y errores

Los recursos exponen IDs, timestamps, estado, engine, modo, impacto, digest,
metadatos i18n y códigos sanitizados. Nunca exponen inputs/outputs marcados
sensibles, aliases resueltos ni configuración secreta.

Errores usan `application/problem+json` con `type`, `title`, `status`, `detail`,
`instance`, `correlation_id` y `error_code`. Códigos iniciales:

- `PLAYBOOK_NOT_FOUND`, `PLAYBOOK_INVALID`, `PLAYBOOK_IMMUTABLE`;
- `PLAYBOOK_DIGEST_MISMATCH`, `PLAYBOOK_REVIEW_SEPARATION_REQUIRED`;
- `PLAYBOOK_BINDING_UNAVAILABLE`, `PLAYBOOK_BINDING_DRIFTED`;
- `PLAYBOOK_ENGINE_DISABLED`, `PLAYBOOK_LIVE_DISABLED`;
- `PLAYBOOK_ACTION_UNAVAILABLE`, `PLAYBOOK_ACTION_CONFIG_INVALID`;
- `PLAYBOOK_CREDENTIAL_UNAVAILABLE`, `PLAYBOOK_EGRESS_DENIED`;
- `PLAYBOOK_IDEMPOTENCY_CONFLICT`, `PLAYBOOK_STATE_CONFLICT`;
- `PLAYBOOK_PAYLOAD_TOO_LARGE`, `PLAYBOOK_DEADLINE_EXCEEDED`.

No se incluyen SQL, stack traces, URLs con query, headers ni detalles de
credenciales.

## 6. Permisos y separación de funciones

Se crean exactamente:

- `playbook.view`, `playbook.author`, `playbook.review`, `playbook.publish`;
- `playbook.execute`, `playbook.cancel`;
- `automation.credential.prepare`, `automation.live.enable`.

Se conservan `playbook.release`, `playbook.execution.read`, `response.execute`,
`response.cancel`, `automation.binding.manage` y `automation.reconcile` por
compatibilidad. Durante la transición:

- lectura acepta `playbook.view` o el permiso histórico equivalente;
- crear una ejecución autorizada sigue exigiendo `response.execute` y además
  policy habilitada; `playbook.execute` no salta la autorización;
- cancelación exige `playbook.cancel` o `response.cancel`;
- `automation.live.enable` nunca basta por sí solo y v1 sigue rechazando LIVE.

Los permisos nuevos se asignan sólo a `tenant-admin` por la migración. La
delegación a otros roles queda como operación administrativa auditada.

## 7. Eventos v1

Se publican por outbox, con el envelope aprobado de Fase 15:

- `security.playbook_version.validated` v1;
- `security.playbook_version.published` v1;
- `security.playbook_binding.probed` v1;
- `security.native_playbook.dispatch_requested` v1;
- `security.playbook_step.claimed` v1;
- `security.playbook_step.completed` v1;
- `security.playbook_execution.completed` v1.

Payload común exacto: `tenant_id`, `resource_id`, `occurred_at`, `status`,
`correlation_id`, `causation_id`. Cada evento puede agregar sólo IDs de recursos,
`engine_type`, `action_code`, `action_version`, `step_id`, `sequence`, digest y
`error_code` sanitizado. Se prohíben artefactos, inputs, outputs, configuración,
aliases y valores de credenciales.

## 8. Configuración y activación

- `PLAYBOOK_NATIVE_ENGINE_ENABLED=true` por defecto.
- `N8N_ENABLED=false` por defecto; n8n se habilita globalmente y luego mediante
  un binding explícito por playbook.
- `PLAYBOOK_NATIVE_ENABLED_TENANTS` vacío significa todos los tenants; cuando
  contiene IDs actúa como allowlist más restrictiva.
- La ejecución efectiva exige autorización durable, tenant permitido, binding
  activo/sincronizado, action bindings verificados y kill switches abiertos.
- `PLAYBOOK_LIVE_ENABLED=false` permanece obligatorio en v1.
- La configuración normal de n8n contiene únicamente interruptor, URL y API key
  write-only. Dispatch/callback se generan y rotan mediante
  `DeploymentSecretStorePort`, permanecen en la sección avanzada y sólo exponen
  presencia, versión y fecha de rotación.
- Ningún secreto guardado vuelve a mostrarse. API y UI sólo permiten reemplazar,
  probar o rotar; toda operación se audita sin valores.
- El adaptador local cifra en reposo con una clave maestra de instalación fuera
  de Git. Un gestor externo puede sustituirlo por puerto/adaptador.
- La configuración se valida al arrancar; un valor inválido falla cerrado.

## 9. Auditoría

Cada creación, validación, publicación, binding, probe, dry-run, activación,
dispatch, claim, intento, outcome, retry, timeout, cancelación y conciliación
genera auditoría tenant-scoped. La entrada contiene actor/servicio, recurso,
acción, outcome, UTC, correlation/causation y IDs relacionados; aplica redacción
estructural y nunca registra payloads sensibles o valores de credenciales.

## 10. Pruebas de aceptación

La entrega no se considera completa hasta ejecutar y conservar evidencia de:

1. upgrade/downgrade en base vacía y rechazo del downgrade con historia;
2. RLS real cross-tenant para las cuatro tablas y FK compuestas;
3. rol de aplicación sin update/delete sobre attempts/outcomes;
4. constraints condicionales `NATIVE | N8N` y preservación de filas n8n;
5. schema, DAG, digest, tamaño, campos extra, secretos y código arbitrario;
6. separación autor/revisor/publicador y permisos backend;
7. E2E `SIMULATED` con PostgreSQL, RabbitMQ y worker reales;
8. claim previo al efecto, idempotencia, retry seguro y deadline;
9. crash/restart, DLQ, timeout ambiguo `UNKNOWN` y outcome tardío;
10. SSRF/egress, redacción y ausencia de secretos en logs/eventos/API/UI;
11. kill switch global, tenant y binding, todos fail-closed;
12. paridad contractual `NATIVE`/`N8N` sin doble efecto.

## 11. Rollout y rollback

Rollout: migración con `LIVE` y n8n apagados, simuladores, tenant de prueba,
shadow/dry-run, un binding predefinido por vez y evidencia antes de ampliar. n8n
permanece en el perfil Docker opcional `automation`.

Rollback operativo: cerrar kill switch, detener nuevos dispatch nativos,
conciliar ejecuciones no terminales y cambiar futuros bindings a `N8N` mediante
operación auditada. La migración sólo puede revertirse cuando las cuatro tablas
nuevas están vacías y no existe binding `NATIVE`; si hay evidencia, el downgrade
aborta. Nunca elimina historia, DLQ, auditoría, secretos ni volúmenes n8n.

## 12. Decisiones ratificadas

1. alcance SIMULATED de la primera entrega;
2. migración y evolución condicional del binding;
3. evolución de versiones y cuatro tablas con columnas, constraints, índices y
   privilegios exactos;
4. RLS forzado y FK compuestas tenant-scoped;
5. puertos y semántica de runner exactos;
6. endpoints, DTO, paginación, concurrencia y errores exactos;
7. permisos nuevos y compatibilidad con permisos históricos;
8. eventos y allowlist de payload exactos;
9. feature flags y activación por tenant/binding;
10. auditoría y redacción;
11. pruebas de aceptación;
12. rollout y rollback.

## 13. GATE

Superado por ratificación humana explícita el 2026-08-01. Se autorizan la
migración 0020, API, eventos, puertos y motor nativo conforme a este contrato y
ADR 0018. `LIVE` conserva una aprobación operativa separada.

