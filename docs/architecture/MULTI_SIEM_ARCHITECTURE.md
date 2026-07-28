# Arquitectura multi-SIEM de Cyrvanta

**Estado:** Aprobada e implementada como base arquitectónica.  
**Alcance:** contratos, Wazuh, persistencia genérica y pruebas; no implementa
otros conectores.

## Límite

`Security Integrations` es el único contexto que conoce formatos, índices,
errores o transporte de un SIEM. El resto de Cyrvanta consume
`CanonicalFinding`, `CanonicalExternalIncident`, evidencia canónica y
capacidades declaradas.

```text
Wazuh + OpenSearch -> WazuhSIEMAdapter -> modelo canónico -> Cyrvanta Core
SIEM futuro       -> adaptador futuro -> modelo canónico -> Cyrvanta Core
```

El registro resuelve una fábrica por `connector_type`; producción registra
únicamente `wazuh`. Agregar otro conector no requiere condicionales ni cambios
en el dominio.

## Capas

- `domain`: modelos canónicos, capacidades, salud y errores. No importa Wazuh.
- `application`: `SIEMConnectorPort` y sincronización independiente del
  fabricante.
- `infrastructure/registry`: registro de fábricas.
- `infrastructure/wazuh`: configuración v1, cliente restringido, schemas,
  normalizador y adaptador.
- `testing`: conector falso no registrado en producción.

## Flujo incremental

1. El orquestador obtiene configuración tenant-owned.
2. El registro crea el adaptador.
3. Se consulta `get_capabilities`.
4. El servicio solicita un lote con cursor/watermark y límites.
5. El adaptador normaliza antes de devolver.
6. El consumidor valida `tenant_id` y entrega una clave de idempotencia al
   sink persistente.
7. Cursor, watermark, salud y error canónico se guardan bajo el mismo tenant.

La clave se deriva de tenant, integración, tipo e ID de origen y hash/timestamp
de origen. La deduplicación definitiva también debe apoyarse en una restricción
persistente del receptor.

## Seguridad

- RLS forzado en configuración, sincronización e historial.
- Configuración cifrada como bloque opaco; los secretos se referencian.
- Consultas Wazuh construidas por el adaptador contra un patrón validado.
- TLS configurable, sin redirects, con timeout, límite de lote y de respuesta.
- Errores y salud solo exponen mensajes redactados.
- Ningún payload crudo ilimitado se guarda en PostgreSQL.

## IA y respuesta

La IA recibe un `CanonicalFinding` serializado y delimitado, nunca un payload
Wazuh directo. n8n sigue siendo un adaptador de automatización. Acciones
genéricas (notificar, escalar, crear ticket) pertenecen a playbooks; una acción
propia de un SIEM exige una capacidad y puerto de respuesta del conector.

## Compatibilidad y límites actuales

La ruta existente de salud conserva su forma. Wazuh se comprueba mediante el
adaptador y sus alertas pueden consultarse y normalizarse desde OpenSearch.
La migración crea persistencia genérica, pero la administración CRUD de
conectores y la programación durable de polling/DLQ quedan para una
especificación de API y jobs posterior. La configuración local actual se
compone desde variables de entorno para no romper la demo instalada.

