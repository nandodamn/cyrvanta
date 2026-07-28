# Modelo de autorización

**Estado:** DRAFT — no es aún un contrato de permisos.

## Principios

- Deny-by-default y mínimo privilegio.
- Autenticación no implica autorización.
- Tenant derivado de identidad/token/sesión verificados.
- Decisiones en casos de uso backend, nunca solo en React.
- Acceso cross-tenant explícito, excepcional y auditado.
- Las cuentas break-glass tienen controles, alertas y revisión reforzados.
- Jobs y service identities reciben permisos mínimos y tenant explícito.

## Sujetos y ámbitos candidatos

- **Usuario tenant:** actúa dentro de tenants asociados.
- **Administrador tenant:** configura únicamente su tenant.
- **Administrador de plataforma:** opera funciones globales explícitas; no
  obtiene acceso implícito a evidencia de todos los tenants.
- **Service identity:** integración o job con alcance técnico limitado.
- **Break-glass local:** recuperación controlada cuando LDAP no está disponible.

La pertenencia multi-tenant de un usuario y el modelo de impersonation requieren
decisión formal.

## Catálogo inicial de permisos

| Recurso | Permisos candidatos |
|---|---|
| Incident | `incident.read`, `incident.create`, `incident.assign`, `incident.update`, `incident.close` |
| Alert | `alert.read` |
| AI Analysis | `analysis.request`, `analysis.read` |
| Response | `response.recommend`, `response.approve`, `response.execute` |
| Playbook | `playbook.read`, `playbook.manage` |
| Integration | `integration.read`, `integration.manage` |
| MITRE | `mitre.read` |
| Audit | `audit.read` |
| Reporting | `report.read` |
| Tenant | `tenant.manage` |
| Platform | `platform.manage` |

Este catálogo procede del prompt maestro. Falta especificar alcance, condiciones
y separación de funciones. `platform.manage` no debe funcionar como comodín.

## Evaluación conceptual

Una decisión considera: sujeto autenticado, tenant efectivo, permiso, recurso,
ownership, estado del recurso, política tenant, modalidad de respuesta, riesgo
de acción y contexto de seguridad. El ID del recurso se resuelve dentro del
tenant antes de revelar existencia; denegaciones no deben facilitar IDOR ni
enumeración.

## Separación de funciones

- Gestionar un playbook no concede aprobarlo ni ejecutarlo.
- Solicitar análisis no concede leer incidentes ajenos.
- Aprobar una acción puede requerir una persona distinta del solicitante.
- Acciones de alto impacto pueden requerir doble aprobación.
- Administrar LDAP/integaciones no revela secretos existentes.
- Leer auditoría requiere filtros tenant y protección contra exportación masiva.

## Autenticación convergente

Local y LDAP producen una identidad interna común. La vinculación, colisiones,
JIT, deshabilitación y prioridad entre proveedores deben especificarse. Nunca
se guarda la contraseña LDAP del usuario. Las credenciales de integración se
cifran y su lectura en claro no forma parte de operaciones normales.

## Pruebas obligatorias

- Positiva de cada permiso y negativa sin permiso.
- A no puede leer, mutar, contar ni inferir recursos de B.
- Cambio de tenant no confía en parámetros del cliente.
- Administrador plataforma usa operación explícita y genera auditoría.
- Job conserva tenant y no amplía permisos.
- Cache y búsqueda no mezclan tenants.
- Aprobador no evade separación de funciones.
- Revocación y lockout tienen efecto conforme a especificación.

## Decisiones pendientes

- Roles predeterminados y roles personalizados.
- Usuarios multi-tenant y selección de tenant activo.
- Modelo de grupos/equipos y asignación.
- Alcance exacto de plataforma y soporte.
- MFA, step-up y política break-glass.
- Duración/token/session/CSRF y revocación.
- Matriz permiso × comando × estado × condición.
