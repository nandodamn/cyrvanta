# ADR 0006 — Postura temporal de seguridad de React Router

- Estado: Aceptado para bootstrap, revisar al publicarse corrección
- Fecha: 2026-07-27

## Contexto

El audit de npm reporta vulnerabilidades en todas las ramas actualmente
compatibles: 7.18.1 mantiene una vulnerabilidad alta asociada a RSC/server
actions y 6.30.4 presenta dos moderadas asociadas a redirects no confiables y
SSR hydration.

## Decisión

Se fija `react-router-dom` 7.18.1. Esta versión corrige
`GHSA-wrjc-x8rr-h8h6`, aplicable a mecanismos de navegación de `Link` y
`useNavigate`. El hallazgo restante `GHSA-qwww-vcr4-c8h2` afecta exclusivamente
las API RSC inestables, que Cyrvanta no importa ni habilita.

Cyrvanta opera como SPA declarativa CSR con `BrowserRouter`; no usa SSR, RSC,
server actions, `ScrollRestoration` ni destinos de navegación procedentes de
entrada no confiable. Los destinos siguen siendo rutas internas constantes.

## Consecuencias

`npm audit --omit=dev` conserva el hallazgo RSC de severidad alta por análisis
de versión, mitigado por ausencia total del modo afectado. No se considera
eliminado. React Router 8.3.0 lo corrige, pero requiere una actualización
coordinada de React y Vite que queda fuera de este cambio visual. El backlog
exige migrar cuando esa combinación se valide y repetir pruebas de rutas,
redirects y autenticación.
