# Cyrvanta — primera ejecución funcional real

**Estado:** herramienta preparada; validación manual pendiente del operador.

Este procedimiento demuestra Cyrvanta en un entorno aislado sin reemplazar
funciones por mocks, fixtures, cifras estáticas o resultados simulados.

## Límites de seguridad

- Use sólo sistemas, cuentas y destinos autorizados.
- No cargue secretos en Git, capturas, tickets, chats o playbooks.
- Configure credenciales desde **Integraciones**; luego sólo podrán reemplazarse.
- Mantenga polling Wazuh y switches LIVE apagados hasta revisar los destinos.
- Una dependencia incompleta debe mantener su playbook deshabilitado.
- El kill switch debe estar disponible durante toda prueba de egreso.

## Acceso inicial

1. Inicie los servicios según el procedimiento del entorno.
2. Acceda con tenant y administrador local entregados fuera de banda.
3. Cambie la contraseña bootstrap en **Administración → Usuarios**.
4. Cree un segundo usuario para comprobar doble control.
5. Verifique que ambos usuarios pertenezcan sólo al tenant esperado.

## Conexiones reales

Configure únicamente las necesarias:

- `WAZUH` y `OPENSEARCH` para ingesta;
- `OLLAMA` para redacción asistida opcional;
- `SMTP` para notificaciones e informes;
- `HTTP_ALLOWLISTED` para tickets HTTPS;
- `N8N` sólo para bindings que usen el adaptador opcional.

Para cada conexión: guarde parámetros y credencial, habilítela, ejecute
**Probar conexión real** y compruebe fecha, salud y ausencia de error. La
interfaz no debe volver a mostrar el secreto. No continúe con una conexión
requerida ausente, ambigua, deshabilitada o no verificada.

## Ingesta Wazuh

Hasta aprobar PHASE 25, la ingesta se inicia manualmente y de forma acotada:

```powershell
docker compose --profile core run --rm backend python -m cyrvanta.sync_wazuh_findings `
  --tenant-id "<tenant-uuid>" `
  --limit 100
```

La salida permitida contiene conteos, cursor siguiente, watermark y correlation
ID; nunca payload raw o credenciales. Verifique alertas reales, procedencia
Wazuh, triaje persistente, correlaciones reales y pulso de 24 horas. Si todavía
no existe una correlación, cree un incidente real desde **Incidentes**. No use
generadores sintéticos.

## Ciclo del incidente

1. Edite título, descripción, severidad, prioridad y clasificación.
2. Asigne un usuario activo del tenant.
3. Agregue un comentario y compruebe la línea temporal.
4. Recorra sólo transiciones válidas.
5. Para cierre seleccione motivo y justificación; para reapertura, una nueva
   justificación.
6. Compruebe versión creciente, actor, timestamps y auditoría.

## Análisis, riesgo y claims

1. Ejecute análisis sobre el incidente real.
2. Compruebe riesgo, factores, ATT&CK y explicación vinculados a evidencia.
3. Si Ollama está verificado, solicite redacción asistida; la IA no autoriza.
4. Registre un claim humano con evidencia tenant-scoped.
5. Use otro usuario para evaluarlo; el autor sólo puede retractar el propio.
6. Relacione dos claims y agregue una presentación en el otro idioma.
7. Confirme que la historia sea append-only.

## Playbook nativo real

1. Revise impacto, parámetros, credenciales y aprobaciones.
2. Configure y pruebe sus conexiones reales.
3. Valide y publique una versión inmutable.
4. Vincúlela a `Cyrvanta Native` y active binding y switches LIVE de forma
   consciente.
5. Cree una propuesta, apruébela con el segundo usuario cuando corresponda y
   ejecute la autorización una sola vez.
6. Verifique estado final, recibo, intento, resultado y auditoría.

Casos iniciales habilitables:

- `contain-and-document-incident` actualiza el incidente;
- `notify-critical-incident` entrega por SMTP;
- `create-security-ticket` realiza POST HTTPS allowlisted e idempotente;
- `incident-report-email` entrega el informe por SMTP.

Los egresos transmiten sólo el snapshot minimizado aprobado. Un estado enviado
no sustituye evidencia del resultado.

## Administración e identidad

1. Administre usuarios sin dejar al tenant sin administrador activo.
2. Reemplace una contraseña y compruebe manualmente la revocación de sesiones.
3. Configure roles y verifique denegación backend para un usuario sin permiso.
4. Si existe LDAP/AD autorizado, configure bind/CA write-only, pruebe, active y
   valide mappings y login JIT.
5. Revise auditoría sin secretos, tokens, API keys o payloads raw.

## Cierre de aceptación

Descargue el informe HTML, revise decisiones/aprobaciones/ejecuciones y apague
switches LIVE al terminar. La aceptación falla ante éxito sin efecto
verificable, dato sintético presentado como real, secreto recuperable, cruce de
tenant, acción sin auditoría o playbook habilitado sin dependencias verificadas.

Codex no ejecutó tests, builds, probes, conexiones, migraciones, ingestas ni
playbooks. La evidencia de aceptación debe ser generada manualmente por el
operador.