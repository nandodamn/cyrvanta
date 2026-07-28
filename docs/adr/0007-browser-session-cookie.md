# ADR 0007 — Sesión web persistente mediante cookie de renovación

- Estado: Aceptado
- Fecha: 2026-07-27

## Contexto

El backend ya emite access tokens breves y refresh tokens opacos, rotatorios,
revocables y almacenados como digest en Redis. El frontend guardaba ambos en
`sessionStorage`, por lo que una pestaña nueva no recuperaba la sesión y un
script ejecutado en el origen podía leer el refresh token.

La revisión humana aprobó que la sesión pueda recordarse de forma segura y que
el usuario controle la persistencia mediante «Recordar sesión».

## Decisión

- El refresh token se transporta en una cookie `HttpOnly`,
  `SameSite=Strict`, limitada a `/api/v1/auth`.
- La cookie es `Secure` por defecto fuera de desarrollo y pruebas. El despliegue
  puede exigirla explícitamente con `SESSION_COOKIE_SECURE`.
- Sin «Recordar sesión» se emite una cookie de sesión. Con la opción activada se
  aplica el TTL configurado de refresh.
- El access token solo vive en memoria del frontend.
- Al iniciar la aplicación, el frontend rota la cookie mediante `/auth/refresh`.
- Las solicitudes de refresh y logout basadas en cookie exigen
  `X-CSRF-Guard: 1`; `SameSite=Strict` aporta una segunda barrera.
- Logout elimina la cookie y revoca el digest en Redis.
- Refresh y logout aceptan temporalmente un refresh token en el body para
  sesiones ya emitidas, pero las nuevas respuestas no exponen ese token.
- Login local y LDAP/AD comparten exactamente la misma política de sesión.

## Consecuencias

Las pestañas del mismo navegador comparten la sesión. Si el usuario marca la
opción, la sesión puede recuperarse tras cerrar y abrir el navegador hasta el
TTL, salvo logout, revocación, desactivación del usuario o pérdida de Redis.

La terminación TLS es obligatoria en producción para usar cookies `Secure`.
Cambiar de origen requiere mantener CORS con allowlist explícita y credenciales.

## Reversión

El frontend puede volver a exigir login al iniciar eliminando la restauración
automática. El backend puede dejar de emitir la cookie sin modificar tablas ni
migraciones; los refresh tokens existentes caducan o se invalidan al reiniciar
Redis.
