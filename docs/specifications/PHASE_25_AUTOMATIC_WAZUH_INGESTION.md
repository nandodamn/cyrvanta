# Fase 25 — Ingesta automática Wazuh tenant-scoped

**Estado:** DRAFT — pendiente de aprobación explícita; no autoriza implementación ni activación.

## 1. Objetivo

Sustituir la ejecución manual de `sync_wazuh_findings` por polling periódico,
acotado y recuperable, sin debilitar aislamiento, procedencia, idempotencia ni
el carácter real-only de Cyrvanta.

## 2. Condiciones de activación propuestas

- Deshabilitado por defecto globalmente y por integración.
- Sólo una conexión `WAZUH` y una `OPENSEARCH` activas, verificadas y sin error
  dentro del tenant.
- Activación y desactivación requieren `integration.manage` y generan auditoría.
- La activación no ejecuta una sincronización inmediata: el scheduler reclama
  el siguiente ciclo según `next_attempt_at`.
- No se aceptan tenant, URL, credenciales, índices, cursores ni límites desde
  cuerpos de jobs o mensajes no confiables.

## 3. Política propuesta

- Intervalo inicial: 60 segundos, configurable entre 30 y 3600 segundos.
- Lote inicial: 100 findings, configurable entre 1 y 500.
- Un único lease por `(tenant_id, integration_id, stream_type)`.
- Lease inicial de 120 segundos; un lease vencido es recuperable.
- Cursor y watermark avanzan únicamente después de persistir todo el lote.
- Un lote parcialmente fallido no confirma cursor ni watermark.
- Backoff por fallos consecutivos: 1, 2, 4, 8 y 15 minutos; máximo 15 minutos.
- Una sincronización exitosa reinicia `error_count` y el backoff.
- Una conexión deshabilitada, no verificada o ambigua falla cerrado y no llama
  servicios externos.

## 4. Persistencia propuesta

Ampliar `integration_sync_state`, manteniendo RLS forzada y clave única actual,
con campos tipados:

- `polling_enabled boolean NOT NULL DEFAULT false`;
- `interval_seconds integer NOT NULL DEFAULT 60` con límites 30–3600;
- `batch_size integer NOT NULL DEFAULT 100` con límites 1–500;
- `next_attempt_at timestamptz`;
- `lease_expires_at timestamptz`;
- `last_started_at timestamptz`;
- `last_succeeded_at timestamptz`;
- `last_error_code varchar(80)` redactado.

El cursor sigue siendo opaco y write-only para el usuario. Ningún secreto ni
payload Wazuh se guarda en esta tabla.

## 5. Reclamo y concurrencia

Una función PostgreSQL restringida reclama estados vencidos mediante
`FOR UPDATE SKIP LOCKED`, fija lease y devuelve sólo tenant, integración,
stream, cursor y límites. El scheduler no obtiene `BYPASSRLS` ni lectura libre
de tablas de negocio. Cada sincronización abre contexto tenant antes de
resolver conexiones o persistir findings.

## 6. Flujo funcional

1. El scheduler reclama un estado habilitado cuyo ciclo esté vencido.
2. Resuelve conexiones tenant-scoped y verificadas.
3. Consulta un lote real con cursor durable.
4. Normaliza y persiste cada finding mediante el servicio existente.
5. La idempotencia durable evita revisiones y eventos duplicados.
6. Sólo tras completar el lote confirma cursor, watermark y próximo ciclo.
7. Ante fallo libera el lease, conserva cursor, incrementa error y aplica
   backoff.

La creación posterior de correlaciones e incidentes continúa por eventos
existentes; el polling no ejecuta playbooks ni respuesta automática.

## 7. API y UI propuestas

- `GET /api/v1/integrations/connections/{id}/polling` — estado redactado.
- `PUT /api/v1/integrations/connections/{id}/polling` — intervalo, lote y
  habilitación con versión optimista.
- La UI muestra habilitado, intervalo, lote, última ejecución exitosa, próximo
  intento y código de error; nunca muestra cursor ni credenciales.
- Habilitar requiere confirmación explícita y probe vigente.

## 8. Auditoría y observabilidad

Se auditan configuración, habilitación, deshabilitación, reset administrativo
de cursor y recuperación manual. Los ciclos técnicos no generan audit por
finding; usan registros de negocio, outbox y logs estructurados.

Métricas: ciclos reclamados/completados/fallidos, duración, lote, duplicados,
edad del cursor, backoff, leases recuperados y backlog, siempre tenant-safe y
sin cardinalidad sensible.

## 9. Pruebas obligatorias

- RLS A/B y rechazo cross-tenant para estado y configuración.
- Doble scheduler no reclama el mismo stream.
- Lease vencido se recupera; lease vigente no se duplica.
- Fallo parcial no avanza cursor ni watermark.
- Replay conserva idempotencia de finding, revisión, evento e incidente.
- Backoff respeta límites y éxito lo reinicia.
- Integración ausente, ambigua, deshabilitada o no verificada no produce red.
- Activación/desactivación audita sin exponer cursor o secretos.
- Reinicio de scheduler conserva progreso durable.
- UI ES/EN refleja carga, error, deshabilitado y estado real.

Codex no ejecutará estas pruebas; quedan preparadas para validación manual del
operador conforme a la instrucción vigente.

## 10. Rollback

- Switch global y por integración permiten detener nuevos ciclos.
- Detener scheduler no afecta API, worker, datos ya persistidos ni comando
  manual acotado.
- El downgrade sólo elimina columnas nuevas si no existe polling habilitado ni
  lease activo; de otro modo falla con instrucción explícita.
- Nunca se eliminan findings, revisiones, eventos, cursores o auditoría durante
  rollback operativo.

## 11. Decisiones pendientes de aprobación

La aprobación debe confirmar: intervalo 60 s, lote 100, límites configurables,
lease 120 s, backoff máximo 15 min, persistencia propuesta, API/UI, auditoría,
pruebas y rollback. Hasta entonces este documento no autoriza código, migración
ni activación.
