# Contrato de conectores SIEM

## Puerto

`SIEMConnectorPort` expone `health_check`, `get_capabilities`,
`fetch_findings`, `fetch_incidents`, `search_events`, `get_evidence`,
`acknowledge_external_incident` y `close_external_incident`.

Cada operación tenant-owned recibe `tenant_id`. Un conector debe declarar sus
capacidades y devolver `UNSUPPORTED_CAPABILITY` cuando la operación no exista.
No se permiten valores nulos que aparenten éxito.

## Errores

Los códigos permitidos son:

`CONNECTOR_UNAVAILABLE`, `AUTHENTICATION_FAILED`, `AUTHORIZATION_FAILED`,
`RATE_LIMITED`, `INVALID_CONFIGURATION`, `TLS_ERROR`, `SOURCE_TIMEOUT`,
`SOURCE_SCHEMA_CHANGED`, `CURSOR_INVALID`, `SEARCH_FAILED`,
`EVIDENCE_NOT_FOUND` y `UNSUPPORTED_CAPABILITY`.

Los mensajes son seguros para logs y nunca contienen credenciales, tokens,
payloads completos o respuestas crudas.

## Configuración y versiones

Una fábrica recibe `ConnectorConfiguration` con integración, tenant, tipo,
versión y valores ya recuperados de almacenamiento cifrado. Cada adaptador
valida su schema versionado antes de abrir una conexión. Una migración entre
schemas debe ser explícita, reversible y probada.

## Reglas para un nuevo conector

1. Implementar y probar configuración y normalizador en infraestructura.
2. Implementar el puerto y fallar explícitamente en capacidades ausentes.
3. Traducir todos los datos al modelo canónico.
4. Registrar una fábrica en composición; no modificar el dominio.
5. Probar aislamiento, idempotencia, redacción, límites y errores.
6. No mostrarlo disponible hasta superar una prueba real aprobada.

