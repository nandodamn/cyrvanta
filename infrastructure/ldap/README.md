# Laboratorio LDAP

Servicio `ldap` (osixia/openldap) en `docker-compose.yml`, perfiles `security`/`live-demo`.
Requiere STARTTLS (Cyrvanta rechaza `ldap://` sin `use_starttls`) -- certificado propio en
`infrastructure/ldap/certs/` (generado con `openssl`, válido 10 años, no el certificado
autogenerado de la imagen: ese vino con una CA vencida desde 2026-01-15).

## Generar el certificado local (no versionado)

`ldap.key` no se commitea (es una clave privada, ver `.gitignore`). Antes de levantar el
servicio por primera vez, generar el par cert/key:

```bash
mkdir -p infrastructure/ldap/certs
cd infrastructure/ldap/certs
openssl req -x509 -newkey rsa:2048 -keyout ldap.key -out ldap.crt -days 3650 -nodes \
  -subj "/O=Cyrvanta Lab/CN=ldap" \
  -addext "subjectAltName=DNS:ldap,DNS:localhost"
```

`ldap.crt` sí está versionado (es público, lo necesita el conector de directorio para validar
TLS). Si se regenera el par, hay que actualizar `ca_certificate_pem` en la config del conector.

## Configuración del conector de directorio en Cyrvanta (Administration > Directorio)

| Campo | Valor |
|---|---|
| `server_uri` | `ldap://ldap:389` |
| `use_starttls` | `true` |
| `ca_certificate_pem` | contenido de `infrastructure/ldap/certs/ldap.crt` |
| `bind_dn` | `cn=admin,dc=cyrvanta-lab,dc=local` |
| `bind_password` | `local-dev-only-ldap-admin-3f9a` |
| `base_dn` | `ou=people,dc=cyrvanta-lab,dc=local` |
| `user_filter` | `(uid={username})` |
| `subject_attribute` | `uid` |
| `email_attribute` | `mail` |
| `display_name_attribute` | `displayName` |

## Usuario de prueba sembrado

- Usuario: `jdoe`
- Contraseña: `CyrvantaLab#2026`
- DN: `uid=jdoe,ou=people,dc=cyrvanta-lab,dc=local`

Verificado extremo a extremo esta sesión: bind admin vía STARTTLS, búsqueda del usuario,
bind con la contraseña real del usuario, y rechazo correcto de contraseña incorrecta.
