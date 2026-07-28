# Administración local de playbooks n8n

Estado: procedimiento provisional para demo. No define el modelo de dominio ni
los contratos finales de Playbooks.

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
8. Añadir el ID exacto del workflow a `N8N_ALLOWED_WORKFLOW_IDS` después de
   revisión humana.
9. Reconstruir el backend para cargar la nueva configuración.

## Reflejo en Cyrvanta

La pantalla **Playbooks** consulta n8n a través del backend. Solo refleja:

- ID, nombre, estado y versión del workflow;
- tipos y nombres de nodos;
- nombres descriptivos de credenciales enlazadas, nunca sus valores;
- estado de sincronización.

Si no existe `N8N_API_KEY`, la pantalla conserva el catálogo allowlisted y
marca la sincronización como pendiente. Si n8n está caído, no presenta éxito
falso ni habilita workflows desconocidos.

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
Cyrvanta. `AUTOMATION_KILL_SWITCH=true` bloquea todas las ejecuciones. Retirar
la publicación `127.0.0.1:5678:5678` deshabilita el acceso local al editor sin
eliminar el volumen `n8n_data`.
