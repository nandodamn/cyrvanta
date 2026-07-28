# Fase 5 — Identidad, RBAC, multitenancy y auditoría

**Estado:** APPROVED — aprobación humana registrada el 2026-07-27  
**Versión:** 0.1.0  
**Alcance:** Fase 5 del roadmap  
**Fuera de alcance:** LDAP/AD, MFA, SSO, incidentes, OpenSearch, Wazuh y automatización

## 1. Objetivo

Completar el plano de administración tenant-safe sobre el bootstrap existente:
tenants, usuarios locales, roles, permisos y consulta de auditoría. La
autenticación no concede permisos por sí sola y ningún identificador aportado
por el cliente establece el tenant efectivo.

## 2. Decisiones propuestas

### 2.1 Usuario e identidad

- Una cuenta interna pertenece a un único tenant durante el MVP.
- El correo local es único dentro del tenant, no globalmente.
- El inicio de sesión local utiliza `tenant_slug + email + password`.
- El `tenant_slug` es un identificador estable, normalizado y no secreto.
- No existe selección dinámica de tenant dentro de una sesión.
- Una persona que opere en dos tenants mantiene dos cuentas internas
  independientes.

Esta decisión evita una identidad global capaz de relacionar organizaciones y
permite evolucionar posteriormente hacia membresías multi-tenant mediante una
migración explícita.

### 2.2 Administración de plataforma

- Las identidades de plataforma están separadas de los usuarios tenant.
- `platform.manage` no concede lectura de datos operativos tenant-owned.
- Crear, suspender o reactivar un tenant es una operación global explícita.
- El acceso de soporte a un tenant no se implementa en esta fase.
- No se implementa impersonation.

### 2.3 Roles y permisos

- Los permisos son un catálogo global, versionado por código estable.
- Los roles son tenant-owned.
- Existen roles de sistema no eliminables y roles personalizados.
- Roles iniciales:
  - `tenant-admin`: administración del tenant, usuarios, roles y auditoría.
  - `auditor`: lectura de auditoría.
  - `viewer`: acceso autenticado sin permisos administrativos.
- Permisos administrativos iniciales:
  - `tenant.read`
  - `tenant.manage`
  - `user.read`
  - `user.manage`
  - `role.read`
  - `role.manage`
  - `audit.read`
- Deny-by-default: la ausencia de un permiso produce denegación.
- `tenant-admin` no puede asignar permisos globales que no formen parte del
  catálogo permitido para tenants.
- El último administrador activo de un tenant no puede desactivarse ni perder
  el rol administrativo.

### 2.4 Sesiones locales

- Argon2id continúa siendo obligatorio.
- Access token corto y refresh token opaco rotatorio.
- Desactivar un usuario invalida sus refresh tokens.
- Cambiar contraseña invalida todos sus refresh tokens.
- Redis continúa como almacén de revocación efímero en esta fase.
- Reiniciar Redis invalida sesiones refresh de forma segura.
- No se implementa MFA ni recuperación automática de contraseña en Fase 5.
- La cuenta bootstrap local actúa como recuperación inicial; una política
  break-glass completa queda pendiente de una especificación separada.

### 2.5 Auditoría

- Los eventos son append-only desde la aplicación.
- No existen operaciones API para modificar o eliminar eventos.
- Se auditan como mínimo:
  - autenticación exitosa y fallida;
  - creación, modificación, activación y desactivación de usuarios;
  - creación y modificación de roles;
  - asignación o revocación de roles y permisos;
  - cambios del tenant;
  - lectura y exportación de auditoría.
- Cada evento conserva tenant, actor, acción, recurso, resultado, correlation
  ID, instante y detalles redactados.
- Contraseñas, tokens y secretos nunca se incluyen en detalles.
- La retención definitiva y la protección criptográfica del historial quedan
  pendientes de requisitos legales y operativos; Fase 5 no permite borrado.

## 3. Contrato HTTP propuesto

Todos los recursos quedan bajo `/api/v1`. Los errores usan RFC 7807. Las
colecciones tienen paginación acotada. Los IDs se resuelven dentro del tenant
antes de revelar existencia.

| Método | Ruta | Permiso | Resultado |
|---|---|---|---|
| `GET` | `/tenant` | `tenant.read` | Tenant efectivo |
| `PATCH` | `/tenant` | `tenant.manage` | Actualiza atributos permitidos |
| `GET` | `/users` | `user.read` | Usuarios del tenant efectivo |
| `POST` | `/users` | `user.manage` | Crea usuario local |
| `GET` | `/users/{user_id}` | `user.read` | Usuario del mismo tenant |
| `PATCH` | `/users/{user_id}` | `user.manage` | Modifica nombre o estado |
| `POST` | `/users/{user_id}/password` | `user.manage` | Reemplaza contraseña |
| `GET` | `/roles` | `role.read` | Roles del tenant efectivo |
| `POST` | `/roles` | `role.manage` | Crea rol personalizado |
| `GET` | `/roles/{role_id}` | `role.read` | Rol y permisos |
| `PATCH` | `/roles/{role_id}` | `role.manage` | Modifica rol permitido |
| `PUT` | `/roles/{role_id}/permissions` | `role.manage` | Reemplaza permisos |
| `PUT` | `/users/{user_id}/roles` | `user.manage` | Reemplaza roles |
| `GET` | `/permissions` | `role.read` | Catálogo asignable |
| `GET` | `/audit-events` | `audit.read` | Consulta tenant-scoped |

No se acepta `tenant_id` en cuerpos tenant-scoped. La creación y administración
global de tenants no se expone hasta aprobar el modelo de identidad de
plataforma.

## 4. Persistencia propuesta

La implementación partirá de las tablas bootstrap existentes, mediante una
migración Alembic aditiva. Antes de escribirla se documentará el catálogo
físico exacto.

Cambios lógicos requeridos:

- sustituir unicidad global de correo por unicidad tenant + correo;
- añadir `slug` estable al tenant;
- distinguir roles de sistema y personalizados;
- cargar el catálogo inicial de permisos de forma idempotente;
- asociar revocación de sesiones con usuario;
- mantener RLS en toda tabla tenant-owned.

No se cambia ni reescribe la migración `0001_bootstrap`.

## 5. Reglas de seguridad

1. El tenant procede exclusivamente de credenciales verificadas.
2. Repositorio, servicio y RLS aplican el mismo tenant.
3. La autorización se comprueba en el caso de uso backend.
4. Una denegación cross-tenant no revela si el recurso existe.
5. Listados, conteos y filtros también están aislados.
6. Las mutaciones administrativas generan auditoría en la misma transacción.
7. Las contraseñas nunca se devuelven ni se registran.
8. Los permisos del cliente o del token no sustituyen la consulta autoritativa
   cuando una revocación deba tener efecto inmediato.

## 6. Criterios de aceptación

- Prueba positiva y negativa por cada permiso administrativo.
- Tenant A no puede leer, modificar, contar ni inferir recursos de tenant B.
- RLS bloquea consultas cruzadas usando el rol de aplicación.
- No se acepta `tenant_id` arbitrario.
- El último administrador activo queda protegido.
- Desactivar usuario o cambiar contraseña revoca refresh tokens.
- Todas las mutaciones generan un evento de auditoría redactado.
- La API publica OpenAPI 3.1 y problemas RFC 7807.
- La interfaz administrativa funciona en español e inglés.
- Ruff, formato, mypy, pytest, ESLint, Prettier, TypeScript, Vitest y build
  pasan.
- Docker Compose aplica la migración y los servicios permanecen saludables.

## 7. Reversión

- La migración tendrá `downgrade` probado mientras no implique pérdida de datos.
- Los seeds serán idempotentes.
- Los nuevos endpoints podrán retirarse sin cambiar tokens existentes.
- La transición desde correo global a correo por tenant debe conservar todas
  las cuentas actuales y detectar colisiones antes de aplicar constraints.

## 8. Decisiones que requieren aprobación

La aprobación de este documento confirma específicamente:

1. usuario de un solo tenant durante el MVP;
2. login mediante `tenant_slug + email + password`;
3. correo único por tenant;
4. identidades de plataforma separadas;
5. roles iniciales y catálogo administrativo;
6. ausencia de MFA, impersonation y soporte cross-tenant en Fase 5;
7. auditoría sin borrado, con retención definitiva pendiente.
