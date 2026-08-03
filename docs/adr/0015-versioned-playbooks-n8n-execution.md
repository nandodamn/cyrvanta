# ADR 0015 — Playbooks versionados y n8n como adaptador

**Estado:** Aceptado
**Fecha:** 2026-07-29

## Contexto

Cyrvanta dispone de un workflow n8n sintético y un catálogo read-only, pero no
de una ejecución durable, autenticada o vinculada al consumo de la autorización
de Etapa 6. Los IDs de n8n no son portables y su historial no puede sustituir a
PostgreSQL como sistema de registro.

## Decisión propuesta

Adoptar, sujeto a aprobación humana, el contrato de
`docs/specifications/PHASE_21_N8N_WORKFLOWS_EXECUTION.md`:

- playbooks lógicos y versiones inmutables en Cyrvanta;
- workflows JSON y manifest versionados en Git;
- binding separado para IDs opacos de cada instalación;
- autorización consumida atómicamente al crear ejecución y outbox;
- `request-dual-approval` como única notificación inicial sin autorización de
  acción;
- claim durable antes de todo efecto;
- dispatch y callback con HMAC, timestamp, nonce e idempotencia;
- estado y resultado autoritativos en PostgreSQL;
- intentos de dispatch inmutables y outcomes técnicos append-only separados;
- reconciliación import/diff/update/deactivate sin borrado automático;
- n8n como adaptador reemplazable;
- modo `live` bloqueado hasta aprobación operativa separada.

## Consecuencias

### Positivas

- Ejecución reproducible y auditable.
- Replays y callbacks duplicados no repiten efectos.
- Los artefactos son portables entre instalaciones.
- La caída de n8n no se presenta como éxito.
- Los secretos permanecen fuera de Git y del modelo funcional.

### Costos

- Se agregan estados, bindings, claims y reconciliación.
- Los workflows deben cumplir una allowlist estricta.
- La operación `live` requiere aislamiento y credenciales por tenant.
- Un timeout posterior al claim puede requerir conciliación humana.

## Alternativas descartadas

- Confiar en el historial o ID de n8n como sistema de registro.
- Ejecutar directamente desde React.
- Tratar el ACK HTTP como éxito.
- Guardar quorum o autorización en n8n.
- Reintentar ciegamente un efecto externo.
- Versionar credential IDs o secretos.

## Estado de aprobación

Aceptado por instrucción humana el 2026-07-29.

## Aclaración de implementación append-only

Aceptada por instrucción humana el 2026-07-30. El intento se crea antes del
envío para que el claim pueda validarlo y no se modifica después. El ACK o el
fallo observado se registra en `playbook_execution_attempt_outcomes` mediante
`INSERT` únicamente. Un outcome `UNKNOWN` no revierte un claim ni un resultado
terminal y requiere conciliación con los hechos posteriores de la ejecución.
