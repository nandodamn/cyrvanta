# ADR 0013 — ATT&CK versionado, riesgo determinista y explicabilidad

**Estado:** Aceptado

**Fecha:** 2026-07-28

## Contexto

Cyrvanta dispone de findings canónicos, claims append-only y correlación
determinista multi-fuente. La vista demo aún presenta un catálogo MITRE estático,
mappings no sustentados y un riesgo provisional que mezcla severidad con una
confianza fija.

Para ser auditable y neutral de proveedor, la plataforma necesita distinguir el
catálogo global, la evidencia de cada tenant y los resultados históricos
reproducibles. La IA no puede convertirse en autoridad de mapping ni de riesgo.

## Decisión

- Enterprise ATT&CK v19.1 es el baseline inicial, importado desde un bundle STIX
  2.1 offline mediante CLI, con hash SHA-256 y activación explícita.
- El catálogo global y sus releases son inmutables; mappings, evaluaciones y
  explicaciones pertenecen al tenant y son append-only.
- Solo se importan tácticas, técnicas/sub-técnicas, mitigaciones, relaciones y
  marking definitions incluidos en la allowlist aprobada.
- La regla `credential-attack` v2 asigna T1110 a fallos de autenticación, T1078
  a autenticaciones exitosas y T1098 únicamente a cambios de privilegios.
- El riesgo v1 suma exactamente cinco factores deterministas: severidad,
  corroboración, diversidad de fuentes, mappings ATT&CK sustentados y calidad
  de normalización. Ni la confianza de IA ni el score de correlación participan.
- Cada resultado conserva definición, versión, snapshot, factores, evidencias y
  fingerprint idempotente.
- La explicación primaria se genera con plantillas deterministas bilingües. Una
  redacción opcional usa exclusivamente `AIProvider` y siempre falla hacia la
  plantilla segura.
- Catálogo e importación son capacidades de plataforma; lectura, validación,
  recálculo y generación tenant-owned se autorizan mediante permisos explícitos.
- La entrega reutiliza outbox/inbox y las operaciones multi-entidad se confirman
  en una única transacción PostgreSQL.
- El endpoint heredado `/api/v1/mitre/techniques` conserva su forma durante la
  transición.

Los estados, límites, pesos, bandas, permisos, eventos y criterios completos son
los aprobados en `docs/specifications/PHASE_19_MITRE_RISK_EXPLAINABILITY.md`.

## Consecuencias

La UI puede explicar cada punto del riesgo y cada mapping con evidencia
verificable, aun sin Ollama. Actualizar ATT&CK crea una release nueva y no
reescribe resultados históricos. El importador requiere un bundle oficial
obtenido fuera de migraciones y del arranque normal.

Los workflows n8n, recomendaciones y doble aprobación quedan fuera de esta
decisión y conservan sus puertas de gobierno posteriores.

## Reversión

Una release activa puede sustituirse explícitamente por otra ya importada. El
consumidor de enriquecimiento puede desactivarse sin detener la ingesta ni la
correlación. No se borran mappings, riesgos, explicaciones, claims ni eventos
históricos. El downgrade de esquema se bloquea cuando existan datos de esta
etapa.
