# PHASE 24 — Entrega funcional real-only

Estado: implementación preparada; validación funcional manual pendiente del operador.

## Capacidades implementadas

- Modos de infraestructura restringidos a `disabled` o `live`.
- Configuración tenant-scoped de conexiones con cifrado Fernet y respuestas write-only.
- Probes reales manuales para SMTP, HTTP allowlisted, n8n, OpenSearch, Ollama y Wazuh.
- Motor NATIVE exclusivamente LIVE, con kill switch y doble activación operativa.
- Acción `incident.status.transition@1.0.0` mediante `IncidentService`, control optimista,
  auditoría y recibo.
- Acciones SMTP y HTTP allowlisted con idempotency key, TLS y recibos sin secretos.
- n8n sin éxito prefabricado: el workflow debe enviar el resultado real firmado por HMAC.
- Biblioteca completa visible; playbooks no implementados o incompletos permanecen bloqueados.
- Menús para configurar conexiones, configurar bindings, validar/publicar y activar.
- Generadores de escenarios y propuesta sintética retirados de API/UI.

## Playbooks habilitables actualmente

- `contain-and-document-incident`: acción interna real.
- `escalation-notification`: entrega SMTP real.

Los demás playbooks del catálogo se muestran con
`PLAYBOOK_ACTION_UNAVAILABLE` hasta incorporar su adaptador real específico. No pueden
publicarse ni activarse.

## Secuencia de validación manual

1. Abrir Integraciones, guardar una conexión y ejecutar **Probar conexión real**.
2. Abrir Playbooks, elegir **Configurar** y guardar/verificar cada binding requerido.
3. Ejecutar **Validar y publicar**.
4. Activar el binding NATIVE.
5. Activar de forma consciente `PLAYBOOK_LIVE_ENABLED=true` y
   `PLAYBOOK_DISPATCH_ENABLED=true`; mantener `AUTOMATION_KILL_SWITCH=false`.
6. Crear o seleccionar un incidente real del tenant. Para el playbook de contención, el estado
   debe admitir la transición a `contained`.
7. Crear la propuesta, completar las aprobaciones y ejecutar la autorización.
8. Verificar estado del incidente o entrega externa, ejecución persistida y auditoría.

## Verificación no ejecutada

Por instrucción del operador, Codex no ejecutó tests, builds, probes, conexiones ni playbooks.

