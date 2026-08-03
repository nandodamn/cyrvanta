# ADR 0016 — Feedback y memoria gobernada

**Estado:** Aceptado  
**Fecha:** 2026-08-01

## Contexto

Cyrvanta ya conserva procedencia, claims, correlación, riesgo, decisiones,
ejecuciones y resultados, pero no dispone de feedback normalizado ni memoria
operacional gobernada. Convertir observaciones históricas en excepciones o
aprendizaje automático introduciría autoridad no auditada y riesgo de mezcla
entre tenants.

## Decisión

Adoptar el contrato de
`docs/specifications/PHASE_22_GOVERNED_FEEDBACK_MEMORY.md` con las doce
decisiones ratificadas explícitamente, sin autoridad automática:

- ocho outcomes normalizados separados por detección y efectividad;
- influencia inicial exclusivamente `OBSERVATIONAL_ONLY`;
- autor distinto de revisor y activador;
- vigencia máxima inicial de 90 días;
- muestra mínima de 20 casos reales para tendencias;
- exclusión de sintéticos de memoria activa y métricas reales;
- ausencia de perfiles personales y texto libre no acotado;
- correcciones mediante nuevas versiones inmutables;
- aislamiento exclusivo por tenant;
- IA limitada a sugerencias estructuradas;
- UI y explicación como únicos consumidores iniciales;
- PostgreSQL como sistema de registro con historia append-only.

La memoria no autoriza, ejecuta ni altera retrospectivamente resultados. Cada
influencia conserva el resultado base y una explicación reproducible.

## Consecuencias positivas

- Feedback y correcciones quedan auditables sin destruir historia.
- Una memoria expirada o desactivada deja de influir inmediatamente.
- Los datos sintéticos no contaminan tendencias reales.
- La separación de funciones evita autoaprobación.
- Los módulos consumidores pueden fallar cerrado y volver al resultado base.

## Costos

- Se agregan ciclo de revisión, expiración y registros de influencia.
- Las métricas requieren ventana, definición versionada y tamaño de muestra.
- La UI debe explicar base e influencia por separado.
- La retención legal completa requerirá una política corporativa posterior.

## Alternativas descartadas

- Reentrenar modelos automáticamente con feedback.
- Usar OpenSearch o un vector store como fuente de verdad.
- Modificar feedback o versiones aprobadas en lugar de supersederlas.
- Compartir memoria entre tenants.
- Activar tendencias con fixtures o muestras insuficientes.
- Permitir que memoria autorice acciones o cambie políticas.

## Rollback

Un kill switch deshabilita influencia sin borrar evidencia. Las versiones se
desactivan mediante eventos append-only. Los consumidores vuelven al resultado
base determinístico. El downgrade físico falla si existe evidencia no
exportada.

## Estado de aprobación

Aceptado por ratificación humana explícita el 2026-08-01 junto con las doce
decisiones materiales y la autorización para cerrar el GATE de Etapa 8.
