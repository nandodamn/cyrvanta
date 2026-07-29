# Fase 21 — Playbooks versionados y ejecución n8n segura

**Etapa estratégica:** 7
**Estado:** DRAFT — propuesta para revisión humana
**Fecha:** 2026-07-29
**Implementación autorizada:** no

## 1. Objetivo

Definir cómo Cyrvanta registra, publica y ejecuta playbooks versionados mediante
un adaptador n8n reemplazable, consumiendo de forma atómica las autorizaciones
de Etapa 6 y conservando en PostgreSQL el estado autoritativo de ejecución.

La etapa debe permitir una demostración real, reproducible y no destructiva sin
confundir aceptación, dispatch, ejecución y resultado final. Ningún workflow,
callback, ID de n8n o respuesta HTTP puede otorgar autorización.

## 2. Alcance

Incluye:

- definiciones y versiones inmutables de playbook;
- artefactos n8n JSON versionados en Git;
- manifest, schemas, fixtures, validadores y pruebas;
- reconciliación idempotente import/diff/update/deactivate;
- binding entre playbook lógico y workflow instalado;
- consumo único de autorización y creación durable de ejecución;
- dispatch asíncrono mediante outbox/worker;
- claim previo a cualquier efecto externo;
- callback autenticado, anti-replay e idempotente;
- estados, intentos, resultados y errores redactados;
- cinco workflows iniciales;
- catálogo de conectores sin valores de credenciales;
- UI bilingüe de playbooks y ejecuciones;
- permisos, RLS, auditoría, métricas y rollback.

No incluye:

- ejecución automática habilitada por defecto;
- acciones ofensivas;
- comandos shell, SSH o código de sistema;
- contención real de usuarios, endpoints o red en la demo;
- gestión de secretos dentro de Git o PostgreSQL;
- acceso directo de React a n8n;
- alta disponibilidad de n8n;
- proveedor concreto obligatorio para tickets, correo o identidad;
- sustitución de PostgreSQL por el historial de n8n;
- aprobación humana dentro de n8n.

## 3. Documentos rectores

- `docs/foundation/*`;
- `docs/specifications/PHASE_15_EVENT_DELIVERY_TRACEABILITY.md`;
- `docs/specifications/PHASE_20_SAFE_DECISION_APPROVAL.md`;
- `docs/requirements/N8N_WORKFLOWS_AS_CODE_REQUIREMENTS.md`;
- `docs/runbooks/N8N_PLAYBOOK_ADMINISTRATION.md`;
- ADR 0014;
- envelope `EventEnvelopeV1`, outbox/inbox y retry existentes.

Etapas 5 y 6 están implementadas. Esta especificación no modifica sus outputs:
riesgo y claims son evidencia. Una `action_authorization` vigente es la única
capacidad que puede iniciar una acción de respuesta. La notificación técnica de
una solicitud de aprobación constituye una excepción acotada y se define en la
sección 10.

## 4. Estado actual y brecha

Existe:

- n8n `1.123.65` fijado y publicado solo en loopback;
- un workflow sintético importado al arranque;
- allowlist de workflow IDs;
- catálogo backend read-only;
- acceso al editor documentado;
- modos `disabled`, `simulated` y `live`;
- kill switch;
- autorización durable de Etapa 6;
- outbox, inbox, retry y DLQ.

La solución provisional no es apta para modo `live` porque:

- el JSON no autentica ni valida el request;
- no existe modelo durable de playbook, versión o ejecución;
- el ID fijo de n8n no es portable;
- no se consume la autorización;
- no existe claim previo al efecto;
- no existe callback autenticado;
- no hay protección durable contra replay;
- la respuesta inmediata puede parecer resultado final;
- no existen scripts de reconciliación ni validadores;
- el workflow no conserva una relación verificable con el artefacto Git;
- la idempotencia actual no resiste concurrencia o reinicio.

La auditoría también detectó que Etapa 6 tenía declarados pero no emitía todos
los eventos de creación de solicitud, evaluación, emisión y revocación. Esa
omisión se corrige antes de Etapa 7. La transición y evento periódico
`security.authorization.expired` permanece como prerrequisito del scheduler de
esta etapa; el chequeo sincrónico de `expires_at` continúa fallando cerrado.

## 5. Principios obligatorios

1. Deny-by-default y modo automático deshabilitado.
2. PostgreSQL es sistema de registro.
3. n8n es un adaptador reemplazable y no una autoridad de negocio.
4. Tenant, actor y autorización proceden de contexto seguro.
5. El navegador nunca llama n8n para ejecutar.
6. Toda ejecución referencia una versión inmutable y aprobada.
7. Autorización y ejecución deben coincidir por fingerprint.
8. La autorización se consume una sola vez y dentro de la transacción que crea
   la ejecución.
9. Un ACK de n8n significa `DISPATCHED`, nunca `SUCCEEDED`.
10. Ningún efecto comienza antes de un claim durable en Cyrvanta.
11. Replays y callbacks duplicados no repiten efectos.
12. Secretos y valores de credenciales nunca se versionan ni se reflejan.
13. Toda falla ambigua permanece visible; no se fabrica éxito.
14. Los workflows demo permanecen inequívocamente `demo` o `synthetic`.
15. Kill switches se reevalúan antes de consumir, despachar y reclamar.
16. Una notificación de sistema no puede reutilizarse para ejecutar una acción
    de respuesta.

## 6. Lenguaje de dominio candidato

### 6.1 Definición de playbook

Identidad lógica tenant-owned y estable, independiente de n8n. Expresa propósito,
action type y estado general. No contiene nodos, secretos ni un ID instalado.

### 6.2 Versión de playbook

Snapshot inmutable que contiene:

- código y versión semántica;
- action type e impacto mínimo;
- modos admitidos;
- schema de inputs y schema de resultado;
- rollback o compensación;
- límites de timeout y targets;
- código de workflow y digest SHA-256 del artefacto;
- tipo y versión del adaptador;
- clasificación `demo`, `synthetic` o `live`;
- estado `DRAFT`, `APPROVED` o `RETIRED`;
- actor, fecha y motivo de aprobación.

Editar contenido crea una nueva versión. Aprobar una versión no habilita
ejecución automática.

### 6.3 Binding de workflow

Mapeo tenant-owned entre una versión de playbook y una instalación de motor de
automatización. Conserva el ID opaco asignado por n8n, project/instance
autorizado, digest observado, estado de sincronización y última verificación.

El ID de n8n nunca forma parte de la identidad portable del playbook.

### 6.4 Ejecución de playbook

Agregado tenant-owned creado al consumir una autorización. Fija:

- autorización, propuesta, incidente y playbook/version;
- origen `AUTHORIZED_RESPONSE` o `SYSTEM_NOTIFICATION`;
- fingerprint autorizado;
- modo y clasificación;
- inputs ya validados;
- idempotency key;
- correlation y causation IDs;
- estado, deadlines y resultado final.

### 6.5 Intento de dispatch

Registro append-only de cada intento técnico de entregar una ejecución al
adaptador. Un retry no crea otra ejecución.

### 6.6 Claim de efecto

Transición atómica y de un solo ganador por ejecución. n8n debe obtenerla de
Cyrvanta antes de notificar, crear un ticket o invocar un conector. Un replay
recibe `duplicate` y no vuelve a efectuar la acción.

### 6.7 Actualización de ejecución

Hecho autenticado e idempotente emitido por el adaptador. Puede registrar
`RUNNING`, `SUCCEEDED` o `FAILED`, pero no reabrir un estado terminal.

## 7. Ownership y topología multitenant candidata

1. Definiciones, versiones, bindings y ejecuciones son tenant-owned.
2. Un binding referencia una única instancia lógica de automatización.
3. El mismo artefacto Git puede instalarse para varios tenants, pero cada
   binding y credencial es independiente.
4. En demo se admite una instancia n8n compartida solo para workflows
   sintéticos sin secretos de clientes.
5. Para acciones `live`, cada tenant debe usar una instancia o project de n8n
   con aislamiento administrativo verificable. Si la edición instalada no
   ofrece ese aislamiento, se requiere instancia dedicada por tenant.
6. El backend verifica tenant en binding, autorización, propuesta, incidente y
   ejecución mediante RLS y claves compuestas.
7. Ningún callback acepta `tenant_id` como autoridad. El tenant se resuelve
   desde la ejecución identificada y autenticada.

## 8. Modelo lógico y físico candidato

Se proponen seis conceptos persistentes:

1. `playbook_definitions`;
2. `playbook_versions`;
3. `automation_engine_bindings`;
4. `playbook_executions`;
5. `playbook_execution_attempts`;
6. `playbook_execution_updates`.

Además se requiere un registro técnico de nonces/firma para anti-replay. No es
un agregado de negocio y tiene retención corta y cleanup programado.

Todas las tablas operativas incluyen UUID, `tenant_id`, timestamps UTC, RLS
habilitada y forzada. Las relaciones tenant-owned usan FK compuestas.

Invariantes candidatas:

- definición única por `(tenant_id, code)`;
- versión única por `(tenant_id, definition_id, version)`;
- una versión aprobada es inmutable;
- digest de artefacto hexadecimal SHA-256;
- un binding activo por versión e instancia;
- ejecución única por `(tenant_id, authorization_id)`;
- ejecución única por `(tenant_id, idempotency_key)`;
- `authorization_id` es obligatorio para `AUTHORIZED_RESPONSE` y nulo para
  `SYSTEM_NOTIFICATION`;
- una notificación referencia un event ID allowlisted y único;
- authorization ID, proposal ID y fingerprint coinciden;
- intentos y updates son append-only;
- update único por `(tenant_id, execution_id, adapter_event_id)`;
- número de secuencia creciente por ejecución;
- un solo claim de efecto;
- estados terminales no pueden revertirse;
- resultado JSON es objeto y no excede el límite;
- errores conservan código estable, no texto sensible.

La migración propuesta debe extender `action_authorizations` únicamente con las
invariantes mínimas para consumo atómico; no debe fabricar ejecuciones
históricas.

## 9. Estados candidatos

Ejecución:

```text
QUEUED
  -> DISPATCHING
  -> DISPATCHED
  -> RUNNING
  -> SUCCEEDED | FAILED | TIMED_OUT | CANCELLED
```

Reglas:

- `QUEUED`: autorización consumida y outbox confirmado en la misma transacción.
- `DISPATCHING`: existe un intento con lease.
- `DISPATCHED`: el workflow recibió el request y el claim autenticado fue
  aceptado; no hay resultado todavía.
- `RUNNING`: claim de efecto concedido.
- `SUCCEEDED`: callback terminal válido y resultado conforme al schema.
- `FAILED`: callback terminal válido o error permanente anterior al efecto.
- `TIMED_OUT`: deadline vencido sin resultado terminal verificable.
- `CANCELLED`: solo antes del claim; después se registra compensación.

`TIMED_OUT` no presupone que el efecto no ocurrió. Una actualización tardía se
conserva para conciliación humana y no cambia el estado automáticamente.

## 10. Orígenes y consumo candidato

### 10.1 Acción de respuesta autorizada

En una transacción tenant-scoped:

1. bloquear autorización, propuesta, policy y playbook version;
2. verificar `ACTIVE`, expiración, revocación y `consumed_at IS NULL`;
3. recalcular policy, kill switches, incidente/version, binding, workflow
   digest, inputs, targets y fingerprint;
4. comprobar `response.execute`;
5. marcar autorización consumida;
6. crear ejecución `QUEUED`;
7. registrar audit event;
8. registrar `security.playbook_execution.dispatch_requested` en outbox;
9. confirmar todo o revertir todo.

No se entrega una autorización como bearer token al navegador o a n8n.

### 10.2 Notificación de sistema

La única excepción inicial sin `action_authorization` es
`request-dual-approval`. Se origina al consumir
`security.approval.requested` mediante inbox y crea una ejecución durable con:

- origen `SYSTEM_NOTIFICATION`;
- event ID y approval request ID;
- playbook/version allowlisted y aprobado;
- destinatario por alias configurado;
- URL de Cyrvanta construida desde base allowlisted;
- inputs mínimos, sin motivo humano, evidencia o parámetros de respuesta;
- outbox de dispatch en la misma transacción.

No usa `response.execute`, no puede seleccionar otro workflow y no puede
alcanzar nodos de contención o ticketing. El mismo event ID no crea dos
notificaciones. Todas las demás ejecuciones iniciales requieren autorización.
Ampliar esta excepción exige una nueva especificación aprobada.

## 11. Dispatch y entrega candidata

1. El worker consume el evento desde RabbitMQ con inbox.
2. Reclama la ejecución mediante lease.
3. Resuelve el binding tenant-scoped.
4. Construye el envelope de dispatch canónico.
5. Firma y envía al webhook allowlisted.
6. Valida límite, status HTTP y ACK schema.
7. Registra intento y estado `DISPATCHED`.
8. Ante error transitorio usa los retries `5`, `30`, `300` segundos existentes.
9. Tras agotar retries marca `FAILED` con código redactado y conserva DLQ.

El webhook path procede del binding aprobado, no de input del usuario. No se
admiten redirects ni URLs fuera de la instancia registrada.

## 12. Claim previo al efecto candidato

El primer paso operativo de todos los workflows es un HTTP Request interno a
Cyrvanta que presenta el dispatch original y la identidad de servicio n8n.

Cyrvanta:

1. valida autenticación y firma del dispatch;
2. resuelve ejecución y tenant;
3. verifica estado, digest, deadline y kill switches;
4. compara fingerprint e inputs;
5. reclama atómicamente el efecto;
6. responde `proceed` una sola vez o `duplicate/denied`.

Los nodos con efectos externos sólo son alcanzables desde la rama `proceed`.
Este claim no equivale a éxito y no concede permisos fuera de la ejecución.

## 13. Envelope de dispatch candidato

Media type: `application/json`.
Schema version: entero `1`.
Tamaño máximo serializado: `65536` bytes.
Campos desconocidos: rechazados.

```json
{
  "schema_version": 1,
  "dispatch_id": "uuid",
  "execution_id": "uuid",
  "authorization_id": "uuid-or-null",
  "proposal_id": "uuid",
  "incident_id": "uuid",
  "playbook_code": "simulate-user-block",
  "playbook_version": "1.0.0",
  "workflow_code": "simulate-user-block",
  "action_type": "simulate-user-block",
  "execution_mode": "demo",
  "proposal_fingerprint": "sha256-hex",
  "correlation_id": "uuid",
  "causation_id": "uuid",
  "issued_at": "UTC RFC3339",
  "expires_at": "UTC RFC3339",
  "inputs": {}
}
```

`authorization_id` sólo puede ser nulo para la notificación de sistema aprobada.
`tenant_id` no se duplica en el body. Se resuelve desde la ejecución. No se
incluyen evidencia raw, aprobadores, motivos, secretos o credenciales.

## 14. ACK de dispatch candidato

Respuesta n8n máxima: `4096` bytes.

```json
{
  "schema_version": 1,
  "execution_id": "uuid",
  "adapter_execution_id": "opaque-string",
  "status": "accepted",
  "received_at": "UTC RFC3339"
}
```

Sólo `accepted` es válido. Cualquier `completed`, `success` o body libre en el
ACK se rechaza para evitar falso éxito.

## 15. Callback candidato

Ruta interna candidata:

```text
POST /api/v1/internal/playbook-execution-updates
```

No se publica al navegador ni a la LAN. Requiere identidad de servicio y firma.
Tamaño máximo: `32768` bytes.

```json
{
  "schema_version": 1,
  "adapter_event_id": "uuid",
  "execution_id": "uuid",
  "adapter_execution_id": "opaque-string",
  "sequence": 1,
  "status": "running",
  "occurred_at": "UTC RFC3339",
  "result": {},
  "error": null
}
```

Estados permitidos: `running`, `succeeded`, `failed`.
`error` contiene como máximo `code`, `retryable` y `safe_detail` acotado a 500
caracteres. Stack traces, responses completas y secretos se descartan.

Un callback duplicado devuelve el resultado idempotente. Un callback con mismo
ID y contenido distinto se rechaza y genera alerta de seguridad.

## 16. Autenticación y canonicalización candidatas

Se proponen dos claves independientes por instancia:

- `dispatch` para Cyrvanta → n8n;
- `callback` para n8n → Cyrvanta.

Los secretos se inyectan por entorno/secret manager y se referencian mediante
`key_id`; nunca se guardan en Git ni en tablas de negocio.

Headers:

```text
X-Cyrvanta-Key-Id
X-Cyrvanta-Timestamp
X-Cyrvanta-Nonce
X-Cyrvanta-Signature
```

Firma HMAC-SHA256 en hexadecimal minúsculo sobre:

```text
v1\n
METHOD\n
normalized_path\n
unix_timestamp_seconds\n
nonce_uuid\n
sha256_hex_of_exact_body_bytes
```

Reglas:

- comparación constant-time;
- path sin query, percent-encoding normalizado y sin redirects;
- tolerancia de reloj: ±120 segundos;
- nonce UUID único, retenido 10 minutos;
- key IDs activos y anterior durante rotación máxima de 24 horas;
- nunca se reutiliza la misma key en ambas direcciones;
- en producción se exige TLS o mTLS además de HMAC;
- en demo la red interna y HMAC son obligatorias; no se permite callback
  anónimo.

Nonces, key ID, dirección y digest del body se registran en una tabla técnica
durable con expiración; Redis puede acelerar la consulta, pero no ser la única
protección anti-replay.

## 17. Idempotencia candidata

Capas:

1. `Idempotency-Key` del comando de ejecución: máximo 128 caracteres y unique
   por tenant;
2. authorization ID: una ejecución;
3. outbox/inbox: entrega al menos una vez sin duplicar handler;
4. dispatch ID: un intento identificable;
5. claim: un efecto por ejecución;
6. adapter event ID: un update;
7. idempotency key del proveedor externo cuando exista.

Si el proveedor no ofrece idempotencia, la ejecución queda limitada a una
acción cuyo claim se concedió una sola vez. Un timeout posterior se presenta
como estado ambiguo y requiere conciliación, nunca retry ciego del efecto.

## 18. Límites y timeouts candidatos

- dispatch body: 64 KiB;
- callback body: 32 KiB;
- ACK: 4 KiB;
- result JSON: 16 KiB;
- 32 campos de input;
- 32 referencias de resultado;
- strings: 1.000 caracteres salvo límites menores del schema;
- dispatch HTTP: 10 segundos;
- claim HTTP: 10 segundos;
- callback HTTP: 10 segundos;
- ejecución por defecto: 15 minutos;
- máximo configurable: 60 minutos;
- 8 updates por ejecución;
- 10 intentos técnicos totales incluyendo conciliación;
- reloj ±120 segundos;
- nonce 10 minutos.

Exceder un límite falla cerrado con código estable y auditoría.

## 19. Workflows iniciales candidatos

### 19.1 `notify-critical-incident`

- impacto `OBSERVATIONAL`;
- correo SMTP HTML y texto;
- locale `es` o `en`;
- destinatario seleccionado por alias allowlisted, nunca dirección libre;
- asunto y body renderizados desde campos tipados;
- demo usa sink/mailbox de laboratorio;
- callback de éxito o error.

### 19.2 `create-security-ticket`

- impacto `OBSERVATIONAL` o `LOW` según configuración;
- adaptador HTTP genérico tipado;
- sin nombres Jira/ServiceNow en el contrato;
- provider idempotency key obligatorio cuando esté disponible;
- guarda referencia externa y URL validada, no credenciales.

### 19.3 `request-dual-approval`

- sólo notifica que existe una solicitud en Cyrvanta;
- es la única ejecución inicial con origen `SYSTEM_NOTIFICATION`;
- enlace allowlisted a la UI de Cyrvanta;
- no recibe ni crea decisiones;
- no cuenta quorum ni emite autorización;
- resultado significa notificación entregada, no aprobación.

### 19.4 `simulate-user-block`

- impacto `MODERATE`;
- exclusivamente `demo`;
- sin conector de identidad;
- resultado exacto:

```json
{
  "execution_mode": "demo",
  "action": "block_user",
  "result": "simulated_success"
}
```

### 19.5 `incident-report-email`

- impacto `OBSERVATIONAL`;
- usa un snapshot minimizado producido por Cyrvanta;
- separa hechos, inferencias, ATT&CK, riesgo, recomendaciones, decisiones,
  acciones y resultados;
- no incluye evidencia raw ni PII no necesaria;
- locale explícito y destinatario por alias.

## 20. Nodos y expresiones candidatas

Allowlist inicial:

- Webhook;
- Respond to Webhook;
- HTTP Request;
- IF;
- Switch;
- Edit Fields/Set;
- Merge;
- Crypto;
- Send Email;
- Date & Time;
- No Operation;
- Stop And Error.

Prohibidos:

- Execute Command;
- SSH;
- Code/Function;
- Read/Write Files;
- Git;
- nodos de base de datos;
- subworkflows no registrados;
- instalación de community nodes;
- cualquier nodo capaz de ejecutar sistema, script o expresión dinámica no
  revisada.

Las expresiones estáticas del artefacto pueden leer campos allowlisted y
formatear valores. El validador rechaza referencias a entorno, secretos,
filesystem, procesos, constructores, evaluación dinámica y expresiones
provenientes del payload.

## 21. Credenciales y conectores candidatos

- Los JSON no contienen credential IDs ni valores.
- Cada workflow declara aliases lógicos de credencial en su manifest.
- El reconciliador resuelve aliases contra configuración externa del entorno.
- Cyrvanta sólo muestra alias, tipo, estado configurado/no configurado y fecha
  de prueba; nunca el ID interno ni el valor.
- Cada cuenta de servicio usa mínimo privilegio.
- Toda credencial real requiere una prueba no destructiva antes de activar un
  binding `live`.
- Rotar una credencial no crea una nueva versión del playbook si el contrato y
  digest no cambian; sí genera auditoría de integración.

Conectores iniciales:

- SMTP/sink de correo;
- HTTP ticketing;
- notificación de aprobación;
- simulador sin credenciales;
- futuros identity/EDR/firewall sólo tras especificación propia.

## 22. Layout como código candidato

```text
infrastructure/n8n/
├── README.md
├── manifest.json
├── workflows/
│   ├── notify-critical-incident.json
│   ├── create-security-ticket.json
│   ├── request-dual-approval.json
│   ├── simulate-user-block.json
│   └── incident-report-email.json
├── schemas/
│   ├── manifest.schema.json
│   ├── dispatch.schema.json
│   ├── callback.schema.json
│   └── results/
├── scripts/
│   ├── reconcile.ps1
│   └── reconcile.py
├── fixtures/
│   ├── valid/
│   └── invalid/
└── tests/
```

El archivo provisional `cyrvanta-demo-response.json` se conserva durante una
ventana de compatibilidad, se marca `legacy`, no se habilita en `live` y se
retira sólo después de validar `simulate-user-block`.

## 23. Manifest candidato

Cada entrada declara:

- workflow code y display name;
- artifact path y SHA-256;
- schema version;
- playbook version;
- action type e impacto;
- clasificación;
- input/result schema paths;
- credential aliases;
- allowed node types;
- timeout;
- estado deseado `active` o `inactive`;
- fecha de retiro opcional.

El digest se calcula sobre JSON canónico sin IDs efímeros de instalación. El
manifest y el artefacto deben coincidir antes de importar.

## 24. Reconciliación candidata

Los scripts PowerShell y Python implementan la misma semántica:

1. health check;
2. validar manifest, schemas, artefactos, nodos y ausencia de secretos;
3. consultar API pública n8n;
4. identificar recursos mediante tags administrados, nunca sólo por nombre;
5. mostrar diff redactado;
6. crear si no existe;
7. actualizar si cambió digest;
8. no duplicar si coincide;
9. desactivar recursos administrados retirados;
10. nunca borrar automáticamente;
11. verificar importación y registrar evidencia local sin API key;
12. retornar exit code no cero ante divergencia o error.

Configuración:

- `N8N_BASE_URL`: URL interna usada por backend/worker;
- `N8N_EDITOR_URL`: URL local mostrada a administradores;
- `N8N_API_URL`: URL host usada exclusivamente por scripts.

No son fuentes duplicadas porque pertenecen a topologías distintas. En un mismo
proceso no se aceptan dos URLs para el mismo propósito. Si `N8N_API_URL` se
omite, el script requiere parámetro explícito; no deriva silenciosamente una URL
inaccesible desde `N8N_BASE_URL`.

`N8N_API_KEY` se lee de entorno/secret store, nunca de argumentos, logs, diff o
archivos versionados.

## 25. API candidata

Recursos de usuario bajo `/api/v1`:

- listar/consultar definiciones y versiones;
- registrar una versión desde artefacto validado;
- aprobar o retirar una versión;
- listar bindings y estado de sincronización;
- iniciar ejecución desde una authorization ID;
- consultar/listar ejecuciones paginadas;
- cancelar antes del claim;
- solicitar conciliación.

Recursos internos:

- claim de efecto;
- callback/update;
- health/binding probe acotado.

Todos los comandos de usuario requieren `Idempotency-Key` y expected version
cuando corresponda. Los IDs ajenos responden `404`. Los endpoints internos no
usan cookies de usuario y exigen identidad de servicio + HMAC.

Paths, DTO, status codes y error codes quedan como candidatos hasta aprobación.

## 26. Eventos candidatos

- `security.playbook_version.registered` v1;
- `security.playbook_version.approved` v1;
- `security.playbook_binding.synchronized` v1;
- `security.playbook_execution.dispatch_requested` v1;
- `security.playbook_execution.dispatched` v1;
- `security.playbook_execution.running` v1;
- `security.playbook_execution.completed` v1;
- `security.playbook_execution.failed` v1;
- `security.playbook_execution.timed_out` v1.

Usan `EventEnvelopeV1`. Payloads contienen IDs, códigos, versiones, digest,
status y error code; no inputs, resultados completos, emails, secretos o
evidencia raw.

## 27. Permisos candidatos

- `playbook.read`;
- `playbook.manage`;
- `playbook.release`;
- `playbook.execution.read`;
- `response.execute`;
- `response.cancel`;
- `automation.binding.manage`;
- `automation.reconcile`.

Separación:

- gestionar JSON/binding no aprueba una acción;
- aprobar una versión no aprueba una ejecución;
- una versión `live` requiere revisor con `playbook.release` distinto del actor
  que registró el artefacto; la demo sintética puede usar tenant-admin y queda
  rotulada;
- aprobar una acción no concede `response.execute`;
- el tenant-admin demo puede ejercitar todo sólo con datos sintéticos;
- platform-admin no obtiene acceso tenant implícito;
- identidad n8n sólo puede claim/update sobre ejecuciones de su binding.

## 28. Auditoría

Se auditan:

- registro, aprobación y retiro de versión;
- digest y resultado de validación;
- alta/cambio/desactivación de binding;
- diff y reconciliación;
- consumo o rechazo de autorización;
- creación, dispatch, retry, claim y terminación;
- callback inválido, replay, nonce duplicado y firma fallida;
- cancelación, timeout y conciliación;
- cambio de kill switch;
- acceso al editor n8n;
- prueba de credencial/conector sin registrar secretos.

Audit conserva IDs, códigos, digest, actor, tenant, correlation y outcome. No
duplica inputs sensibles, resultados completos o headers de autenticación.

## 29. UI e i18n

La UI debe:

- distinguir catálogo Cyrvanta de instalación n8n;
- mostrar playbook/version, digest, clasificación y aprobación;
- mostrar binding `synchronized`, `drifted`, `missing`, `retired` o
  `unavailable`;
- mostrar conectores por alias y estado, nunca secretos;
- ofrecer buscador, filtros y paginación;
- mostrar timeline de ejecución y separar dispatch de resultado;
- rotular demo/synthetic/live;
- mostrar expiración, retry, timeout y conciliación;
- abrir editor sólo a `playbook.manage` y sólo mediante URL administrativa
  configurada;
- funcionar en español e inglés y con alternativa textual accesible.

## 30. Observabilidad

Métricas mínimas:

- versiones registradas/aprobadas/retiradas;
- bindings por estado y drift;
- ejecuciones por action type, modo y estado;
- latencia autorización→dispatch→claim→terminal;
- retries, timeouts y conciliaciones;
- callbacks inválidos/replay/firma;
- claims concedidos/duplicados/denegados;
- resultados por error code;
- edad de ejecución no terminal.

No usar tenant, user, incident, execution o adapter IDs como labels.

## 31. Pruebas obligatorias

### Dominio

- versión aprobada inmutable;
- digest reproducible;
- state machine válida e inválida;
- autorización consumida una vez;
- fingerprint mismatch deniega;
- ACK no implica éxito;
- terminal no se reabre.

### Schemas y workflow

- JSON/schema y conexiones válidas;
- manifest/digest coinciden;
- no secretos ni credential IDs;
- sólo nodos/expresiones allowlisted;
- todos los paths de efecto dependen de claim `proceed`;
- cinco workflows cumplen sus schemas;
- `simulate-user-block` retorna exactamente el resultado aprobado.

### Seguridad

- firma válida/inválida, body alterado y key desconocida;
- timestamp fuera de ventana;
- nonce repetido;
- callback duplicado igual/diferente;
- redirect, path o host no allowlisted;
- inputs, results y errores sobredimensionados;
- workflow/nodo peligroso;
- logs y audit sin secretos.

### Persistencia y multitenancy

- negocio + consumo + ejecución + outbox confirman o revierten juntos;
- Tenant A no ve, ejecuta, reclama o actualiza recursos de B;
- binding cross-tenant falla por FK/RLS;
- claim concurrente concede un ganador;
- retries no crean otra ejecución;
- callback concurrente no duplica terminal;
- rol n8n no tiene SELECT libre.

### Adaptador y reconciliación

- health, import, diff, update, no-op y retire;
- importación repetida no duplica;
- drift detectado;
- API key ausente o n8n caído falla explícitamente;
- evidencia real de workflows instalados;
- ACK, callback success/error y timeout;
- provider sin idempotencia no recibe retry ciego.

### Frontend y E2E

- listas acotadas, filtros e i18n;
- permisos backend aunque botón esté oculto;
- propuesta → aprobación → autorización → ejecución demo → resultado;
- approval requested → notificación durable sin autorización → enlace a
  Cyrvanta;
- auditoría reconstruye correlation/causation;
- caída de n8n no muestra éxito.

## 32. Migración candidata

Después de aprobación:

1. crear tablas, constraints, índices y RLS;
2. extender consumo de autorización con compare-and-set;
3. implementar expiración durable y evento aprobado de autorizaciones;
4. sembrar permisos y cinco definiciones/versiones sintéticas;
5. implementar dominio, repositorios y API;
6. implementar adaptador, firma, replay y callback;
7. crear layout, schemas, validators, scripts y fixtures;
8. importar primero workflows inactivos;
9. ejecutar contract/security tests;
10. activar sólo workflows demo aprobados;
11. ejecutar E2E sintético;
12. retirar gradualmente endpoint `approved: bool` y workflow legacy;
13. mantener `live` deshabilitado hasta evidencia y aprobación operativa.

## 33. Rollback

- activar kill switch y detener nuevos consumos;
- desactivar workflows administrados sin borrarlos;
- permitir finalizar o conciliar ejecuciones reclamadas;
- no devolver autorizaciones consumidas a `ACTIVE`;
- conservar playbooks, intentos, updates, resultados y audit;
- volver a UI read-only si el adaptador se deshabilita;
- downgrade físico sólo si no existen registros; si existen, fallar con
  instrucciones de exportación/backup;
- no eliminar volumen n8n, credenciales, workflows o DLQ automáticamente;
- el workflow legacy puede permanecer inactivo durante la ventana documentada.

## 34. Decisiones materiales para aprobación

La implementación queda bloqueada hasta aprobar o enmendar:

1. lenguaje de dominio y ownership;
2. seis conceptos persistentes;
3. state machine y semántica de timeout;
4. acción autorizada y excepción `SYSTEM_NOTIFICATION`;
5. consumo atómico de autorización;
6. claim obligatorio antes del efecto;
7. envelope y ACK;
8. callback y estados permitidos;
9. HMAC, canonicalización y claves separadas;
10. ventana ±120 s, nonce 10 min y rotación 24 h;
11. límites y timeouts;
12. idempotencia en siete capas;
13. cinco workflows y clasificación;
14. allowlist/denylist de nodos y expresiones;
15. aliases de credenciales;
16. layout y manifest;
17. reconciliación sin borrado;
18. tres URLs con propósito no duplicado;
19. modelo multitenant de instancia/project dedicado para `live`;
20. separación del revisor de artefactos `live`;
21. API interna y de usuario candidata;
22. eventos y permisos;
23. auditoría, observabilidad y UI;
24. pruebas, migración, compatibilidad y rollback;
25. modo `live` bloqueado hasta aprobación operativa separada.

## 35. Paquete recomendado

Se recomienda aprobar las decisiones 1 a 25 sin cambios. Este paquete:

- satisface los requisitos humanos de workflows como código;
- reutiliza autorización, outbox/inbox, retry y RLS existentes;
- evita que n8n sea autoridad;
- permite pruebas reales y demo no destructiva;
- mantiene portabilidad hacia otro motor de automatización;
- prepara acciones `live` sin habilitarlas.

La aprobación autorizaría implementar contratos, migración, workflows, scripts,
callback, UI y pruebas. No autorizaría conectar un sistema de identidad, EDR,
firewall, correo o ticketing real sin configuración y prueba operativa
específica.

## 36. Criterios de salida

La Etapa 7 estará completa cuando:

1. la autorización se consuma una vez y cree una ejecución durable;
2. el dispatch sea asíncrono, autenticado e idempotente;
3. ningún efecto ocurra sin claim;
4. callback/replay/firma y estados fallen cerrado;
5. los cinco workflows estén versionados, validados e importados;
6. import/diff/update/retire sea reproducible en PowerShell y Python;
7. RLS y pruebas cross-tenant reales pasen;
8. el E2E sintético produzca resultado y audit verificables;
9. n8n caído, timeout o callback inválido no produzcan falso éxito;
10. UI bilingüe muestre catálogo, bindings y ejecuciones;
11. `approved: bool` y workflow legacy queden retirados o inactivos;
12. documentación, runbooks, rollback y evidencia de validación estén
    actualizados.
