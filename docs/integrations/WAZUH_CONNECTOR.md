# Conector Wazuh

**Tipo registrado:** `wazuh`  
**Schema de configuración:** `1`  
**Adaptador/normalizador:** `1.0`

Wazuh Manager se usa para salud y OpenSearch como fuente de alertas.
`WazuhIndexerClient` ejecuta búsquedas acotadas y `WazuhNormalizer` transforma
cada hit en `CanonicalFinding` antes de entregarlo al núcleo.

Capacidades actuales:

- polling de alertas y búsqueda temporal normalizada: sí;
- polling de incidentes externos: no;
- webhooks y sincronización bidireccional: no;
- recuperación raw y acciones de respuesta: no.

Las operaciones ausentes fallan con `UNSUPPORTED_CAPABILITY`.

La configuración v1 incluye host/puerto, URL del indexer, patrón, TLS,
referencias opcionales a secretos, timeout y tamaño máximo. El patrón se valida
y el cliente no sigue redirects.

En el laboratorio la composición obtiene valores de `WAZUH_*` y
`OPENSEARCH_*`, preservando la instalación. La persistencia tenant-owned existe,
pero aún no hay endpoint administrativo aprobado para escribirla.

El normalizador mapea timestamp, regla, nivel, grupos, agente, usuario e IP
cuando existen. Campos ausentes usan nulos/defaults seguros. La referencia raw
usa locator y hash SHA-256; no copia el payload a PostgreSQL.

