# Fase 19 — MITRE ATT&CK, riesgo determinista y explicabilidad

**Etapa estratégica:** 5

**Estado:** DRAFT — propuesta para revisión humana; no autoriza implementación

**Fecha:** 2026-07-28

**Implementación autorizada:** no

## 1. Objetivo

Definir un contrato neutral de proveedor para:

- importar y consultar un catálogo MITRE ATT&CK oficial, local y versionado;
- vincular evidencia tenant-owned con tácticas, técnicas y sub-técnicas;
- calcular riesgo mediante reglas deterministas, versionadas y reproducibles;
- explicar mappings y riesgo en español e inglés a partir de factores y
  evidencia verificables;
- permitir redacción opcional mediante `AIProvider` sin convertir la IA en
  autoridad de mapping, riesgo o respuesta.

La etapa debe preservar el funcionamiento actual, incluida la demo, y sustituir
gradualmente sus resultados provisionales sin reescribir historia.

## 2. Documentos rectores

Esta propuesta se rige por:

- `docs/foundation/01_PROJECT_VISION.md`;
- `docs/foundation/02_SYSTEM_ARCHITECTURE.md`;
- `docs/foundation/03_DEVELOPMENT_RULES.md`;
- `docs/foundation/04_TECHNOLOGY_STACK.md`;
- `docs/domain/BOUNDED_CONTEXTS.md`;
- `docs/domain/DOMAIN_MODEL.md`;
- `docs/specifications/PHASE_15_EVENT_DELIVERY_TRACEABILITY.md`;
- `docs/specifications/PHASE_16_CANONICAL_SECURITY_MODEL_PROVENANCE.md`;
- `docs/specifications/PHASE_17_CLAIM_LEDGER.md`;
- `docs/specifications/PHASE_18_DETERMINISTIC_MULTI_SOURCE_CORRELATION.md`;
- ADR 0010, ADR 0011 y ADR 0012.

Ante conflicto prevalecen seguridad, aislamiento multitenant y las reglas de
Foundation.

## 3. Fuente oficial candidata

MITRE publica ATT&CK como colecciones STIX 2.1 versionadas en
`mitre-attack/attack-stix-data`. A la fecha de esta propuesta, la versión
vigente es ATT&CK `19.1`.

Fuentes de referencia:

- <https://attack.mitre.org/resources/versions/>;
- <https://attack.mitre.org/resources/attack-data-and-tools/>;
- <https://github.com/mitre-attack/attack-stix-data>.

La implementación no seguirá el archivo mutable `latest`. Cada importación
debe usar un artefacto de release identificado por dominio, versión, URL de
procedencia y SHA-256 observado. El bundle no se descarga durante el build ni
se actualiza automáticamente al arrancar.

La primera entrega candidata importa únicamente el dominio
`enterprise-attack`. Mobile e ICS quedan fuera hasta disponer de casos de uso y
pruebas aprobadas.

## 4. Estado actual y brechas

El slice demostrativo actual:

- declara tres técnicas estáticas en `operations.application.service`;
- entrega siempre `T1110`, `T1078` y `T1098`, con independencia de la evidencia;
- calcula un riesgo efímero a partir de severidad y una confianza fija;
- mezcla análisis, MITRE, riesgo, Ollama y automatización en `OperationsService`;
- llama a Ollama directamente mediante HTTP en lugar de un `AIProvider`;
- no persiste catálogo, mappings, evaluaciones de riesgo ni explicaciones;
- no conserva versión de dataset, regla de mapping, factores ni fingerprint de
  inputs;
- modela una sola táctica por técnica, aunque ATT&CK puede relacionar una
  técnica con varias tácticas;
- no diferencia mapping propuesto, sustentado, validado, rechazado o
  supersedido;
- expone un listado no paginado de solo tres técnicas.

Los claims de Fase 17 sí permiten conservar inferencias y recomendaciones, y la
correlación de Fase 18 aporta miembros, factores, regla, versión y evidencia
reproducible. Esas capacidades deben reutilizarse.

## 5. Alcance

### 5.1 Incluido

- importador offline de colecciones Enterprise ATT&CK STIX 2.1;
- catálogo global versionado de tácticas, técnicas, sub-técnicas, mitigaciones
  y relaciones allowlisted;
- conservación de objetos revocados y deprecados necesarios para historia;
- mappings tenant-owned entre incidente, evidencia y objeto ATT&CK;
- reglas deterministas y versionadas de mapping;
- propuestas opcionales de IA validadas contra el catálogo local;
- evaluación de riesgo append-only y reproducible;
- explicación estructurada y presentación bilingüe;
- procedencia, auditoría, permisos, RLS, eventos, observabilidad y rollback;
- migración compatible del slice demo.

### 5.2 Fuera de alcance

- importar Groups, Software, Campaigns o identidad de adversarios;
- inferir atribución;
- usar ATT&CK como puntaje de severidad universal;
- resolución general de activos o cuentas;
- respuesta automática, aprobaciones o ejecución de playbooks;
- embeddings, vector database o búsqueda semántica;
- traducción automática del catálogo oficial completo;
- modificar o personalizar objetos oficiales por tenant;
- actualización programada del catálogo sin revisión;
- almacenar razonamiento privado o cadena de pensamiento de un modelo.

## 6. Bounded contexts

### 6.1 Threat Knowledge

Es propietario del catálogo global, releases importados, objetos ATT&CK y reglas
de mapping aprobadas. No importa persistencia de Incident, Correlation, Claims,
AI Analysis o Risk.

### 6.2 Incident Management

Continúa siendo propietario del incidente y su timeline. Threat Knowledge solo
recibe referencias autorizadas mediante puertos o DTO de aplicación.

### 6.3 Risk and Policy

Es propietario de definiciones de riesgo y evaluaciones append-only. Consume
snapshots acotados de incidente, correlación, findings y mappings sustentados.
No permite que Threat Knowledge ni AI Analysis escriban su persistencia.

### 6.4 AI Analysis

Puede proponer mappings o redactar una explicación. Sus outputs se consideran
datos no confiables, se validan mediante schemas estrictos y nunca cambian el
score determinista.

### 6.5 Claim Ledger

Conserva las afirmaciones epistemológicas. Un mapping propuesto por IA produce
una `INFERENCE`; un mapping derivado por una regla aprobada produce un
`DERIVED_FACT`. La evaluación humana no convierte una inferencia en hecho:
agrega una evaluación y, cuando corresponda, una afirmación humana separada.

## 7. Catálogo ATT&CK

### 7.1 Release inmutable

Cada release importado se identifica conceptualmente por:

- dominio ATT&CK;
- versión de colección;
- versión STIX;
- versión de especificación ATT&CK declarada por el bundle;
- instante de publicación cuando esté disponible;
- fuente oficial;
- SHA-256 del artefacto recibido;
- instante, herramienta y resultado de importación.

Una release importada no se modifica. Reimportar el mismo dominio, versión y
hash es idempotente. El mismo número de versión con distinto hash falla cerrado
y requiere revisión.

### 7.2 Objetos iniciales

El importador admite exclusivamente:

- `x-mitre-tactic`;
- `attack-pattern` para técnicas y sub-técnicas;
- `course-of-action` para mitigaciones;
- `relationship` cuando ambos extremos pertenecen al allowlist anterior;
- `marking-definition` necesario para procedencia y términos.

Los demás tipos se ignoran con conteos observables, no se persisten como JSON
genérico.

### 7.3 Identidad e historia

- El STIX ID identifica el objeto dentro del dataset.
- El external ID ATT&CK (`TAxxxx`, `Txxxx`, `Txxxx.xxx`, `Mxxxx`) se conserva y
  valida por tipo.
- La versión del objeto y la versión del dataset se conservan por separado.
- `revoked` y `deprecated` no eliminan historia ni mappings previos.
- Una consulta nueva no propone objetos revocados o deprecados por defecto.
- Un mapping histórico siempre referencia la release y versión utilizadas al
  producirlo.

### 7.4 Idioma

El texto oficial del catálogo se conserva en su idioma original y con su
procedencia. La interfaz, filtros, estados, factores y explicaciones de
Cyrvanta son bilingües mediante claves i18n.

No se presenta una traducción automática como texto oficial MITRE. Una
explicación bilingüe puede resumir el significado aplicado al incidente, pero
debe identificarse como explicación Cyrvanta.

### 7.5 Relaciones y multiplicidad

Tácticas, técnicas, sub-técnicas y mitigaciones se relacionan mediante objetos
versionados; no se aplana una técnica a un único campo `tactic`. Por ejemplo,
la versión vigente de `T1078` pertenece a varias tácticas. El orden de
presentación es una proyección y no cambia la semántica importada.

### 7.6 Atribución y términos

La distribución debe conservar `marking-definition`, atribución, avisos y
referencias requeridos por los términos de uso incluidos con el artefacto
oficial. Cyrvanta no elimina marcas, no presenta el catálogo como propio y no
modifica texto oficial en sitio. La revisión de licencia del producto continúa
como puerta de gobernanza independiente.

### 7.7 Importación on-premise

La primera implementación recomendada usa un comando administrativo offline
contra un archivo local previamente descargado. Debe:

1. limitar tamaño antes de parsear;
2. exigir STIX 2.1 y dominio allowlisted;
3. calcular SHA-256;
4. validar estructura y external IDs;
5. importar en una transacción;
6. registrar métricas y auditoría administrativa sin copiar el bundle al log;
7. activar una release solo mediante una operación explícita posterior.

Descarga HTTP, TAXII y scheduler quedan para un adaptador posterior. Si se
habilitan, usarán destinos allowlisted, TLS verificado, timeouts y límites para
evitar SSRF y agotamiento de recursos.

## 8. Mapping de evidencia a ATT&CK

### 8.1 Semántica

Un mapping afirma que evidencia concreta sustenta la aplicabilidad de un objeto
ATT&CK a un incidente. No afirma atribución, intención, compromiso confirmado
ni riesgo por sí mismo.

Todo mapping debe conservar:

- tenant e incidente;
- release, STIX ID y external ID;
- origen `RULE`, `AI` o `HUMAN`;
- regla/versión o proveedor/modelo/prompt cuando corresponda;
- evidencias tenant-owned;
- rationale estructurado no localizado;
- estado;
- fingerprint de inputs;
- timestamps y actor/proceso.

### 8.2 Estados candidatos

- `PROPOSED`: candidato aún no aceptado como señal de riesgo;
- `SUPPORTED`: generado por una regla determinista aprobada y con evidencia
  completa;
- `VALIDATED`: confirmado explícitamente por una persona autorizada;
- `REJECTED`: descartado con razón;
- `SUPERSEDED`: reemplazado sin borrar historia.

Solo `SUPPORTED` y `VALIDATED` participan en riesgo v1.

### 8.3 Evidencia permitida

Inicialmente se permiten referencias a:

- `FINDING_REVISION`;
- `CORRELATION_MATCH`;
- `CLAIM`;
- `INCIDENT_TIMELINE_ENTRY` cuando la entrada proviene de un hecho estructurado.

La evidencia debe pertenecer al mismo tenant e incidente. Texto libre aislado,
salida de IA sin evidencia, audit logs y telemetría raw no son evidencia
suficiente.

### 8.4 Reglas deterministas

Las reglas son inmutables y versionadas. Declaran:

- inputs requeridos;
- combinación exacta de regla/versión de correlación o selectores canónicos;
- objetos ATT&CK de una release;
- evidencia mínima;
- rationale code;
- vigencia y estado.

La regla inicial candidata para la demo mapea el match
`credential-attack` versión `2` a:

- `T1110` cuando existe señal de fallos de autenticación;
- `T1078` cuando existe éxito posterior sustentado;
- `T1098` únicamente cuando existe la señal exacta de cambio de privilegios o
  manipulación de cuenta definida por la regla.

Esta correspondencia es una propuesta para aprobación, no una taxonomía
universal ni una equivalencia de códigos Wazuh.

### 8.5 Propuestas de IA

El modelo recibe:

- evidencia minimizada y delimitada;
- candidatos ATT&CK recuperados del catálogo local;
- external IDs y versiones;
- instrucciones explícitas contra prompt injection.

El output usa un schema estricto y solo puede referenciar candidatos
proporcionados. IDs desconocidos, revocados, deprecados o sin evidencia se
rechazan. Toda propuesta queda `PROPOSED` y no afecta el riesgo hasta validación
humana.

## 9. Riesgo determinista v1

### 9.1 Semántica

El score representa prioridad técnica relativa para investigación dentro de
Cyrvanta. No representa probabilidad matemática, pérdida económica, certeza,
severidad CVSS, confianza del modelo ni autorización de respuesta.

El resultado conserva score `0–100`, banda, definición/versión, factores,
contribuciones, evidencias, inputs ausentes y fingerprint.

### 9.2 Factores candidatos

Paquete recomendado:

| Factor | Contribución máxima | Regla v1 |
|---|---:|---|
| Severidad de incidente | 60 | `informational=5`, `low=15`, `medium=30`, `high=45`, `critical=60` |
| Corroboración de evidencia | 15 | 1 revisión=`0`; 2=`5`; 3=`10`; 4 o más=`15` |
| Diversidad de fuente | 10 | 1 sistema=`0`; 2 o más=`10` |
| Mapping ATT&CK sustentado | 10 | 0=`0`; 1=`5`; 2 o más=`10` |
| Calidad de normalización | 5 | todas `VALID`=`5`; cualquier `PARTIAL`=`0` |

Reglas adicionales:

- se cuentan revisiones distintas, no redeliveries ni filas duplicadas;
- se cuentan sistemas fuente canónicos, no nombres de adaptadores;
- solo mappings `SUPPORTED` o `VALIDATED` no revocados participan;
- un dato ausente contribuye `0` y queda visible; no se inventa un valor;
- el score es la suma exacta, limitada a `100`;
- los mismos inputs, definición y versiones producen el mismo resultado.

### 9.3 Bandas candidatas

- `0–19`: minimal;
- `20–39`: low;
- `40–59`: medium;
- `60–79`: high;
- `80–100`: critical.

Las claves son códigos no localizados. La UI muestra traducciones españolas e
inglesas y siempre enseña el valor numérico, los factores y los datos ausentes.

### 9.4 Relación con otros scores

- `correlation.score` continúa midiendo factores de agrupación.
- `finding.confidence` conserva lo declarado por el origen.
- una confianza de IA es metadata de una inferencia.
- `risk.score` solo usa los factores aprobados en esta sección.

Ningún score se convierte implícitamente en otro. La versión v1 no usa
confianza de IA ni correlation score como factor para evitar circularidad y
doble conteo.

### 9.5 Recalculado e historia

La evaluación es append-only. Un cambio de incidente, evidencia, mapping,
definición o release crea otra evaluación y supersede la anterior de manera
explícita. Un redelivery con el mismo fingerprint es idempotente.

La revisión humana de severidad puede disparar una nueva evaluación; nunca se
reescribe el resultado anterior.

## 10. Explicabilidad

### 10.1 Explicación estructurada autoritativa

La fuente de verdad es una proyección determinista formada por:

- definición y versión de riesgo;
- score, banda y factores;
- mappings con estado, regla/actor y release;
- referencias a evidencia;
- datos ausentes y limitaciones;
- procedencia simulada o real.

El texto base se genera desde códigos y plantillas i18n. No necesita Ollama.

### 10.2 Redacción opcional mediante IA

Una redacción IA:

- usa el puerto `AIProvider`, nunca HTTP directo desde dominio o React;
- tiene prompt, input schema y output schema versionados;
- genera español e inglés en campos separados;
- recibe únicamente la explicación estructurada y evidencia minimizada;
- no puede agregar técnicas, factores, scores, acciones ni hechos;
- se valida comparando sus referencias con los inputs;
- conserva proveedor, modelo, parámetros, prompt, hashes, latencia y estado;
- cae a la explicación determinista ante timeout, error o schema inválido.

La salida se registra como presentación de claims existentes o como
`INFERENCE`, nunca como `FACT`.

### 10.3 Contradicciones y límites

La explicación debe mostrar:

- mappings rechazados o supersedidos cuando el usuario tenga permiso;
- factores sin evidencia;
- diferencia entre simulado y real;
- diferencia entre `SUPPORTED` por regla y `VALIDATED` por humano;
- que ATT&CK clasifica comportamiento y no demuestra atribución.

## 11. Flujo recomendado

### 11.1 Enriquecimiento determinista

1. El worker consume un match nuevo o ampliado de correlación.
2. Abre una sesión tenant-scoped.
3. Obtiene un snapshot acotado mediante puertos.
4. Evalúa reglas de mapping contra una release activa explícita.
5. Persiste mappings idempotentes y claims asociados.
6. Calcula y persiste riesgo v1.
7. Genera explicación estructurada bilingüe.
8. Registra outbox y confirma una única transacción PostgreSQL.

Un fallo revierte todos los efectos de ese enriquecimiento. La ingesta y la
correlación ya confirmadas no se revierten.

### 11.2 Redacción IA

La redacción IA es un trabajo asíncrono posterior. La llamada externa ocurre
fuera de una transacción larga. Al volver:

1. se reabre contexto tenant;
2. se comprueba que el fingerprint de inputs siga vigente;
3. se valida el schema y las referencias;
4. se persiste presentación o error explícito;
5. se publica el resultado mediante outbox.

Si los inputs cambiaron, el output se descarta como stale y puede solicitarse
otro análisis.

## 12. Persistencia lógica candidata

No se aprueban nombres físicos con este DRAFT. Conceptualmente se requieren:

### 12.1 Datos globales

- release ATT&CK inmutable;
- versión de objeto ATT&CK por release;
- relaciones allowlisted;
- definición versionada de regla de mapping;
- definición versionada de riesgo.

Los datos globales no llevan `tenant_id`, pero solo el proceso administrativo
puede mutarlos. El rol de aplicación normal recibe lectura.

### 12.2 Datos tenant-owned

- mapping de incidente a ATT&CK;
- referencias de evidencia del mapping;
- evaluación de riesgo append-only;
- factores de evaluación;
- explicación estructurada;
- presentación IA opcional y procedencia.

Todos incluyen `tenant_id`, RLS habilitada y forzada, FK compuestas que
demuestran mismo tenant, UUID, timestamps UTC e índices derivados de consultas
aprobadas.

No se almacena STIX raw en JSONB como sustituto del modelo relacional. Metadata
acotada y extensiones allowlisted sí pueden usar JSONB.

## 13. API candidata

La aprobación debe elegir entre un recurso de enriquecimiento unificado o
recursos separados. Se recomienda:

- catálogo paginado y filtrable por external ID, nombre, tipo, táctica, release
  y estado;
- detalle de objeto ATT&CK por UUID interno;
- mappings paginados por incidente;
- evaluación de riesgo vigente e historial paginado;
- explicación vigente con alternativa textual accesible;
- comandos separados para validar/rechazar mappings con versión esperada.

El endpoint demo existente `/api/v1/mitre/techniques` se conserva durante una
ventana de compatibilidad como proyección read-only y se depreca explícitamente.
No se cambia su shape silenciosamente.

Toda lista usa paginación y filtros allowlisted. El tenant procede del contexto
autenticado. IDs ajenos responden `404`. Errores siguen RFC 7807.

## 14. Eventos candidatos

- `security.threat-mapping.assessed` versión 1;
- `security.risk.assessed` versión 1;
- `security.explanation.generated` versión 1;
- `security.explanation.failed` versión 1.

El envelope de Fase 15 conserva tenant, event, correlation y causation IDs. Los
payloads contienen IDs, versiones, estado y hashes; nunca descripciones ATT&CK
completas, evidencia raw, prompts, PII o secretos.

La implementación puede consolidar eventos si demuestra menor acoplamiento sin
perder causalidad. Los nombres y payloads no quedan aprobados hasta aprobar
esta especificación.

## 15. Permisos candidatos

- `mitre.catalog.read`;
- `mitre.mapping.read`;
- `mitre.mapping.validate`;
- `risk.read`;
- `risk.recalculate`;
- `explanation.read`;
- `explanation.generate`;
- `threat-knowledge.manage` para importación/activación administrativa.

Paquete recomendado:

- `tenant-admin`: lectura, validación de mapping, recálculo y generación;
- usuario demo `tenant-admin`: puede ejercitar todo el slice tenant-owned;
- importación y activación de catálogo: solo operación de plataforma/CLI, no
  tenant-admin;
- ninguna capacidad de esta etapa concede respuesta o automatización.

Los roles analistas siguen pendientes de aprobación de RBAC y no reciben
permisos nuevos por inferencia.

## 16. Seguridad y multitenancy

- El catálogo es global read-only; mappings, riesgo y explicaciones son
  tenant-owned.
- Toda evidencia referenciada se verifica bajo el mismo tenant.
- RLS se fuerza incluso para el rol normal de aplicación.
- Repositorios no ofrecen consultas tenant-owned sin scope.
- Jobs y eventos conservan tenant en envelope y sesión.
- La importación usa límites de tamaño, profundidad, objetos y relaciones.
- XML no participa; no existe riesgo XXE en STIX JSON.
- URLs no confiables dentro de STIX no se recuperan ni se convierten en links
  activos sin allowlist.
- Descripciones STIX y evidencia se escapan en UI.
- Prompts tratan evidencia como hostil y prohíben seguir instrucciones.
- Logs omiten bundle, evidencia, prompts y outputs completos.
- El catálogo no se actualiza durante una investigación sin activación
  explícita y auditable.

## 17. Auditoría y observabilidad

Se auditan:

- importación, activación y retiro de una release;
- validación, rechazo y supersesión humana de mapping;
- solicitud manual de recálculo;
- solicitud y resultado de redacción IA;
- lectura/exportación privilegiada según política.

Procesamiento automático de alto volumen usa eventos, outbox y métricas sin
duplicar audit rows por cada lectura interna.

Métricas mínimas:

- releases y objetos importados/ignorados/rechazados;
- duración y fallos de importación;
- mappings por origen/estado/external ID;
- evaluaciones idempotentes, supersedidas y fallidas;
- distribución de bandas y factores ausentes;
- latencia, schema failures, stale outputs y fallback de IA;
- retry y DLQ por evento.

No se incluyen tenant IDs en métricas de cardinalidad no acotada.

## 18. Límites candidatos

Antes de implementar deben aprobarse límites físicos. Paquete recomendado:

- bundle STIX: máximo 250 MiB;
- objetos por importación: 100 000;
- relaciones allowlisted: 500 000;
- mappings por incidente: 128 activos y 512 históricos;
- evidencias por mapping: 32;
- factores de riesgo v1: exactamente 5;
- mappings procesados por evaluación: 128;
- explicación estructurada por locale: 4 000 caracteres;
- contexto IA serializado: 32 KiB;
- output IA por locale: 2 000 caracteres;
- timeout IA: configuración existente, máximo operativo aprobado;
- un job concurrente por tenant/incidente/fingerprint.

Exceder un límite falla cerrado y produce código observable; nunca trunca de
forma que cambie silenciosamente el riesgo.

## 19. Pruebas de aceptación

### 19.1 Catálogo

- fixture STIX 2.1 mínimo válido;
- fixture oficial recortado con procedencia y hash documentados;
- importación idempotente;
- mismo número de release con hash distinto rechazado;
- external IDs, sub-técnicas, revocados y deprecados;
- objetos/relaciones desconocidos ignorados con métricas;
- rollback transaccional ante bundle inválido.

### 19.2 Mapping

- regla exacta produce los mappings esperados;
- evidencia insuficiente no produce `SUPPORTED`;
- mapping IA queda `PROPOSED`;
- ID inexistente, revocado o deprecado se rechaza;
- validación/rechazo exige permiso y versión;
- redelivery no duplica mapping ni claim.

### 19.3 Riesgo

- tabla completa de severidades y bandas;
- mismos inputs/versiones producen score y fingerprint idénticos;
- orden de inputs no cambia resultado;
- faltantes contribuyen cero y quedan explicados;
- IA, confidence y correlation score no alteran v1;
- nueva evidencia crea evaluación append-only y supersede la previa;
- límites fallan cerrado.

### 19.4 Aislamiento y seguridad

- Tenant A accede a sus mappings/riesgo/explicación;
- Tenant A no accede, cuenta ni infiere recursos de Tenant B;
- FK tenant-scoped bloquean referencias cruzadas;
- RLS real con rol de aplicación;
- eventos y worker preservan tenant;
- prompt injection no modifica schema ni referencias;
- output con técnica inventada se rechaza;
- importador resiste tamaño, profundidad y campos inesperados.

### 19.5 Frontend y accesibilidad

- español e inglés;
- no depende solo de color;
- alternativa textual al mapa/matriz;
- paginación y búsqueda acotada;
- teclado, foco y estados loading/empty/error;
- simulación y procedencia visibles;
- snapshot y E2E del escenario canónico v2.

## 20. Migración y compatibilidad

La implementación candidata:

1. agrega catálogo y datos tenant-owned mediante migraciones nuevas;
2. importa el bundle aprobado fuera de la migración de schema;
3. incorpora reglas demo versionadas;
4. mantiene el catálogo estático actual como fallback temporal;
5. habilita el nuevo pipeline detrás de configuración segura;
6. compara resultados demo sin presentar equivalencia automática como real;
7. depreca el resultado efímero anterior después de validar persistencia y UI;
8. nunca fabrica mappings históricos para análisis previos.

La migración no descarga Internet ni llama Ollama. Datos demo existentes
permanecen marcados como simulados.

## 21. Rollback

- Desactivar consumidores de enriquecimiento no detiene ingesta, correlación ni
  acceso a incidentes.
- La release activa puede volver explícitamente a una versión importada previa.
- Las definiciones nuevas se desactivan; no se editan en sitio.
- La UI vuelve a la proyección demo únicamente si queda rotulada como legado.
- El downgrade de schema se bloquea si existen mappings, evaluaciones o
  explicaciones, hasta exportación y remoción administrativa explícita.
- Nunca se borran claims, incidentes, correlaciones, audit o historia ATT&CK de
  forma automática.

## 22. Dependencia downstream con n8n

Los outputs estructurados de esta etapa serán inputs futuros del workflow
`incident-report-email`. La Etapa 5 no envía correos ni conoce n8n. Expone
snapshots autorizados mediante un puerto que la futura Etapa 7 podrá consumir.

Los requisitos recibidos para workflows como código están versionados en
`docs/requirements/N8N_WORKFLOWS_AS_CODE_REQUIREMENTS.md`. No cambian los pesos,
mappings ni criterios de esta etapa y no autorizan adelantar aprobaciones o
ejecuciones.

## 23. Decisiones materiales pendientes

La implementación queda bloqueada hasta aprobar o enmendar:

1. Enterprise ATT&CK v19.1 como baseline inicial.
2. Importación offline por CLI y activación explícita.
3. Tipos STIX allowlisted y exclusión de Groups/Software/Campaigns.
4. Conservación del texto oficial en inglés sin traducción presentada como
   oficial.
5. Ownership global del catálogo y tenant-owned de mappings/riesgo/explicación.
6. Estados `PROPOSED`, `SUPPORTED`, `VALIDATED`, `REJECTED`, `SUPERSEDED`.
7. Evidencias permitidas y relación con Claim Ledger.
8. Mappings exactos de `credential-attack` v2.
9. Cinco factores, pesos y bandas del riesgo v1.
10. Exclusión de IA, confidence y correlation score del riesgo v1.
11. Modelo append-only y política de supersesión.
12. Flujo transaccional determinista y trabajo IA posterior.
13. Estrategia de compatibilidad del endpoint y resultado demo.
14. API, eventos y permisos candidatos.
15. Límites físicos de sección 18.
16. Política de actualización, rollback y conservación histórica.
17. Uso permitido de redacción IA y fallback determinista.
18. Criterios de aceptación y pruebas reales de RLS.

## 24. Paquete recomendado para aprobación

Se recomienda aprobar las alternativas descritas en las secciones 3 a 21 sin
variaciones y registrar la decisión en un ADR nuevo.

La aprobación autorizaría diseñar el catálogo físico, migraciones, contratos,
puertos, schemas, endpoints, eventos, permisos y UI exactos. Mientras el
documento permanezca `DRAFT`, no se implementará ninguna de esas piezas.

## 25. Criterios de salida de Etapa 5

La etapa estará completa cuando:

1. una release oficial versionada se importe offline e idempotentemente;
2. el escenario canónico v2 produzca mappings sustentados y rastreables;
3. el mismo snapshot produzca el mismo riesgo y explicación;
4. cada factor y mapping apunte a evidencia autorizada;
5. la UI sea bilingüe, paginada y accesible;
6. Ollama pueda redactar mediante `AIProvider` y falle hacia templates seguros;
7. IDs inventados y prompt injection fallen cerrado;
8. pruebas cross-tenant y RLS reales pasen;
9. los servicios existentes y la demo no sufran regresiones;
10. documentación, ADR, migración, rollback y comandos operativos estén
    actualizados.
