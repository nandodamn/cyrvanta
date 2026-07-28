# Modelo canónico de seguridad

Este documento resume el contrato vigente del adaptador. Su evolución
versionada y la persistencia propuesta para la Etapa 2 se especifican, todavía
sin autorización de implementación, en
`docs/specifications/PHASE_16_CANONICAL_SECURITY_MODEL_PROVENANCE.md`.

`CanonicalFinding` representa una detección sin semántica exclusiva de
proveedor: origen e instancia, objeto e ID externos, timestamps, título,
descripción, severidad 0–100, confianza 0–1, categoría, estado, regla,
entidades, IP, proceso, archivo, indicadores, etiquetas y referencia de
evidencia.

`CanonicalExternalIncident` representa agrupaciones externas como offenses,
incidentes, notables, casos o grupos de alertas sin afirmar equivalencia
exacta. Los campos no disponibles permanecen nulos o la capacidad se declara
ausente.

Los lotes contienen elementos, próximo cursor y watermark opcional. Las
búsquedas están limitadas por texto, tiempo y cantidad.

## Invariantes

- `tenant_id` se conserva desde la solicitud hasta el sink.
- Origen, ID externo y provenance no se reescriben silenciosamente.
- Severidad y confianza usan escalas canónicas validadas.
- El contenido externo es no confiable.
- PostgreSQL conserva referencias o snapshots mínimos, no telemetría cruda.
- Cambiar la representación requiere nueva versión normalizada.
