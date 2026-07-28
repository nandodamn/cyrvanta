# ADR 0005 — Decisiones reversibles del bootstrap de autenticación

- Estado: Aceptado para bootstrap
- Fecha: 2026-07-27

## Contexto

La iteración exige login solo con email y contraseña, sin aceptar tenant en el
body, y limita las tablas iniciales. Falta el contrato final de identidad.

## Decisión

Durante el bootstrap el email local será globalmente único, permitiendo resolver
al usuario y derivar su tenant después de verificar credenciales. Los refresh
tokens serán opacos, rotatorios y almacenados como hash en Redis con TTL; no se
añade una tabla fuera del alcance aprobado. Los access tokens serán JWT
asimétricamente no requeridos en esta fase y usarán un secreto configurable.

## Consecuencias

Es una restricción temporal y reversible. La fase formal de identidad deberá
decidir usuarios multi-tenant, selector de tenant y persistencia durable de
sesiones. Reiniciar Redis invalida sesiones refresh de forma segura.
