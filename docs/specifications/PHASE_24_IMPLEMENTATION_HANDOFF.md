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
- Menús bilingües para reemplazar, habilitar, deshabilitar y verificar conexiones sin volver a mostrar secretos, además de configurar bindings, validar/publicar y activar.
- Administración LDAP/AD completa: bind y CA write-only, transporte seguro, timeout, atributos y grupos, JIT condicionado a mappings no privilegiados, activación posterior a una prueba vigente y vínculo explícito de identidades locales.
- Generadores de escenarios y propuesta sintética retirados de API/UI.
- Listas, detalles, mutaciones, métricas, memoria, correlaciones, decisiones y ejecuciones operativas excluyen registros sintéticos históricos; el dispatcher rechaza cualquier versión que no sea `LIVE`.

## Playbooks habilitables actualmente

- `contain-and-document-incident`: transición interna real y auditable.
- `notify-critical-incident`: entrega SMTP real de un snapshot minimizado.
- `create-security-ticket`: POST HTTPS real, allowlisted e idempotente.
- `incident-report-email`: informe real minimizado y entrega SMTP.

Cada capacidad externa permanece bloqueada hasta que su conexión tenant-scoped esté activa y
verificada, el binding de acción sea válido, la versión sea publicada y los switches LIVE estén
habilitados. El egreso excluye evidencia raw, secretos y parámetros libres de la propuesta.

Los demás playbooks del catálogo se muestran con
`PLAYBOOK_ACTION_UNAVAILABLE` hasta incorporar su adaptador real específico. No pueden
publicarse ni activarse.

## Secuencia de validación manual

1. Abrir Integraciones, guardar una conexión y ejecutar **Probar conexión real**. Una conexión deshabilitada no puede probarse ni resolverse hasta volver a habilitarla.
2. Para LDAP/AD: guardar, ejecutar la prueba real y activar la configuración desde Administración; la activación queda bloqueada si la última prueba no fue exitosa.
3. Abrir Playbooks, elegir **Configurar** y guardar/verificar cada binding requerido.
4. Ejecutar **Validar y publicar**.
5. Activar el binding NATIVE.
6. Activar de forma consciente `PLAYBOOK_LIVE_ENABLED=true` y
   `PLAYBOOK_DISPATCH_ENABLED=true`; mantener `AUTOMATION_KILL_SWITCH=false`.
7. Crear o seleccionar un incidente real del tenant. Para el playbook de contención, el estado
   debe admitir la transición a `contained`.
8. Crear la propuesta, completar las aprobaciones y ejecutar la autorización.
9. Verificar estado del incidente o entrega externa, ejecución persistida y auditoría.

## Verificación no ejecutada

Por instrucción del operador, Codex no ejecutó tests, builds, probes, conexiones ni playbooks.

