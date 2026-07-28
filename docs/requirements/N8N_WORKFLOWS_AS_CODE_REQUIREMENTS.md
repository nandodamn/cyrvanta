# Requisitos de workflows n8n como código

**Estado:** INPUT HUMANO REGISTRADO — obligatorio para la especificación de
Etapa 7; no autoriza contratos físicos ni implementación prematura

**Fecha:** 2026-07-28

**Fuente:** instrucción humana adjunta a la continuación de Etapa 5

## 1. Objetivo recibido

Permitir que los playbooks de Cyrvanta se definan como JSON de n8n, se
versionen en Git, se validen, se importen idempotentemente y se prueben sin
incorporar credenciales reales.

La futura especificación deberá conservar n8n como adaptador reemplazable.
Cyrvanta continúa siendo sistema de registro para definiciones aprobadas,
autorizaciones, ejecuciones y resultados.

## 2. Reglas obligatorias recibidas

1. No incluir secretos, passwords, API keys ni tokens reales.
2. No incluir IDs internos de credenciales dependientes de una instalación.
3. Resolver credenciales externamente en n8n.
4. Validar autenticación, payload, tenant, idempotencia y campos permitidos.
5. No aceptar código, comandos o expresiones arbitrarias desde Cyrvanta.
6. Prohibir `Execute Command`, SSH y ejecución de código del sistema en
   workflows de producción.
7. Marcar workflows demo como `demo` o `synthetic`.
8. Informar resultado mediante callback autenticado.
9. Conservar correlation ID, incident ID, tenant ID, playbook execution ID y
   timestamp.
10. No producir falso éxito ante errores.

## 3. Estructura solicitada

```text
infrastructure/n8n/
├── README.md
├── workflows/
├── schemas/
├── scripts/
├── fixtures/
└── tests/
```

La migración desde el archivo provisional actual deberá ser no destructiva y
mantener una ventana de compatibilidad explícita.

## 4. Workflows solicitados

### 4.1 `notify-critical-incident`

Notificación SMTP con HTML y texto, idioma, destinatario allowlisted, modo demo,
validación de autenticación/payload y callback de éxito o error.

### 4.2 `create-security-ticket`

Creación mediante webhook o adaptador HTTP configurable, sin acoplar el contrato
a Jira, ServiceNow u otro proveedor.

### 4.3 `request-dual-approval`

Notificación de aprobación. n8n no conserva el estado autoritativo: la decisión
y separación de funciones pertenecen a Cyrvanta.

### 4.4 `simulate-user-block`

Exclusivamente demo, sin efecto real. Debe retornar de forma inequívoca:

```json
{
  "execution_mode": "demo",
  "action": "block_user",
  "result": "simulated_success"
}
```

### 4.5 `incident-report-email`

Envío bilingüe de resumen, hechos, inferencias, MITRE ATT&CK, riesgo,
recomendaciones, decisiones, acciones y resultados.

## 5. Automatización de administración solicitada

- script PowerShell para Windows;
- alternativa Python;
- importación mediante API pública de n8n;
- diff entre workflows locales e instalados;
- update sin duplicados;
- desactivación de workflows retirados;
- health check;
- uso de `N8N_API_URL` y `N8N_API_KEY`;
- prohibición de imprimir la API key.

La futura implementación deberá reconciliar `N8N_API_URL` con la configuración
actual `N8N_BASE_URL` sin crear dos fuentes de verdad.

## 6. Envelopes propuestos por la instrucción

La instrucción aporta candidatos de request y callback versión `1.0` con IDs de
evento, tenant, incidente, ejecución, correlación, action type, modo, timestamps,
payload, workflow/n8n execution ID, estado, resultado y error.

Esos campos son requisitos de entrada para la especificación, no contratos
aprobados. Deben reconciliarse con:

- envelope de Fase 15, que usa versiones enteras y conserva event, tenant,
  correlation y causation IDs;
- modelo de decisión/aprobación de Etapa 6;
- agregado durable de ejecución y resultado de Etapa 7;
- callbacks RFC 7807/API y política de redacción;
- semántica al menos una vez, inbox, outbox, retry y DLQ existentes.

No se duplicará `event_id`, tenant o causalidad dentro de capas incompatibles
sin una decisión formal.

## 7. Seguridad solicitada

- HMAC o autenticación equivalente;
- timestamp y protección contra replay;
- allowlist de action types;
- allowlist de destinatarios demo;
- límites de tamaño;
- timeout y reintentos controlados;
- errores redactados;
- callback autenticado;
- idempotencia durable.

La especificación deberá decidir canonicalización de firma, rotación de keys,
ventana de replay, almacenamiento de nonces, orden de validaciones, respuesta a
duplicados y autenticación mutua. No se inventan esos valores en este documento.

## 8. Pruebas solicitadas

- JSON de workflow válido y nodos conectados;
- campos obligatorios;
- ausencia de secretos y IDs de credenciales;
- ausencia de nodos peligrosos;
- autenticación inválida, replay y payload inválido;
- destinatario no permitido;
- correo simulado;
- callback de éxito y error;
- importación idempotente;
- n8n no disponible;
- evidencia de workflows importados realmente, sin inventar resultados.

## 9. Auditoría del estado actual

Existe:

- n8n `1.123.65` fijado en Compose y publicado solo en loopback;
- volumen persistente y health check;
- exclusión de `executeCommand` y `readWriteFile`;
- un workflow demo JSON importado al arranque;
- catálogo backend read-only mediante API de n8n;
- allowlist de workflow IDs;
- acceso administrativo documentado y API key externa;
- kill switch y modos `disabled`, `simulated`, `live`.

Brechas:

- el layout solicitado no existe;
- el workflow actual no autentica, no valida tenant/payload/replay y no emite
  callback;
- no existen schemas, validators, import/diff/update/retire scripts ni tests de
  workflows;
- la ejecución no tiene registro durable de playbook, versión, aprobación,
  dispatch, callback o resultado;
- la idempotencia actual deriva un ID en memoria y no resiste concurrencia;
- no existe callback backend autenticado;
- `approved: bool` no demuestra una aprobación persistida;
- la respuesta HTTP inmediata puede confundirse con resultado final;
- faltan límites, HMAC, rotación, replay window y redacción contractual.

El workflow provisional no es una base autorizada para producción.

## 10. Dependencias cronológicas

1. Etapa 5 debe aprobar y producir mappings, riesgo y explicación antes de
   alimentar `incident-report-email`.
2. Etapa 6 debe definir decisión, aprobación simple/doble, separación de
   funciones, expiración y autorización.
3. Etapa 7 debe formalizar playbook, versión, ejecución, callback, resultado,
   rollback, idempotencia y adaptador.
4. Recién entonces se implementan workflows, scripts y callback real.

Puede adelantarse en la especificación de Etapa 7 el diseño de validadores y
fixtures, pero no se conectará una acción real ni se importarán workflows como
aprobados antes de satisfacer las puertas anteriores.

## 11. Criterio de incorporación

La futura especificación de Etapa 7 debe incluir todos los requisitos de este
documento, indicar cualquier enmienda necesaria y presentar para aprobación:

- contratos exactos;
- modelo durable;
- permisos;
- HMAC/replay/idempotencia;
- workflows y nodos permitidos;
- importación, diff, update y retiro;
- callback y estados;
- pruebas y rollback.
