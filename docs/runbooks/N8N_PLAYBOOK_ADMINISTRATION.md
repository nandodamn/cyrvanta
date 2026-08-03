# Administración local de playbooks n8n

Estado: procedimiento de Etapa 7 para demo synthetic. El modo `live` continúa
bloqueado hasta aprobación operativa separada. El contrato autoritativo está en
`docs/specifications/PHASE_21_N8N_WORKFLOWS_EXECUTION.md`.

## Centro de llaves en Cyrvanta

La navegación **Llaves API** permite preparar `N8N_API_KEY`,
`N8N_DISPATCH_KEY` y `N8N_CALLBACK_KEY` en campos enmascarados. Es una
superficie de entrega local: los valores permanecen únicamente en memoria del
componente y Cyrvanta no los envía, persiste, registra ni copia
automáticamente.

El operador debe transferir cada valor directamente a las variables de entorno
protegidas o al gestor externo de secretos, configurar `N8N_KEY_ID`, reiniciar
los procesos afectados y borrar los campos. La página no reemplaza el gestor de
secretos ni modifica la configuración en ejecución.

## Límites de seguridad

- El editor se publica únicamente en `127.0.0.1:5678`.
- Solo usuarios Cyrvanta con `playbook.manage` reciben el enlace administrativo.
- Las credenciales y sus secretos se crean, cifran y conservan en n8n.
- Cyrvanta nunca consulta ni persiste valores de credenciales.
- Cyrvanta muestra únicamente workflows registrados en
  `N8N_ALLOWED_WORKFLOW_IDS`.
- Un workflow visible no queda autorizado para ejecución automática.

## Primer acceso

1. Iniciar el perfil `automation`.
2. Abrir `http://localhost:5678`.
3. Crear la cuenta propietaria local de n8n cuando la instalación lo solicite.
4. En n8n, crear las credenciales necesarias desde **Credentials**.
5. Crear o importar el workflow y probarlo con datos sintéticos.
6. Crear una API key de propietario desde la configuración de n8n.
7. Guardar la clave únicamente como `N8N_API_KEY` en el `.env` local.
8. Configurar `N8N_API_URL=http://localhost:5678` para los scripts host-side;
   no reutilizar ni derivar `N8N_BASE_URL`, que pertenece al backend.
9. Ejecutar `python infrastructure/n8n/scripts/validate_workflows.py`.
10. Ejecutar primero
   `python infrastructure/n8n/scripts/reconcile.py` sin `--apply` y revisar el
   diff redactado.
11. Añadir el ID exacto del workflow a `N8N_ALLOWED_WORKFLOW_IDS` después de
   revisión humana.
12. Usar `--apply` solo después de aprobar el diff y verificar nuevamente.
13. Reconstruir el backend para cargar la nueva configuración.

## Reflejo en Cyrvanta

La pantalla **Playbooks** consulta n8n a través del backend. Solo refleja:

- ID, nombre, estado y versión del workflow;
- tipos y nombres de nodos;
- nombres descriptivos de credenciales enlazadas, nunca sus valores;
- estado de sincronización.

Si no existe `N8N_API_KEY`, la pantalla conserva el catálogo allowlisted y
marca la sincronización como pendiente. Si n8n está caído, no presenta éxito
falso ni habilita workflows desconocidos.

## Verificación de outcomes append-only

Cada envío crea primero un registro inmutable en
`playbook_execution_attempts`. El ACK o fallo observado se agrega por `INSERT`
en `playbook_execution_attempt_outcomes`; el rol de aplicación no posee
`UPDATE` ni `DELETE` sobre ninguna de las dos tablas. Un outcome `UNKNOWN`
permite un nuevo intento con otro `dispatch_id`. Claims y callbacks posteriores
siguen siendo la evidencia autoritativa y nunca se sobrescriben.
## Conectores iniciales recomendados

La instalación no debe configurar credenciales ficticias. Según el entorno del
cliente, los primeros conectores de respuesta suelen ser:

- correo o Microsoft Teams/Slack para notificación;
- Jira, ServiceNow u otro sistema de tickets;
- Microsoft Active Directory/Entra ID para acciones de identidad;
- firewall, EDR o Wazuh para acciones de contención compatibles;
- HTTP Request con autenticación tipada para APIs sin nodo nativo.

No se permiten nodos genéricos de shell en playbooks aprobados. Cada conector
debe usar una cuenta de servicio de mínimo privilegio y tener una acción de
prueba no destructiva.

## Rollback

Quitar el ID de `N8N_ALLOWED_WORKFLOW_IDS` impide nuevas ejecuciones desde
Cyrvanta. `AUTOMATION_KILL_SWITCH=true` bloquea todas las ejecuciones.
Desactivar `cyrvanta-simulate-user-block` no reactiva automáticamente
`cyrvanta-demo-response`; el legado permanece inactivo. Retirar
la publicación `127.0.0.1:5678:5678` deshabilita el acceso local al editor sin
eliminar el volumen `n8n_data`.

La migración `0018_dispatch_outcomes` solo puede revertirse cuando
`playbook_execution_attempt_outcomes` está vacía. Si contiene evidencia, el
rollback falla cerrado y exige exportación/revisión previa.
