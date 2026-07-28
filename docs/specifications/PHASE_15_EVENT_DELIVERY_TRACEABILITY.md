# Fase 15 — Entrega de eventos y trazabilidad asíncrona

**Estado:** DRAFT — propuesta contractual para revisión humana.
**Fecha:** 2026-07-28
**Implementación autorizada:** no.

## 1. Objetivo

Crear la base asíncrona común para que Cyrvanta publique y procese eventos
tenant-scoped con:

- entrega al menos una vez;
- escritura atómica del cambio de negocio y su evento;
- deduplicación durable por consumidor;
- correlación y causalidad de extremo a extremo;
- reintentos acotados y dead-letter queue;
- auditoría, observabilidad y aislamiento.

La fase no implementa todavía correlación de seguridad, claims, decisiones,
playbooks ni memoria. Entrega la infraestructura reutilizable para esas etapas.

## 2. Estado actual

- RabbitMQ 4.0.5 está en el perfil Compose `core`.
- `aio-pika` ya es dependencia del backend.
- `worker.py` abre una conexión robusta y queda esperando indefinidamente.
- No existen exchanges declarados por aplicación, colas, bindings, publicación,
  consumidores, publisher confirms, retry o DLQ.
- No existen outbox, inbox ni idempotencia durable.
- PostgreSQL usa transacciones async y RLS tenant-scoped.
- HTTP ya genera request y correlation IDs.

## 3. Decisiones vinculantes si se aprueba

### 3.1 Garantía

La garantía es **at-least-once**. Cyrvanta no promete exactly-once. Los efectos
observables se vuelven equivalentes a una sola ejecución mediante inbox,
constraints e idempotencia de cada handler.

### 3.2 Consistencia

El cambio de negocio y el registro outbox se escriben en la misma transacción
PostgreSQL. No se publica directamente a RabbitMQ dentro del caso de uso.

### 3.3 Orden

No se garantiza orden global ni entre tenants. El orden por agregado tampoco se
presume cuando existen retries. Los consumidores deben validar versión/estado y
ser seguros ante eventos tardíos o repetidos.

### 3.4 Payload

El payload es JSON versionado, mínimo y sin secretos. No transporta telemetría
raw, credenciales, tokens, prompts completos ni resultados sensibles cuando una
referencia estable sea suficiente.

### 3.5 Alcance de tenant

Esta fase admite únicamente eventos tenant-owned. Los eventos globales de
plataforma quedan fuera de alcance hasta especificar su autorización.

## 4. Envelope v1 propuesto

Nombre contractual: `EventEnvelopeV1`.

| Campo | Tipo | Obligatorio | Regla |
|---|---|---:|---|
| `event_id` | UUID | sí | UUID aleatorio; identidad inmutable del evento. |
| `event_name` | string | sí | Minúsculas separadas por puntos; allowlist del productor. |
| `schema_version` | integer | sí | Inicia en `1`; positivo. |
| `tenant_id` | UUID | sí | Proviene del contexto seguro, nunca del payload solicitado. |
| `aggregate_type` | string | sí | Código estable y no localizado. |
| `aggregate_id` | UUID | sí | Recurso causante dentro del tenant. |
| `occurred_at` | datetime UTC | sí | Instante del hecho, no del consumo. |
| `correlation_id` | UUID | sí | Conservado desde HTTP/job o generado en el origen interno. |
| `causation_id` | UUID/null | sí | `event_id` que causó este evento; nulo solo en una raíz. |
| `producer` | string | sí | Componente lógico versionable, no hostname. |
| `payload` | object JSON | sí | Schema específico de evento, máximo 256 KiB serializado. |

Reglas:

1. El consumidor rechaza campos desconocidos en el envelope.
2. Cada payload posee schema propio asociado a
   `(event_name, schema_version)`.
3. Un cambio incompatible crea nueva `schema_version`.
4. El productor mantiene como mínimo la versión vigente; compatibilidad con
   versiones anteriores se declara por consumidor.
5. Un schema no soportado va a DLQ con código redactado; no se descarta.
6. Los logs registran IDs, nombre y versión, nunca el payload completo.

Primer evento de aceptación:

```text
platform.traceability.probe.created
```

Su payload contiene solo un código sintético y timestamp de prueba. No representa
una integración de seguridad real.

## 5. Modelo lógico y físico propuesto

### 5.1 Tabla `event_outbox`

Registro tenant-owned append-oriented hasta su publicación.

| Columna | Tipo propuesto | Restricción |
|---|---|---|
| `event_id` | uuid | PK |
| `tenant_id` | uuid | FK tenant, no nulo |
| `event_name` | varchar(160) | no nulo |
| `schema_version` | integer | `> 0` |
| `aggregate_type` | varchar(100) | no nulo |
| `aggregate_id` | uuid | no nulo |
| `occurred_at` | timestamptz | no nulo |
| `correlation_id` | uuid | no nulo |
| `causation_id` | uuid | nulo para raíz |
| `producer` | varchar(120) | no nulo |
| `payload` | jsonb | objeto, no nulo |
| `status` | varchar(24) | `pending`, `publishing`, `published` |
| `attempt_count` | integer | `>= 0` |
| `available_at` | timestamptz | no nulo |
| `lease_expires_at` | timestamptz | nullable |
| `published_at` | timestamptz | nullable |
| `last_error_code` | varchar(80) | nullable, redactado |
| `created_at` | timestamptz | no nulo |

Índices candidatos:

- `(status, available_at, created_at)` para dispatch acotado.
- `(tenant_id, aggregate_type, aggregate_id, occurred_at)` para trazabilidad.
- `(tenant_id, correlation_id, occurred_at)` para reconstrucción.

No se persiste `last_error_message` libre para evitar secretos.

### 5.2 Tabla `event_inbox`

Registro tenant-owned de deduplicación y resultado técnico por consumidor.

| Columna | Tipo propuesto | Restricción |
|---|---|---|
| `id` | uuid | PK |
| `tenant_id` | uuid | FK tenant, no nulo |
| `event_id` | uuid | no nulo |
| `consumer_name` | varchar(120) | no nulo |
| `event_name` | varchar(160) | no nulo |
| `schema_version` | integer | `> 0` |
| `status` | varchar(24) | `processing`, `completed`, `failed` |
| `attempt_count` | integer | `>= 1` |
| `lease_expires_at` | timestamptz | nullable |
| `first_received_at` | timestamptz | no nulo |
| `last_received_at` | timestamptz | no nulo |
| `completed_at` | timestamptz | nullable |
| `last_error_code` | varchar(80) | nullable, redactado |

Constraint:

```text
UNIQUE (tenant_id, consumer_name, event_id)
```

El inbox no duplica el payload.

### 5.3 RLS y rol dispatcher

- Ambas tablas habilitan y fuerzan RLS.
- Casos de uso y handlers usan `tenant_session(tenant_id)`.
- El rol de aplicación no puede consultar sin tenant.
- El dispatcher cross-tenant no recibe acceso general a tablas de negocio.
- Se propondrá una función PostgreSQL `SECURITY DEFINER`, con `search_path`
  fijo, propietario administrativo y permisos mínimos, que reclama un lote
  acotado de outbox mediante `FOR UPDATE SKIP LOCKED`.
- El dispatcher solo podrá ejecutar las funciones específicas de claim,
  confirmación y fallo; no tendrá `BYPASSRLS` ni `SELECT` libre.
- Payload y IDs retornados por la función se consideran sensibles.

La migración no codificará nombres de roles sin validar la variable
`POSTGRES_APP_USER`, siguiendo las migraciones existentes.

## 6. Puertos y límites de código

Estructura candidata:

```text
backend/src/cyrvanta/shared/
  domain/
    events.py
  application/
    messaging.py
  infrastructure/
    event_store.py
    rabbitmq.py
    consumers.py
```

Contratos candidatos:

- `DomainEvent`: dataclass inmutable sin SQLAlchemy, Pydantic o aio-pika.
- `EventPublisher`: registra un evento en outbox dentro de la sesión recibida.
- `OutboxDispatcher`: reclama, publica y confirma filas.
- `EventHandler`: procesa un envelope ya validado.
- `InboxGuard`: reclama/deduplica antes del handler.

Reglas:

- El dominio no importa RabbitMQ, SQLAlchemy o FastAPI.
- La serialización y validación de transporte pertenecen a infraestructura.
- Un handler abre contexto tenant antes de leer o escribir.
- El handler y la marca `completed` del inbox se confirman en la misma
  transacción.
- No se crean repositorios genéricos que permitan consultas no acotadas.

## 7. Topología RabbitMQ propuesta

Exchanges durables:

- `cyrvanta.events` — topic.
- `cyrvanta.deadletter` — topic.

Cola inicial:

- `cyrvanta.traceability.v1`

Binding inicial:

- `platform.traceability.probe.*`

Retry sin plugins:

- retry 1: 5 segundos;
- retry 2: 30 segundos;
- retry 3: 5 minutos;
- después: DLQ.

Los delays serán configuración validada, no lógica de dominio. Las colas retry
usan TTL y dead-letter exchange. Mensajes y exchanges son durables; los
mensajes se publican persistentes y con publisher confirms.

Propiedades AMQP mínimas:

- `message_id = event_id`;
- `type = event_name`;
- `correlation_id = correlation_id`;
- `content_type = application/json`;
- header `schema_version`;
- header `tenant_id`.

El envelope completo sigue siendo la fuente de validación; headers no se
consideran confiables por sí solos.

## 8. Flujo de publicación

1. Caso de uso obtiene tenant y correlation ID seguros.
2. Modifica negocio y registra outbox en la misma transacción.
3. Dispatcher reclama un lote con lease y `SKIP LOCKED`.
4. Publica con confirmación.
5. Solo después del confirm marca `published`.
6. Ante fallo incrementa intento, guarda código redactado y programa
   `available_at`.
7. Un lease expirado permite recuperación tras caída.

Publicar y fallar antes de marcar `published` puede duplicar el mensaje; esto es
esperado y cubierto por inbox/idempotencia.

## 9. Flujo de consumo

1. Consumidor recibe y valida tamaño, JSON, envelope y schema.
2. Establece tenant desde el envelope validado, no desde el payload.
3. Reclama `(tenant, consumer, event)` en inbox.
4. Si ya está `completed`, ACK sin repetir el handler.
5. Si tiene lease activo, no ejecuta concurrentemente.
6. Si el lease expiró, registra nuevo intento y recupera.
7. Ejecuta handler y marca inbox `completed` en una transacción.
8. ACK únicamente después del commit.
9. Error transitorio va a retry; error permanente o schema desconocido va a
   DLQ.

Un handler no puede publicar directamente a RabbitMQ; genera nuevos eventos en
outbox con `causation_id` igual al evento consumido.

## 10. Errores y clasificación

- `invalid_envelope`: permanente, DLQ.
- `unsupported_schema`: permanente, DLQ.
- `tenant_context_rejected`: permanente, DLQ y alerta de seguridad.
- `handler_rejected`: permanente según contrato del handler.
- `dependency_unavailable`: transitorio.
- `database_conflict`: transitorio cuando sea recuperable.
- `handler_timeout`: transitorio hasta agotar retries.

Los códigos son estables y no contienen datos sensibles. Stack traces solo en
logs internos controlados; nunca dentro del mensaje.

## 11. Configuración propuesta

- `EVENT_MAX_PAYLOAD_BYTES=262144`
- `OUTBOX_BATCH_SIZE=50`
- `OUTBOX_LEASE_SECONDS=60`
- `EVENT_HANDLER_TIMEOUT_SECONDS=30`
- `EVENT_CONSUMER_PREFETCH=16`
- `EVENT_RETRY_DELAYS_SECONDS=5,30,300`

Todos tendrán límites seguros en `Settings`. El nombre de exchanges y colas es
constante de infraestructura versionada, no entrada libre del usuario.

## 12. API y frontend

No se agregan endpoints ni pantallas en esta fase.

Reprocesar DLQ será inicialmente una operación administrativa mediante runbook
y comando interno restringido. Una API futura requerirá permiso, idempotencia,
auditoría y especificación separada.

## 13. Auditoría

- La mutación de negocio mantiene su evento de auditoría actual.
- Crear outbox/inbox no genera un audit event por cada transición técnica.
- Replays manuales, descarte de DLQ, cambios de topología y fallos de tenant son
  acciones de seguridad auditables.
- Audit no almacena payload del evento.

## 14. Observabilidad

Métricas mínimas:

- outbox pending y edad del más antiguo;
- publicaciones, confirms y fallos;
- eventos recibidos, completados y duplicados;
- retries por código;
- DLQ depth;
- latencia outbox-a-publicación y evento-a-completado;
- leases expirados;
- rechazo por tenant/schema/tamaño.

Logs estructurados:

- `event_id`, `event_name`, `schema_version`;
- `tenant_id` cuando esté autorizado;
- `correlation_id`, `causation_id`;
- consumidor, intento y código de error;
- nunca payload ni secreto.

## 15. Seguridad

- Tamaño máximo antes de deserialización completa cuando sea posible.
- JSON y schema estrictos.
- Nombres de evento y productor allowlisted.
- RabbitMQ solo en red interna, con credenciales por entorno.
- TLS y credenciales separadas son obligatorios en producción.
- No confiar en headers AMQP para tenant.
- No ejecutar instrucciones contenidas en payload.
- Payload minimizado y clasificado.
- RLS y contexto tenant en outbox, inbox y handlers.
- DLQ protegida como dato sensible.

## 16. Pruebas obligatorias

### Unitarias

- envelope válido e inválido;
- límites de tamaño y nombres;
- serialización UTC;
- clasificación de errores;
- backoff y leases;
- evento hijo conserva correlation y define causation.

### Persistencia

- negocio + outbox confirman o revierten juntos;
- unique inbox evita doble efecto;
- reclaim de lease expirado;
- claim concurrente no duplica filas;
- filas tenant A invisibles a tenant B;
- RLS forzada.

### RabbitMQ

- declaración idempotente de topología;
- persistent delivery y publisher confirms;
- retry 1/2/3 y DLQ;
- restart del worker sin pérdida;
- mensaje duplicado ejecuta un efecto.

### Seguridad

- tenant A no lee/escribe outbox/inbox de B;
- envelope manipulado no cambia tenant;
- payload excesivo o schema desconocido va a DLQ;
- logs no contienen payload ni secretos;
- dispatcher no posee acceso a tablas de negocio.

### Aceptación

Un caso de uso crea `platform.traceability.probe.created` y su outbox en una
transacción. El worker lo publica, consume y registra como completado. Una copia
duplicada se reconoce sin repetir el efecto. Un fallo transitorio recorre los
retries y uno permanente llega a DLQ. Correlation y causation son reconstruibles.

## 17. Archivos previstos al implementar

- nueva migración Alembic posterior a `0007`;
- modelos/puertos/infraestructura bajo `shared`;
- composición de `worker.py`;
- configuración y `.env.example`;
- pruebas unitarias, persistencia, RabbitMQ, RLS y seguridad;
- runbook de DLQ/replay;
- documentación de operación.

No se prevén cambios en React, OpenAPI, Wazuh, OpenSearch, Ollama o n8n.

## 18. Rollback

- El despliegue puede detener dispatcher/consumidores sin afectar API.
- Los productores se habilitan solo cuando worker y topología están saludables.
- La migración downgrade solo elimina tablas si están vacías.
- Si existen filas, el downgrade debe fallar con instrucción de exportar,
  respaldar o completar procesamiento; nunca descartar eventos silenciosamente.
- Exchanges/colas no se eliminan automáticamente durante rollback.
- Un runbook documentará drenaje, respaldo, restauración y limpieza explícita.

## 19. Criterios de aprobación del contrato

Para autorizar implementación se debe confirmar:

1. Envelope v1 y límite de payload.
2. At-least-once sin garantía de orden.
3. Tablas `event_outbox` y `event_inbox`.
4. Funciones restringidas para dispatch cross-tenant.
5. Retry 5 s, 30 s, 5 min y posterior DLQ.
6. Sin API/UI en esta fase.
7. Prueba sintética como primer flujo.
8. Downgrade no destructivo cuando existan filas.

La aprobación debe registrarse antes de crear migración o código.
