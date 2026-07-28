# ADR 0011 — Ledger epistemológico append-only

**Estado:** Aceptado
**Fecha:** 2026-07-28

## Contexto

El análisis actual mezcla resúmenes, confianza, técnicas y recomendaciones sin
persistencia por afirmación. `grounded=True` no prueba qué evidencia sustenta
cada conclusión y una salida de IA podría confundirse con un hecho.

## Decisión

- Los ocho tipos D-003 son códigos cerrados e inmutables.
- `DECISION`, `ACTION` y `RESULT` quedan bloqueados en esta etapa.
- Claims, evidencia, relaciones, evaluaciones y presentaciones son append-only.
- El rol de aplicación recibe solo `SELECT` e `INSERT` sobre el ledger.
- El autor humano no valida ni rechaza su propio claim.
- IA no crea `FACT`, `DECISION`, `ACTION` ni `RESULT`, ni evalúa claims.
- Los claims IA no evaluados se muestran como `PROPOSED`.
- Validar una hipótesis/inferencia no cambia su tipo.
- Traducciones son presentaciones versionadas, no nuevos claims.
- La respuesta de análisis actual permanece compatible y se acompaña de claims
  persistentes; los reportes no crean análisis nuevos.

## Parámetros iniciales

- statement: 2000 caracteres;
- explicación: 4000;
- criterio de hipótesis: 2000;
- hasta 16 códigos de evidencia faltante;
- hasta 32 enlaces de evidencia iniciales;
- listas API de 1 a 100 elementos, offset máximo 10000;
- idiomas de contenido: `es`, `en`, `und`;
- sin borrado automático hasta aprobar retención;
- tenant-admin recibe permisos `claim.read`, `claim.create`, `claim.assess`,
  `claim.translate`, `claim.retract` y `analysis.read`.

El schema Ollama de esta etapa conserva exclusivamente los resúmenes
estructurados ya validados. Esos resúmenes originan una inferencia propuesta;
la IA no produce directamente relaciones, evaluaciones ni tipos privilegiados.

## Consecuencias

- Se conserva historia completa y contradicciones visibles.
- El ledger agrega almacenamiento e índices acotados en PostgreSQL.
- Los análisis repetidos usan claves determinísticas para no duplicar claims
  idénticos del mismo input.
- La UI puede diferenciar tipo, origen y estado sin interpretar texto.
- Retención y roles adicionales siguen siendo puertas de gobierno.
