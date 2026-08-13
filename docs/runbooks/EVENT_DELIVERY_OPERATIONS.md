# Operación de entrega de eventos reales

**Estado:** outbox, RabbitMQ, inbox, retries y DLQ habilitados para eventos
productivos tenant-scoped.

## Seguridad

- RabbitMQ permanece en la red interna con credenciales del entorno.
- No copie payloads de colas o tablas a tickets, chats o logs.
- El tenant procede del envelope validado y se aplica antes del handler.
- No reprocesar DLQ sin revisar schema, tenant, causalidad y código de error.
- Un evento observado no sustituye auditoría ni el registro de negocio.

## Eventos enrutados

El worker declara bindings y consumidores para:

- findings normalizados y correlación;
- claims, evaluaciones, relaciones y presentaciones;
- mappings, riesgo y explicaciones;
- propuestas, policy, aprobaciones y autorizaciones;
- feedback y memoria gobernada;
- versiones, bindings, pasos y ejecuciones de playbooks.

Sólo estos handlers producen efectos posteriores:

- `security.finding.normalized` inicia correlación;
- eventos de correlación inician enriquecimiento;
- `security.playbook_execution.dispatch_requested` entrega al motor elegido.

Los demás eventos completan inbox como observaciones durables. No vuelven a
ejecutar la mutación que los originó.

## Resultado esperado

1. La mutación funcional y su outbox confirman en una transacción.
2. El dispatcher publica con confirmación en `cyrvanta.events`.
3. RabbitMQ entrega el evento a la cola durable.
4. Inbox reclama `(tenant, consumer, event)` y deduplica reentregas.
5. El handler ejecuta dentro de `tenant_session` y completa inbox tras commit.
6. Eventos hijos conservan correlation ID y declaran causation ID.
7. Un duplicado genera `event_duplicate` sin repetir el efecto.

## Diagnóstico manual

Revise logs redactados del worker:

```powershell
docker compose --profile core logs worker --no-color --tail 200
```

Códigos principales:

- `outbox_publish_failed`: publicación no confirmada;
- `event_retry_scheduled`: fallo transitorio enviado a retry;
- `event_deadlettered`: retries agotados o error permanente;
- `event_rejected`: envelope, schema, tenant o tamaño inválido;
- `event_completed`: handler e inbox confirmados;
- `event_duplicate`: redelivery sin segundo efecto.

Una fila outbox que repite `rabbitmq_publish_failed` puede indicar un evento sin
binding, caída de RabbitMQ o topología divergente. No la marque manualmente como
publicada.

## Reprocesamiento de DLQ

Antes de cualquier replay:

1. detenga el consumidor si necesita una inspección consistente;
2. compruebe tenant, nombre, schema y que el error esté corregido;
3. registre aprobación administrativa;
4. preserve `event_id`, correlation ID, causation ID y cuerpo exacto;
5. publique una sola vez y verifique inbox y resultado;
6. documente el resultado sin payload sensible.

No use requeue masivo, no modifique el payload para forzar aceptación y no
elimine evidencia para vaciar la cola.

## Rollback

1. Detenga productores nuevos.
2. Drene outbox y cola principal cuando sea seguro.
3. Respalde outbox, inbox y DLQ.
4. Detenga el worker.
5. No elimine exchanges, colas o filas automáticamente.
6. Ejecute downgrade físico sólo bajo las condiciones no destructivas de la
   migración correspondiente.

## Pruebas no ejecutadas por Codex

Existe una prueba de registro que descubre nombres de eventos en código
productivo y exige que todos estén incluidos en el worker. Codex no la ejecutó
ni inició RabbitMQ; el operador verificará entrega y redelivery manualmente.