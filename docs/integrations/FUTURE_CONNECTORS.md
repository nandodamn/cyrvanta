# Conectores futuros

Todos están **planificados y no disponibles en esta versión**. Autenticación y
API deberán validarse contra la versión instalada antes de implementar.

| Conector | Objeto principal | Autenticación probable | Sincronización | Diferencias y prueba real |
|---|---|---|---|---|
| IBM QRadar | offense y eventos | token de servicio/API | API incremental y Ariel | Lifecycle propio; exige consola licenciada, cuenta mínima y dataset controlado. |
| Splunk Enterprise Security | notable/risk event | token o cuenta de servicio | SPL con checkpoint temporal | Depende de índices, macros y ES; exige instancia ES y notables conocidos. |
| Microsoft Sentinel | incident y alertas | identidad de aplicación | API cloud incremental | Tenant, suscripción y workspace; exige tenant Azure y roles mínimos. |
| Elastic Security | detection alert y case | API key/cuenta de servicio | APIs y búsqueda Elasticsearch | Detección y caso son distintos; exige stack compatible y reglas de laboratorio. |
| ArcSight | event/correlation event | token o cuenta según producto | API específica de edición | La familia no comparte una API; exige producto, versión y licencia exactos. |
| LogRhythm | alarm y event | token/cuenta de servicio | alarmas y consultas temporales | Varía por módulo; exige API habilitada y datos de prueba. |
| Google Security Operations | detection/rule detection | cuenta de servicio/OAuth | APIs cloud y UDM | UDM no debe filtrarse al núcleo; exige proyecto, permisos e ingestión de prueba. |

Ninguno se registrará ni mostrará activo hasta superar pruebas de tenant,
límites, errores, redacción, idempotencia y recuperación.

