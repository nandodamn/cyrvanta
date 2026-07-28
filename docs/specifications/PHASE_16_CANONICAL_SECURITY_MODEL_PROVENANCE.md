# Fase 16 — Modelo canónico de seguridad y procedencia

**Estado:** APROBADO PARA IMPLEMENTACIÓN — autorizado por instrucción humana el
2026-07-28.
**Fecha:** 2026-07-28
**Implementación autorizada:** sí.

## 1. Objetivo

Definir el contrato neutral de proveedor que permitirá recibir findings desde
Wazuh y futuros adaptadores sin acoplar el dominio a sus formatos, preservando:

- tenant y origen verificables;
- identidad e idempotencia deterministas;
- historial de normalización;
- calidad y limitaciones explícitas;
- separación entre referencias durables en PostgreSQL y telemetría raw en
  OpenSearch;
- compatibilidad con las pantallas y API de alertas existentes.

Esta fase no autoriza migraciones, tablas, endpoints, productores de eventos ni
conectores adicionales. Especifica esas piezas para revisión.

## 2. Alcance

### 2.1 Incluido

- `CanonicalFindingV1` como único objeto canónico persistible de esta fase.
- Procedencia, fingerprints, tiempos y evaluación de normalización.
- Referencias acotadas a activo, cuenta, indicador, red, proceso y archivo.
- Persistencia lógica versionada vinculada a `alert_references`.
- Evento interno posterior a persistencia.
- Contrato de conformidad para Wazuh y adaptadores de prueba.
- RLS, auditoría, observabilidad, pruebas y rollback.

### 2.2 Fuera de alcance

- Persistir incidentes externos.
- Unificar findings en incidentes Cyrvanta.
- Resolver o fusionar entidades.
- Crear un lago de datos o copiar telemetría raw a PostgreSQL.
- Diseñar claims, correlación, MITRE, riesgo o respuesta.
- Agregar CRUD de integraciones o nuevas pantallas.
- Declarar conectores futuros como reales sin credenciales y datos reales.

`CanonicalExternalIncident` permanece como contrato experimental de puerto y no
se persiste en esta fase. Alertas, eventos y casos propios de cada SIEM se
traducen a `CanonicalFindingV1` solo cuando el adaptador pueda satisfacer sus
invariantes.

## 3. Diagnóstico del estado actual

La base multi-SIEM ya contiene:

- puerto `SIEMConnectorPort`;
- registro de conectores desacoplado;
- adaptador y normalizador Wazuh;
- fixtures para pruebas contractuales;
- búsqueda incremental mediante cursor/watermark;
- tabla `alert_references` usada por incidentes y API actuales.

Brechas que esta especificación resuelve:

1. Los modelos de dominio actuales dependen de Pydantic.
2. `occurred_at` es obligatorio y Wazuh inventa el instante actual cuando el
   origen no provee un timestamp válido.
3. La idempotencia se calcula en memoria y no tiene garantía durable.
4. No existe historial de cambios del mismo objeto externo.
5. No se registra de forma estructurada la calidad de normalización.
6. Las referencias de entidad no declaran tipo, namespace ni valor normalizado.
7. `alert_references` no conserva integración, versión de adaptador,
   normalizador, schema ni fingerprint.
8. La severidad canónica numérica y la severidad textual de la proyección
   actual no tienen una conversión contractual.

## 4. Decisiones vinculantes si se aprueba

### 4.1 Objeto canónico inicial

`CanonicalFindingV1` representa una observación de seguridad normalizada, no un
incidente confirmado ni una decisión. Sus valores no se presentan como hechos
validados más allá de lo observado por la fuente.

El dominio utilizará dataclasses inmutables y value objects sin Pydantic,
SQLAlchemy, FastAPI, OpenSearch o SDK de proveedor. Los DTO Pydantic quedan en
los límites de entrada/salida. La migración será compatible y gradual.

### 4.2 Identidad estable y revisiones

Un finding posee:

- una identidad estable de agregado Cyrvanta;
- una identidad externa dentro de tenant e integración;
- cero o más revisiones normalizadas append-only;
- una proyección actual compatible en `alert_references`.

Recibir el mismo payload no crea una revisión ni repite efectos. Recibir un
payload distinto para la misma identidad externa crea una nueva revisión y
actualiza la proyección actual en una única transacción.

No se sobrescribe ni elimina silenciosamente una revisión previa.

### 4.3 Tenant confiable

El `tenant_id` se obtiene del contexto seguro del job o caso de uso. El
adaptador no puede elegirlo ni cambiarlo a partir del payload del proveedor.

Una discrepancia entre tenant esperado y resultado normalizado produce rechazo
permanente y señal de seguridad. No se intenta corregir el tenant.

### 4.4 Telemetría raw

El payload original permanece en OpenSearch o en el sistema fuente. PostgreSQL
guarda solo:

- referencia estable y acotada;
- hash del payload;
- campos canónicos mínimos;
- procedencia y evaluación de normalización.

No se persisten documentos raw, comandos completos no acotados, credenciales,
tokens ni blobs de evidencia en PostgreSQL.

## 5. Contrato lógico `CanonicalFindingV1`

| Campo | Tipo lógico | Regla |
|---|---|---|
| `finding_id` | UUID | Identidad estable de Cyrvanta. |
| `tenant_id` | UUID | Contexto seguro, obligatorio. |
| `integration_id` | UUID | Configuración concreta del conector. |
| `source_system` | código | Minúsculas, estable y no localizado. |
| `source_instance_id` | string acotado | Instancia externa, sin secretos. |
| `source_object_type` | código | Tipo neutral declarado por adaptador. |
| `source_object_id` | string acotado | Identificador externo obligatorio. |
| `source_occurred_at` | UTC/null | Timestamp declarado por la fuente. |
| `observed_at` | UTC | Momento real de ingestión por Cyrvanta. |
| `effective_at` | UTC | Tiempo usado para orden y ventanas. |
| `effective_time_basis` | enum | `SOURCE`, `DERIVED` o `INGESTED`. |
| `title` | string acotado | Texto no confiable, obligatorio. |
| `description` | string acotado/null | Sanitizado para presentación. |
| `severity_score` | entero 0–100 | Conversión versionada. |
| `confidence` | decimal 0–1/null | Conserva el contrato actual; ausente si la fuente no lo expresa. |
| `category` | código/string acotado | Taxonomía del normalizador. |
| `status` | código/null | Estado externo, no ciclo de incidente Cyrvanta. |
| `rule_id` | string acotado/null | Identidad de regla externa. |
| `entity_references` | colección acotada | Referencias, no entidades resueltas. |
| `evidence_reference` | objeto/null | Localizador permitido, sin secreto. |
| `payload_fingerprint` | SHA-256 | Hash determinista del payload de origen. |
| `normalization` | evaluación | Versiones, calidad e incidencias. |
| `schema_version` | entero | Inicia en `1`. |

Todo string y colección tendrá límites físicos explícitos antes de implementar.
Esos tamaños quedan pendientes de validación con fixtures Wazuh reales y
volúmenes aprobados; no se inventan en este DRAFT.

## 6. Semántica temporal

El normalizador nunca inventa un timestamp de origen.

- Si existe timestamp válido del proveedor:
  `source_occurred_at = effective_at` y basis `SOURCE`.
- Si existe un timestamp derivable mediante una regla documentada:
  `source_occurred_at = null`, `effective_at` usa el derivado y basis
  `DERIVED`; la regla queda en las incidencias de normalización.
- Si no existe tiempo utilizable:
  `source_occurred_at = null`, `effective_at = observed_at` y basis
  `INGESTED`; la calidad no puede ser `VALID`.

`observed_at` siempre es el reloj de Cyrvanta y no se usa para simular que la
fuente informó el momento del hecho.

## 7. Fingerprints e idempotencia

### 7.1 Canonicalización

Los hashes usan SHA-256 sobre bytes UTF-8 de JSON canónico:

- claves ordenadas;
- separadores sin espacios;
- Unicode normalizado a NFC;
- timestamps UTC en formato contractual;
- números sin representaciones equivalentes ambiguas;
- versión de algoritmo registrada.

### 7.2 Identidad externa

La identidad lógica se determina por:

```text
(tenant_id, integration_id, source_object_type, source_object_id)
```

No se correlacionan identidades entre tenants. `source_system` y
`source_instance_id` forman parte de procedencia y validación de la integración,
pero `integration_id` delimita la identidad durable.

### 7.3 Fingerprint de payload

`payload_fingerprint` se calcula sobre el documento de origen recibido antes de
normalizar. Si el proveedor no entrega el documento completo, el adaptador
construye un material de fingerprint explícito y versionado y lo declara en la
evaluación.

La clave durable de deduplicación es:

```text
(tenant_id, integration_id, source_object_type,
 source_object_id, payload_fingerprint)
```

La versión del algoritmo y el modo (`RAW_DOCUMENT` o `ADAPTER_MATERIAL`) se
persisten. Cambiar el algoritmo requiere migración/versionado y no reinterpreta
hashes históricos.

## 8. Calidad de normalización

`NormalizationAssessmentV1` contiene:

| Campo | Regla |
|---|---|
| `status` | `VALID`, `PARTIAL` o `REJECTED`. |
| `completeness_score` | Entero 0–100 calculado por regla versionada. |
| `issue_codes` | Códigos allowlisted, acotados y no localizados. |
| `adapter_name` | Código estable. |
| `adapter_version` | Versión del adaptador. |
| `normalizer_version` | Versión de reglas de mapeo. |
| `fingerprint_version` | Versión de canonicalización/hash. |
| `canonical_schema_version` | Versión de `CanonicalFinding`. |

Reglas:

- `REJECTED` no se persiste como finding ni genera evento normalizado.
- Identidad, tenant o procedencia inválidos siempre producen `REJECTED`.
- Campos opcionales ausentes pueden producir `PARTIAL`.
- Basis temporal `INGESTED` produce al menos `PARTIAL`.
- El score es diagnóstico, no probabilidad ni confianza de amenaza.
- Los mensajes traducidos se generan desde `issue_codes`; no se persiste texto
  localizado.

Los pesos exactos del score se definirán con fixtures aprobados antes de
implementar. El contrato no fija números arbitrarios.

## 9. Referencias canónicas de entidad

`CanonicalEntityReferenceV1` contiene:

- `kind`: `ASSET`, `ACCOUNT`, `IP_ADDRESS`, `DOMAIN`, `URL`, `HASH`,
  `PROCESS` o `FILE`;
- `value`: valor observado acotado;
- `namespace`: fuente o ámbito cuando sea necesario;
- `normalized_value`: valor determinista cuando exista una regla aprobada;
- `display_value`: opcional y sanitizado;
- `attributes`: únicamente allowlist tipada por `kind`.

Estas referencias no crean una entidad maestra, no fusionan valores y no
correlacionan por sí solas. La resolución tenant-scoped y reversible corresponde
a una fase posterior.

Datos sensibles, command lines y rutas se minimizan. Los atributos libres o no
acotados permanecen en la evidencia raw.

## 10. Modelo lógico de persistencia propuesto

### 10.1 `alert_references`

Se conserva como identidad estable y proyección actual para evitar romper API,
incidentes, dashboard y datos existentes. No se renombra en esta fase.

Al implementar, su contrato se ampliaría solo con las referencias necesarias
para identificar la integración y la revisión vigente. La conversión
`severity_score` a severidad textual será determinista, versionada y compatible
con los valores actuales.

### 10.2 `finding_revisions`

Tabla append-only candidata, tenant-owned, vinculada a `alert_references`.
Contendría:

- identidad de revisión y número monotónico por finding;
- integración e identidad externa;
- tiempos y basis temporal;
- campos canónicos mínimos;
- fingerprints y sus versiones;
- evaluación de normalización;
- referencia raw permitida;
- timestamps de creación.

No contendría payload raw. Una constraint materializaría la clave durable de
deduplicación definida en 7.3.

### 10.3 Transacción

Una ingestión válida realiza atómicamente:

1. reclamar/crear identidad estable;
2. deduplicar por fingerprint;
3. agregar revisión si corresponde;
4. actualizar `alert_references`;
5. registrar el evento en outbox.

Si cualquiera falla, no queda revisión, proyección ni evento parcial.

### 10.4 RLS

- Ambas relaciones habilitan y fuerzan RLS.
- Todas las FK y constraints relevantes incluyen/verifican tenant.
- El worker abre `tenant_session` antes de persistir.
- No existe consulta cross-tenant para adaptadores.
- Funciones administrativas futuras requerirán contrato y privilegio separado.

Los nombres de columnas, tipos, longitudes, índices y SQL definitivos no se
aprueban con este documento. Se presentarán en la migración candidata después
de aprobar el modelo lógico.

## 11. Evento interno propuesto

Nombre:

```text
security.finding.normalized
```

Schema version `1`. Se registra mediante el outbox aprobado en Fase 15 después
de crear una revisión nueva.

Payload mínimo candidato:

- `finding_id`;
- `revision_id`;
- `revision_number`;
- `integration_id`;
- `source_system`;
- `severity_score`;
- `effective_at`;
- `normalization_status`.

El envelope aporta tenant, event ID, correlación y causalidad. El payload no
incluye documento raw, descripción, indicadores, rutas ni secretos.

Un duplicado de payload no genera otro evento. Una nueva revisión sí genera uno
con el mismo `finding_id` y distinta `revision_id`.

## 12. Puertos y límites de código

Contratos candidatos:

- `SecurityFindingSource`: obtiene objetos externos acotados y cursor.
- `FindingNormalizer`: transforma entrada de proveedor en resultado
  `accepted` o `rejected`.
- `FindingRepository`: persiste identidad, revisión y proyección dentro de una
  sesión tenant-scoped.
- `FindingIngestionService`: orquesta validación, persistencia y evento.

Reglas:

- Solo infraestructura conoce Wazuh/OpenSearch.
- El normalizador es puro respecto a red y base de datos.
- El reloj se inyecta.
- El tenant no forma parte de datos controlables por el adaptador.
- Ningún puerto devuelve querysets o clientes de infraestructura.
- Errores externos se traducen a códigos canónicos existentes.

## 13. Conformidad de adaptadores

El mismo kit contractual se ejecutará contra:

1. Wazuh con fixtures versionados y marcados como sintéticos.
2. Un adaptador de referencia in-memory, exclusivamente de prueba.

Ambos deben producir el mismo contrato canónico para observaciones
semánticamente equivalentes. El adaptador de prueba nunca aparece en el
registro de producción ni en UI como integración real.

Pruebas con Wazuh real se habilitan cuando existan manager/index, credenciales,
tenant e índices con datos autorizados. El contrato no depende de disponer hoy
de una empresa o Active Directory.

Conectores QRadar, Splunk, Sentinel, Elastic u otros permanecen `planned` hasta
tener adaptador, contract tests, configuración segura y verificación real.

## 14. API, UI e i18n

No se agrega API ni UI pública.

La API de alertas existente seguirá leyendo `alert_references`. La procedencia
detallada y el historial de revisiones no se exponen hasta aprobar permisos,
paginación, redacción y contrato OpenAPI.

Los códigos de estado, calidad e incidencias son estables y no localizados. La
UI futura los traducirá al español e inglés.

## 15. Seguridad y auditoría

- Todo texto externo se considera no confiable y se escapa en UI.
- URLs/localizadores usan esquemas allowlisted y nunca contienen credenciales.
- Se limita tamaño antes de normalización cuando sea posible.
- Rechazos por tenant, identidad o procedencia generan log de seguridad.
- La auditoría registra cambios administrativos de configuración; no copia
  telemetría raw.
- La creación automática de cada revisión se rastrea por evento y logs
  estructurados, evitando duplicar un audit event de alto volumen.
- Logs no contienen payload raw, tokens, command lines ni descripciones
  completas.
- La retención de revisiones queda sujeta a la política aprobada por tenant y
  mínimos de plataforma; no se implementa borrado sin esa especificación.

## 16. Observabilidad

Métricas mínimas:

- objetos recibidos, aceptados, parciales, rechazados y duplicados;
- revisiones creadas por integración;
- latencia de fuente a ingestión y de ingestión a persistencia;
- basis temporal utilizado;
- incidencias de normalización por código;
- errores de cursor, proveedor, persistencia y publicación;
- backlog por integración sin incluir datos de otros tenants.

Logs estructurados:

- tenant autorizado, integración, sistema fuente;
- tipo e ID externo hash/redactado cuando corresponda;
- finding/revisión, fingerprint truncado para diagnóstico;
- versión de adaptador/normalizador/schema;
- correlation/event IDs y código de resultado.

## 17. Pruebas obligatorias

### Dominio y normalización

- objetos inmutables y sin dependencias de infraestructura;
- timestamp de origen ausente o inválido nunca se inventa;
- severidad, confianza y referencias respetan límites;
- score/calidad reproducibles para la misma versión;
- Unicode y JSON canónico producen fingerprints estables;
- payload distinto crea nueva revisión lógica.

### Persistencia y multitenancy

- duplicado concurrente crea una sola revisión;
- nueva revisión actualiza proyección atómicamente;
- rollback no deja proyección/evento parcial;
- tenant A no lee, deduplica ni referencia filas de B;
- integración de A no puede inyectar tenant B;
- PostgreSQL no contiene payload raw.

### Contrato y adaptadores

- Wazuh y referencia in-memory satisfacen el mismo suite;
- cursor/watermark no pierde ni duplica efectos;
- error externo se traduce a código canónico;
- fixture y modo simulado están identificados explícitamente;
- adaptadores futuros no requieren cambiar el dominio.

### Evento

- una revisión nueva registra `security.finding.normalized`;
- un duplicado no registra otro evento;
- envelope conserva tenant/correlación/causalidad;
- payload cumple minimización y límite;
- redelivery no duplica el efecto del consumidor.

### Compatibilidad

- endpoints y pantallas actuales de alertas conservan comportamiento;
- incidentes existentes mantienen sus referencias;
- modo español/inglés y temas no dependen del proveedor;
- migración de datos existentes es determinista y reversible.

## 18. Estrategia de implementación propuesta

Solo después de aprobación:

1. convertir el contrato DRAFT en decisión aprobada;
2. fijar límites físicos con fixtures Wazuh representativos;
3. introducir dataclasses/value objects y adaptadores de compatibilidad;
4. crear migración candidata con RLS y backfill seguro;
5. implementar repositorio y servicio transaccional;
6. corregir Wazuh para no inventar tiempos;
7. registrar el evento mediante Fase 15;
8. ejecutar suites unitarias, contractuales, RLS y Compose;
9. probar con datos Wazuh reales cuando estén disponibles;
10. documentar resultado y limitaciones observadas.

## 19. Rollback

- Productor de ingestión nuevo detrás de configuración segura y desactivable.
- API actual continúa sobre `alert_references`.
- El despliegue puede detener ingestión sin perder telemetría en la fuente.
- Downgrade no elimina `finding_revisions` si contiene filas.
- Con filas existentes, el downgrade falla con instrucción explícita de
  respaldar/exportar; nunca descarta historial.
- Cambiar de normalizador crea versión nueva; no reescribe revisiones.
- Una falla de OpenSearch deja la integración degradada y no fabrica evidencia.

## 20. Información pendiente antes de implementación

Se necesita aprobar o aportar:

1. límites de longitud y cardinalidad usando muestras Wazuh representativas;
2. política de retención mínima/máxima de revisiones por tenant;
3. regla exacta y versionada de score de completitud;
4. umbrales de conversión de severidad numérica a textual;
5. catálogo allowlisted inicial de `issue_codes`;
6. esquemas permitidos para localizadores de evidencia;
7. volúmenes, frecuencia de polling y objetivos de latencia;
8. tratamiento/redacción requerido para usuarios, IP, rutas y command lines;
9. estrategia de backfill para `alert_references` existentes sin procedencia
   completa;
10. ambiente Wazuh real autorizado para la prueba de aceptación operativa.

Durante la implementación se resolvieron límites, calidad, severidad,
localizadores, backfill conservador y validación Wazuh real. Retención y
frecuencia/polling permanecen como puertas separadas: no bloquean la ingestión
manual acotada ya validada, pero sí el borrado o scheduler periódico.

## 21. Criterios de aprobación

Para autorizar implementación se debe confirmar:

1. `CanonicalFindingV1` es el único objeto persistible inicial.
2. `alert_references` se conserva como proyección compatible.
3. El historial se modela como revisiones append-only.
4. El tiempo de origen ausente no se inventa.
5. Identidad, fingerprint e idempotencia siguen las secciones 7 y 10.
6. Calidad usa `VALID`, `PARTIAL`, `REJECTED` más score e incidencias.
7. PostgreSQL no almacena telemetría raw.
8. Las referencias no ejecutan resolución de entidades.
9. Se aprueba `security.finding.normalized` v1.
10. No se agregan API/UI ni conectores reales nuevos en esta fase.
11. Los diez pendientes de la sección 20 se resolverán antes de la parte física
    que dependa de ellos.

La aprobación quedó registrada el 2026-07-28. Los parámetros físicos y
excepciones resultantes se registran en ADR 0010.

## 22. Resultado de implementación

Implementado el 2026-07-28:

- `CanonicalFinding` y value objects como dataclasses inmutables;
- semántica temporal sin timestamp de origen inventado;
- fingerprint SHA-256 canónico y calidad Wazuh v1;
- migración `0009_finding_provenance`;
- revisiones append-only con RLS y proyección compatible;
- repositorio e ingestión transaccional;
- evento `security.finding.normalized` mediante outbox/inbox;
- topología RabbitMQ y handler durable para el evento;
- comando acotado `python -m cyrvanta.sync_wazuh_findings`;
- ADR 0010 con parámetros físicos y decisiones de compatibilidad.

Validación observada:

- Ruff y mypy: correctos;
- pytest: 50 pruebas aprobadas;
- migración `0009_finding_provenance` aplicada en PostgreSQL Compose;
- lote real OpenSearch/Wazuh: 10 recibidos, 10 revisiones y 10 eventos;
- replay del mismo lote: 10 duplicados y cero revisiones/eventos nuevos;
- worker: 10 inbox completados;
- RLS real: tenant propietario ve 10 revisiones y el segundo tenant ve 0;
- tabla de revisiones sin columna de payload/documento raw;
- API de salud y aplicación web: HTTP 200.

La retención configurable y la FK de `integration_id` permanecen pendientes de
sus contratos de gobierno/configuración. El polling automático no se activa:
el comando real queda listo para job/scheduler cuando se aprueben frecuencia,
cursor durable y política operativa.
