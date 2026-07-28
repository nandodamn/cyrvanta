# Fase 6 — LDAP y Active Directory

**Estado:** APPROVED — aprobación humana registrada el 2026-07-27  
**Versión:** 0.1.0  
**Alcance:** autenticación LDAP/AD tenant-scoped mediante adaptador reemplazable  
**Fuera de alcance:** Kerberos, SAML, OIDC, sincronización completa de directorio,
MFA y administración de contraseñas del directorio

## 1. Objetivo

Permitir que cada tenant configure autenticación contra LDAP o Active Directory
sin acoplar el dominio a un proveedor concreto. Una autenticación externa
correcta produce la misma identidad interna y el mismo contexto de seguridad
que la autenticación local.

## 2. Principios obligatorios

1. LDAP autentica; Cyrvanta autoriza.
2. El directorio nunca decide el tenant a partir de datos no verificados.
3. La contraseña del usuario LDAP solo vive durante la solicitud.
4. Nunca se registra, persiste, publica en eventos ni envía a colas.
5. El secreto de bind se cifra en reposo y nunca se devuelve en claro.
6. TLS y validación de certificado están habilitados por defecto.
7. Cada configuración pertenece a un tenant y queda protegida por RLS.
8. Fallar LDAP no habilita bypass automático ni amplía privilegios.
9. Toda vinculación, autenticación y cambio de configuración se audita.
10. El adaptador LDAP no importa modelos ORM ni lógica HTTP.

## 3. Decisiones propuestas

### 3.1 Configuración por tenant

Cada tenant puede tener como máximo una configuración LDAP activa durante el
MVP. La configuración contiene conceptualmente:

- tipo de directorio: `ldap` o `active_directory`;
- estado: borrador, activo, deshabilitado o degradado;
- lista ordenada de servidores;
- modo de transporte: `ldaps` o StartTLS;
- base DN;
- bind DN o identidad técnica;
- secreto de bind cifrado;
- filtro de búsqueda de usuario parametrizado;
- atributo de login;
- atributo de identificador externo estable;
- atributo de correo y nombre visible;
- base y filtro opcionales de grupos;
- timeout y límites acotados;
- referencia a CA interna opcional;
- política JIT;
- instante y resultado sanitizado de la última prueba.

No se permiten filtros LDAP libres aportados durante el login. La configuración
se valida y compila antes de activarse.

### 3.2 Descubrimiento y bind

El flujo propuesto es:

1. Resolver tenant mediante `tenant_slug`.
2. Cargar la configuración activa tenant-scoped.
3. Conectar con TLS verificable.
4. Usar la identidad técnica para buscar exactamente un usuario.
5. Rechazar cero resultados, múltiples resultados o atributos inválidos.
6. Intentar bind como el DN encontrado usando la contraseña efímera.
7. Obtener identificador estable y grupos mediante búsquedas acotadas.
8. Resolver o crear la identidad interna según política.
9. Calcular roles mediante mappings aprobados.
10. Emitir tokens internos y auditoría.

El filtro recibe el login como valor escapado, nunca como fragmento de filtro.

### 3.3 Identidad y colisiones

- Una identidad LDAP se vincula mediante:
  `tenant + provider + external_subject`.
- Para Active Directory, el identificador preferido es `objectGUID`.
- Para LDAP genérico se exige un atributo estable configurado.
- El correo no es una clave de vinculación automática.
- Si existe una cuenta local con el mismo correo y no hay vínculo explícito, el
  login se rechaza como colisión y se audita.
- Vincular una identidad LDAP a una cuenta local existente requiere una acción
  administrativa explícita.
- Una cuenta interna puede conservar credencial local para recuperación solo
  mediante política explícita; no se crea automáticamente.
- Deshabilitar la identidad interna bloquea login aunque LDAP autentique.

### 3.4 Just-in-time y sincronización

- JIT está deshabilitado por defecto.
- Cuando se habilita, solo crea usuarios para los que coincida una regla de
  admisión explícita basada en grupo allowlisted.
- El rol JIT predeterminado es `viewer`.
- JIT nunca asigna `tenant-admin`.
- Los cambios de grupos se aplican en cada login exitoso.
- Perder un grupo puede revocar roles mapeados, pero no elimina la cuenta.
- Roles asignados manualmente y roles derivados del directorio se distinguen
  para impedir revocaciones accidentales.
- No se implementa sincronización periódica completa en Fase 6.

### 3.5 Mapeo de grupos

- Cada mapping pertenece al tenant.
- Relaciona un identificador estable o DN normalizado de grupo con un rol
  tenant-owned.
- Solo roles allowlisted y no privilegiados pueden mapearse inicialmente.
- `tenant-admin` requiere asignación local explícita.
- Un mapping inválido falla cerrado y genera auditoría.
- Los grupos no reconocidos no conceden permisos.

### 3.6 Disponibilidad y recuperación

- LDAP no disponible produce fallo de autenticación explícito y sanitizado.
- No existe fallback silencioso de LDAP a contraseña local.
- El usuario elige proveedor únicamente cuando la cuenta tenga ambos métodos
  autorizados.
- La cuenta bootstrap local se conserva como recuperación administrativa.
- Rate limiting, backoff y timeouts protegen el directorio.
- Los mensajes al usuario no permiten enumerar cuentas ni distinguir
  contraseña incorrecta de usuario inexistente.

## 4. Puerto y adaptador propuestos

El dominio depende de un puerto conceptual `DirectoryProvider` con operaciones:

- validar configuración;
- probar conectividad y bind técnico;
- autenticar usuario;
- obtener sujeto externo y atributos normalizados;
- resolver membresías de grupos;
- comprobar salud.

El resultado normalizado no expone objetos específicos de `ldap3`, Microsoft ni
otro SDK. El primer adaptador puede usar `ldap3` y su estrategia simulada para
pruebas, ejecutando las operaciones bloqueantes fuera del event loop.

## 5. Contrato HTTP propuesto

Todas las rutas están bajo `/api/v1`.

| Método | Ruta | Permiso | Resultado |
|---|---|---|---|
| `GET` | `/directory/configuration` | `directory.read` | Configuración redactada |
| `PUT` | `/directory/configuration` | `directory.manage` | Crea o reemplaza borrador |
| `POST` | `/directory/configuration/test` | `directory.manage` | Prueba segura |
| `POST` | `/directory/configuration/activate` | `directory.manage` | Activa configuración válida |
| `POST` | `/directory/configuration/disable` | `directory.manage` | Deshabilita LDAP |
| `GET` | `/directory/group-mappings` | `directory.read` | Mappings tenant-scoped |
| `PUT` | `/directory/group-mappings` | `directory.manage` | Reemplaza mappings |
| `POST` | `/auth/directory/login` | público limitado | Autentica con tenant slug |
| `POST` | `/users/{user_id}/directory-link` | `user.manage` | Vinculación explícita |
| `DELETE` | `/users/{user_id}/directory-link` | `user.manage` | Desvinculación auditada |

El login recibe únicamente `tenant_slug`, `username` y `password`. No recibe
DN, filtros, servidor, grupos, roles ni `tenant_id`.

## 6. Persistencia lógica propuesta

La migración física se diseñará después de aprobar esta especificación. Se
requieren conceptualmente:

- configuración de directorio tenant-owned;
- identidad externa vinculada a usuario interno;
- mapping tenant-owned de grupo a rol;
- procedencia de asignaciones de rol;
- metadatos de salud y sincronización;
- referencia/versionado del material criptográfico.

Todas las estructuras tenant-owned tendrán RLS. No se modifica `0001` ni
`0002`.

## 7. Secretos y criptografía

- El secreto de bind se cifra en la aplicación antes de persistir.
- La clave maestra proviene de configuración externa al repositorio.
- La API acepta reemplazar el secreto, pero nunca leerlo.
- La respuesta indica solamente si existe un secreto configurado.
- La rotación crea nueva versión cifrada y audita el cambio.
- Logs y errores aplican redacción defensiva de DN, filtros y endpoints cuando
  puedan contener información sensible.
- En producción se recomienda un secret manager mediante adaptador; el cifrado
  local es el baseline on-premise.

## 8. Pruebas obligatorias

- Adaptador contra servidor LDAP simulado, sin credenciales reales.
- TLS inválido, CA no confiable y hostname incorrecto fallan cerrados.
- Escape de caracteres especiales e intentos de inyección en filtros.
- Cero y múltiples resultados de búsqueda.
- Contraseña incorrecta y usuario inexistente producen respuesta equivalente.
- Colisión de correo local/LDAP no vincula automáticamente.
- JIT deshabilitado rechaza sujeto desconocido.
- JIT habilitado exige grupo allowlisted y asigna como máximo `viewer`.
- Grupo desconocido no concede roles.
- `tenant-admin` no puede derivarse de grupos.
- Tenant A no consulta configuración, identidades ni grupos de B.
- Deshabilitar usuario interno bloquea login LDAP.
- Secreto no aparece en API, logs, auditoría ni excepciones.
- Timeouts no bloquean el event loop.
- Login, prueba, activación, mapping y vínculo generan auditoría.
- Backend, frontend, migraciones y Docker mantienen todos los checks.

## 9. Reversión

- La funcionalidad se puede deshabilitar por tenant sin afectar login local.
- La migración será aditiva y tendrá downgrade mientras no implique pérdida de
  vínculos.
- Desactivar LDAP no elimina configuraciones, vínculos ni auditoría.
- El adaptador puede sustituirse sin cambiar los casos de uso.
- La clave de cifrado y su rotación no dependen del proveedor LDAP.

## 10. Decisiones que confirma la aprobación

1. una configuración activa por tenant durante el MVP;
2. TLS verificable obligatorio por defecto;
3. búsqueda con bind técnico y bind posterior del usuario;
4. vínculo por sujeto externo estable, nunca solo por correo;
5. JIT deshabilitado por defecto y limitado a grupo allowlisted;
6. `tenant-admin` nunca se deriva de grupos;
7. sin fallback silencioso a credencial local;
8. secreto de bind cifrado y no recuperable mediante API;
9. sin sincronización completa, Kerberos, SAML, OIDC ni MFA en Fase 6.
