# ADR 0017 — Cyrvanta Playbook Engine nativo con n8n opcional

**Estado:** Aceptado  
**Fecha:** 2026-08-01

## Contexto

Fase 21 y ADR 0015 establecieron que Cyrvanta posee el dominio, autorizaciones,
versiones, ejecuciones y evidencia de playbooks; n8n es un adaptador reemplazable.
El estado autoritativo ya reside en PostgreSQL, pero el binding actual limita el
motor a `N8N` y el dispatcher concreto depende de ese producto.

Un motor restringido de ciberseguridad permite controlar amenazas, aprobación,
trazabilidad y propiedad intelectual. Recrear un automatizador generalista y su
ecosistema no ofrece la misma diferenciación.

## Decisión

Adoptar `docs/specifications/PHASE_21A_CYRVANTA_PLAYBOOK_ENGINE.md`:

- motor nativo detrás de un puerto estable;
- n8n como adaptador opcional;
- JSON portable v1, restringido y determinístico;
- sólo acciones allowlisted y condiciones declarativas en v1;
- sin código arbitrario, shell, loops o plugins no firmados;
- ejecución asíncrona en los workers existentes inicialmente;
- PostgreSQL, RLS, outbox/inbox, claim, idempotencia y auditoría autoritativos;
- secretos sólo mediante aliases y secret store;
- activación por feature flag, tenant y binding;
- retiro de n8n del perfil estándar sólo tras criterios verificables y una
  aprobación operativa separada.

## Consecuencias positivas

- Propiedad intelectual y control del roadmap de ejecución.
- Menor superficie que un motor generalista.
- Semántica nativa de incidentes, impacto, autorizaciones y evidencia.
- Multitenancy y auditoría coherentes con Cyrvanta.
- Menor dependencia para el conjunto estándar.
- Compatibilidad con n8n durante la transición y en casos extendidos.

## Costos y riesgos

- Cyrvanta mantiene runner, recovery, conectores y schemas.
- Deben probarse crash recovery, retries, timeout ambiguo y DLQ.
- El catálogo nativo será inicialmente menor que el de n8n.
- El editor visual profesional completo queda diferido.
- La coexistencia requiere paridad sin doble efecto.
- Cada conector `LIVE` necesita threat model y aprobación operativa.

## Alternativas

### Mantener sólo n8n

Reduce desarrollo, pero conserva dependencia para el flujo estándar y no
aprovecha completamente el dominio durable de Cyrvanta.

### Sustituir n8n inmediatamente

Descartada por riesgo y falta inicial de paridad de conectores y recovery.

### Fork o clon completo de n8n

Descartado por superficie, mantenimiento y consideraciones de licencia sin
concentrarse en la diferenciación de ciberseguridad.

### Motor especializado con adaptadores opcionales

Recomendado: concentra inversión en seguridad, gobierno y trazabilidad y conserva
n8n donde todavía aporte valor.

## Compatibilidad

ADR 0015 continúa vigente. Este ADR amplía el conjunto de motores y formaliza un
runner first-party. Bindings, ejecuciones y evidencia `N8N` no se reescriben.
ADR 0018 refina la selección: el motor nativo es el predeterminado y n8n queda
opcional globalmente y por playbook, con secretos técnicos automatizados.

## Estado de aprobación

Aceptado por ratificación humana explícita el 2026-08-01 junto con las 20
decisiones de Fase 21-A y la autorización para implementar el motor manteniendo
n8n como adaptador opcional.