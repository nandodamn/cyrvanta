# Operación de entrega de eventos

**Estado:** implementado para la prueba sintética de Fase 15.
**Alcance:** outbox, RabbitMQ, inbox, retries y DLQ.

## Seguridad

- Ejecutar únicamente en infraestructura administrada.
- No copiar payloads de colas o tablas a tickets, chats o logs.
- No exponer RabbitMQ fuera de la red interna.
- La prueba usa datos sintéticos; no representa una detección real.
- No reprocesar DLQ sin revisar tenant, schema y código de error.

## Crear una prueba sintética

1. Levantar el perfil `core`.
2. Obtener el UUID de un tenant demo mediante una consulta administrativa
   controlada.
3. Ejecutar:

```powershell
docker compose --profile core run --rm backend python -m cyrvanta.traceability_probe `
  --tenant-id "<tenant-uuid>" `
  --code "manual-probe"
```

El comando imprime `event_id`, `correlation_id` y
`data_classification=synthetic`. No imprime payload ni credenciales.

## Resultado esperado

1. `event_outbox.status` cambia de `pending` a `published`.
2. RabbitMQ entrega `platform.traceability.probe.created`.
3. `event_inbox.status` termina en `completed`.
4. Outbox e inbox conservan el mismo tenant/event/correlation.
5. Una entrega duplicada produce log `event_duplicate` y no repite el handler.

## Diagnóstico

Revisar logs sin payload:

```powershell
docker compose --profile core logs worker --no-color --tail 200
```

Indicadores:

- `outbox_publish_failed`: RabbitMQ no confirmó; la fila vuelve a `pending`.
- `event_retry_scheduled`: fallo transitorio enviado a una cola TTL.
- `event_deadlettered`: agotó retries o falló validación permanente.
- `event_rejected`: envelope, schema, metadata o tamaño inválidos.
- `event_completed`: handler e inbox confirmados.

## Colas

- Principal: `cyrvanta.traceability.v1`
- Retry: `cyrvanta.traceability.v1.retry.1..N`
- Dead letter: `cyrvanta.traceability.v1.dlq`

Los delays se leen de `EVENT_RETRY_DELAYS_SECONDS`.

## Reprocesamiento de DLQ

La primera fase no expone API de replay. Antes de cualquier reproceso:

1. detener el consumidor si se requiere una inspección consistente;
2. verificar el tenant y que el schema sea soportado;
3. clasificar el error como corregido;
4. registrar aprobación administrativa;
5. republicar preservando `event_id`, `correlation_id` y payload;
6. verificar inbox y resultado;
7. registrar el resultado de la intervención.

No usar requeue masivo ni modificar el payload para forzar aceptación. La
automatización auditada de este procedimiento pertenece a una fase posterior.

## Rollback

1. Detener productores nuevos.
2. Drenar outbox y cola principal.
3. Respaldar outbox, inbox y DLQ.
4. Detener worker.
5. Ejecutar downgrade únicamente cuando outbox e inbox estén vacíos.

La migración rechaza el downgrade si existen filas y nunca elimina colas
automáticamente.
