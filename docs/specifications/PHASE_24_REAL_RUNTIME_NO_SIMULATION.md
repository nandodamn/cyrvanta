# PHASE 24 — Runtime real sin simulaciones

Estado: `APROBADO — 2026-08-13`

## Objetivo

Cyrvanta no presentará datos sintéticos, métricas estáticas, conectores simulados ni
ejecuciones sin efecto como funcionalidades disponibles. Una capacidad estará `READY` sólo
cuando tenga configuración tenant-scoped, prueba de conexión real, autorización, persistencia,
auditoría y manejo de fallo. En cualquier otro caso figurará `DISABLED`, `UNCONFIGURED` o
`UNHEALTHY` y no podrá ejecutarse.

Los fixtures y dobles de prueba pueden existir exclusivamente bajo directorios de tests; no se
registran en el contenedor productivo ni son alcanzables desde API o UI.

## Decisiones funcionales

1. Se retiran del producto los endpoints y botones `/demo/scenarios/*`.
2. No se crean alertas, incidentes, claims, decisiones, métricas o resultados sintéticos.
3. `OPENSEARCH_MODE`, `WAZUH_MODE` y `OLLAMA_MODE` aceptan únicamente `disabled` o `live`.
4. `N8N_MODE` acepta únicamente `disabled` o `live`; n8n continúa opcional.
5. Ningún estado `simulated` se considera saludable.
6. El dashboard usa exclusivamente registros tenant-scoped persistidos; sin datos muestra cero
   y `Sin actividad registrada`.
7. La biblioteca muestra todos los playbooks aprobados del catálogo. Los incompletos permanecen
   visibles y deshabilitados, con su menú de configuración y bloqueos de readiness; sólo pueden
   activarse cuando versión, binding, acciones y conexiones reales estén saludables.
8. Toda ejecución NATIVE publicada produce un efecto real, verificable e idempotente.
9. Un conector ausente o sin credenciales falla cerrado antes de crear autorización ejecutable.
10. Las credenciales se guardan cifradas por alias, nunca se devuelven y sólo pueden
    reemplazarse, probarse o rotarse.

## Conexiones reales admitidas

| Capacidad | Conector final | Resultado requerido |
|---|---|---|
| Alertas SIEM | Wazuh API/manager | Hallazgos canónicos persistidos con procedencia |
| Evidencia | OpenSearch | Consulta tenant-scoped con error real y estado de salud |
| Redacción IA | Ollama | Respuesta validada por schema; el determinismo sigue siendo autoridad |
| Directorio | LDAP/Active Directory | Bind LDAPS, búsqueda, grupos y autenticación reales |
| Automatización opcional | n8n API/webhook | Workflow reconciliado, firmado y callback persistido |
| Notificación | SMTP | Entrega SMTP real con Message-ID y resultado seguro |
| Ticket/Webhook | HTTP allowlisted | Respuesta HTTP real, TLS y destino allowlisted |
| Acción interna | Cyrvanta | Mutación de dominio real, auditada y tenant-scoped |

Los proveedores EDR/firewall que no tengan adaptador real configurado quedan `UNAVAILABLE` y
sus playbooks no se publican. No se sustituyen por éxito simulado.

## Catálogo NATIVE inicial publicable

1. `contain-and-document-incident`: transición real del incidente a `contained` y registro
   auditable conforme a PHASE 21-B.
2. `notify-critical-incident`: envío SMTP real.
3. `create-security-ticket`: POST HTTPS real a un endpoint ITSM allowlisted.
4. `incident-report-email`: generación del reporte real existente y entrega SMTP real.

Cada acción usa inputs tipados y allowlisted. No admite shell, código, plantillas ejecutables,
URLs, headers o parámetros libres introducidos por el playbook.

## Seguridad y multitenancy

- El tenant procede del contexto autenticado.
- Cada integración, alias, binding, propuesta, aprobación, ejecución y resultado se valida
  contra el mismo tenant.
- TLS es obligatorio fuera de loopback; LDAPS es obligatorio para directorio.
- Las respuestas externas son datos no confiables, limitados en tamaño y normalizados.
- No se registran secretos, bodies sensibles ni tokens.
- LIVE permanece apagado por defecto y requiere kill switches global y tenant, binding activo,
  conexión saludable, permiso y aprobación exigida por impacto.
- Los callbacks aplican autenticación, replay protection, expiración e idempotencia durable.

## API y persistencia

Se reutilizan los endpoints y registros aprobados cuando sean suficientes. Cualquier endpoint,
tabla, columna o evento adicional requiere un anexo físico aprobado antes de implementarse.
Las respuestas de catálogo incorporarán readiness y razones bloqueantes sin revelar secretos.

## UI

- Se elimina toda acción `Generar demo`, etiqueta `Simulado` y contador de fuentes simuladas.
- Integraciones muestra `Deshabilitada`, `Sin configurar`, `No saludable` o `Conectada`.
- Playbooks muestra `Real`, efecto, conexión, credenciales pendientes, aprobación y readiness.`n- Todos los playbooks conservan su menú de configuración aunque estén deshabilitados.
- Los controles no ejecutables explican exactamente qué configuración real falta.
- Ninguna cifra estática se presenta como dato operativo.

## Migración de legado

Los registros históricos marcados sintéticos no se convierten en reales. Quedan excluidos por
defecto de vistas operativas y memoria influyente. Su eliminación física requiere política de
retención aprobada; hasta entonces sólo son accesibles mediante una vista administrativa de
legado claramente identificada.

## Criterios de aceptación manual

1. Sin conexiones configuradas, todas las capacidades externas están bloqueadas y ninguna
   informa éxito.
2. Wazuh real crea hallazgos y desencadena correlación, incidente, análisis y métricas reales.
3. OpenSearch y Ollama muestran salud basada en llamadas reales.
4. LDAP/AD autentica y asigna roles conforme a mappings tenant-scoped.
5. Cada playbook publicado completa su efecto real y conserva recibo seguro y auditoría.
6. Una conexión caída, credencial inválida, timeout, replay, cross-tenant o respuesta inválida
   falla cerrado y deja estado final coherente.
7. n8n deshabilitado no afecta el motor NATIVE.
8. No existen endpoints o controles de producto que creen datos sintéticos.

## Rollback

Los conectores y bindings pueden deshabilitarse sin borrar historial. El rollback nunca fabrica
un éxito: una compensación sólo se ofrece cuando el conector real declara y ejecuta una acción
inversa aprobada.

## Orden de implementación

1. Política `disabled | live` y retirada de generadores sintéticos.
2. Readiness real en conexiones y catálogo.
3. Acción interna real PHASE 21-B.
4. SMTP real.
5. HTTP ITSM/webhook real allowlisted.
6. Publicación selectiva de playbooks completamente funcionales.
7. Guía de configuración y pruebas manuales.
