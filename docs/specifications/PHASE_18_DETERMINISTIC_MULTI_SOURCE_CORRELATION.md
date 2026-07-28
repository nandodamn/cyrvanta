# Fase 18 — Correlación determinista multi-fuente

**Estado:** IMPLEMENTADO Y VALIDADO
el 2026-07-28.

**Fecha:** 2026-07-28
**Implementación autorizada:** sí; completada el 2026-07-28.

## 1. Objetivo

Definir el contrato de una primera correlación general, reproducible y neutral
al proveedor que agrupe findings canónicos relacionados y proponga la creación
o ampliación de incidentes sin utilizar IA como autoridad.

La correlación deberá conservar:

- tenant y procedencia de cada input;
- revisión exacta de cada finding;
- regla, versión y configuración efectiva;
- candidatos, miembros, factores y resultado;
- score de correlación separado de riesgo y confianza;
- idempotencia, explicación y evaluación humana;
- trazabilidad mediante outbox/inbox.

Este documento no autoriza todavía modelos físicos, migraciones, endpoints,
permisos, eventos ni cambios en workers.

## 2. Resultado funcional esperado

Con los mismos inputs ordenados, la misma regla y la misma versión, Cyrvanta
produce exactamente:

- la misma identidad de evaluación;
- los mismos miembros;
- los mismos factores;
- el mismo score;
- el mismo resultado de match/no-match;
- la misma explicación estructurada.

Wazuh y dos fixtures sintéticos semánticamente equivalentes deben poder
participar sin que el motor conozca sus formatos originales.

## 3. Estado de partida

La base reutilizable contiene:

- `CanonicalFindingV1` y revisiones append-only con fingerprints;
- referencias de entidad todavía no resueltas;
- evento `security.finding.normalized`;
- outbox/inbox at-least-once y worker durable;
- alertas, incidentes, timeline y control optimista;
- un `correlation_run` exclusivamente sintético y acoplado al demo;
- ledger de claims, evidencia y evaluaciones append-only;
- adaptador Wazuh y adaptador in-memory solo para pruebas.

Brechas:

1. El evento normalizado no activa correlación real.
2. No existe selección tenant-scoped de candidatos.
3. No hay definición versionada de reglas ni hash de configuración.
4. No se persisten miembros por revisión, factores o score.
5. La correlación demo crea directamente sus datos dentro de Incident
   Management.
6. No hay evaluación humana reutilizable ni métricas de precisión.
7. Score de correlación, riesgo, severidad y confianza podrían confundirse.
8. No hay estrategia aprobada para ampliar un incidente o iniciar otro.
9. Wazuh conserva su primer `rule.groups` como `category`; ese valor no es una
   taxonomía semántica neutral entre proveedores.
10. Las referencias Wazuh de `ASSET` y `ACCOUNT` aún no incluyen
    `normalized_value`; no pueden usarse para coincidencia exacta hasta aprobar
    perfiles de normalización.
11. El escenario demo actual crea `alert_references` y `correlation_runs`
    directamente, sin generar revisiones canónicas aptas para este motor.

## 4. Alcance

### 4.1 Incluido

- reglas deterministas, inmutables y versionadas;
- selección acotada de candidatos;
- matching exacto sobre referencias normalizadas;
- ventanas temporales explícitas;
- evaluación y explicación mediante factores;
- miembros anclados a revisiones de findings;
- creación o ampliación idempotente de incidentes activos;
- `DERIVED_FACT` que afirma únicamente el resultado de la regla;
- evaluación humana mediante el ledger de claims;
- eventos internos, permisos candidatos, observabilidad y rollback;
- UI bilingüe de explicación después de persistencia y API.

### 4.2 Fuera de alcance

- resolución difusa o probabilística de entidades;
- gráficos de identidad global o cross-tenant;
- embeddings, similitud vectorial o LLM;
- cálculo de riesgo definitivo;
- importación o validación MITRE ATT&CK;
- fusión automática de incidentes;
- reapertura, resolución o cierre automático;
- nuevas integraciones SIEM;
- polling periódico Wazuh;
- retención o borrado automático;
- memoria operacional o reentrenamiento;
- decisión o ejecución de playbooks.

## 5. Límites de bounded context

### Correlation

Es propietario conceptual de:

- definiciones y versiones de reglas;
- evaluaciones;
- matches;
- miembros;
- factores y explicación.

Correlation no modifica tablas de Incident Management directamente. Invoca un
puerto de aplicación para solicitar:

- crear un incidente nuevo;
- agregar evidencia a un incidente activo ya asociado;
- añadir una entrada de timeline.

### Incident Management

Continúa siendo propietario del incidente, su estado, versión, relaciones con
alertas y timeline. Valida concurrencia y decide si el incidente todavía admite
nueva evidencia.

### Security Integrations / Intake

Entrega referencias canónicas y revisiones. No decide correlaciones.

### Claim Ledger

Registra el resultado determinista como `DERIVED_FACT` y conserva su evaluación
humana. Validar ese claim no cambia su tipo ni convierte la interpretación de
seguridad en un hecho observado.

## 6. Semántica de correlación

Una correlación afirma:

> La regla R, versión V, evaluó el conjunto de revisiones I y satisfizo los
> factores F con score S.

No afirma por sí sola:

- que ocurrió un ataque;
- que una identidad humana realizó una acción;
- que el incidente tiene un riesgo concreto;
- que una técnica MITRE aplica;
- que una respuesta está autorizada.

`MATCHED` significa que la regla determinista alcanzó su umbral. No significa
“confirmado por un analista”.

## 7. Inputs autorizados

El motor inicial consume exclusivamente revisiones persistidas de
`CanonicalFindingV1` con normalización `VALID` o `PARTIAL`.

Cada input conserva:

- tenant;
- finding ID y revision ID;
- integración y sistema fuente;
- tiempo efectivo y basis temporal;
- severidad canónica;
- categoría y regla externa cuando existan;
- referencias de entidad normalizadas;
- fingerprint y versiones de normalización.

No se usa:

- payload raw;
- texto libre como clave primaria de matching;
- `display_value`;
- tenant declarado dentro de telemetría;
- campos desconocidos del proveedor.

Un input `PARTIAL` puede participar únicamente si la regla declara qué
incidencias acepta. Nunca se convierte silenciosamente en `VALID`.

## 8. Selección de candidatos

La selección ocurre dentro de un único tenant y antes de evaluar factores.

Restricciones propuestas:

- ventana retrospectiva acotada por versión de regla;
- número máximo de candidatos por evaluación;
- tipos de fuente, categorías y severidades allowlisted;
- orden estable por `effective_at`, finding ID y revision ID;
- solo la revisión vigente al momento del evento, salvo replay histórico
  explícito;
- exclusión de revisiones rechazadas;
- timeout y código de truncamiento visibles.

Si se alcanza el límite, la evaluación falla cerrada con resultado
`CANDIDATE_LIMIT_EXCEEDED`; no evalúa un subconjunto como si fuera completo.

No existe una consulta cross-tenant para seleccionar candidatos.

## 9. Matching de entidades

La primera versión admite coincidencia exacta y determinista:

- `ASSET`: `namespace + normalized_value`;
- `ACCOUNT`: `namespace + normalized_value`;
- `IP_ADDRESS`: dirección normalizada y rol fuente/destino cuando aplique;
- `DOMAIN`, `URL` y `HASH`: valor normalizado;
- `PROCESS` y `FILE`: solo cuando la regla declara atributos exactos
  suficientes.

Reglas:

1. Un valor sin namespace requerido no coincide por conveniencia.
2. Si el tipo requiere normalización y `normalized_value` no está disponible,
   esa referencia no coincide.
3. `display_value` nunca participa.
4. No se aplica fuzzy matching.
5. Dos referencias iguales en tenants distintos nunca coinciden.
6. Una equivalencia futura se agrega como evidencia versionada y reversible;
   no reescribe inputs históricos.

## 10. Tiempo y ventanas

Las ventanas usan `effective_at` de cada revisión.

- basis `SOURCE`: fuerza temporal normal.
- basis `DERIVED`: participa si la regla permite el código de derivación.
- basis `INGESTED`: no satisface factores que requieran secuencia temporal
  estricta, salvo declaración explícita.

Cada regla define:

- duración máxima de ventana;
- tolerancia de skew;
- si el orden de señales importa;
- cantidad mínima y máxima de miembros;
- estrategia determinista para anclar la ventana.

Se propone anclar la identidad de agrupación al primer `effective_at` ordenado
y a un bucket versionado por regla. La semántica exacta del bucket debe
aprobarse antes del diseño físico.

## 11. Reglas versionadas

Contrato lógico candidato `CorrelationRuleVersionV1`:

| Campo lógico | Regla |
|---|---|
| `rule_code` | Código estable, no localizado. |
| `version` | Inmutable; una corrección crea otra versión. |
| `status` | `DRAFT`, `ACTIVE` o `RETIRED`. |
| `input_schema_version` | Versión canónica aceptada. |
| `candidate_policy` | Fuentes, categorías, límites y ventana. |
| `factor_definitions` | Factores tipados y pesos. |
| `threshold` | Umbral de match. |
| `grouping_policy` | Claves exactas y bucket temporal. |
| `incident_policy` | Creación/ampliación permitida. |
| `partial_input_policy` | Incidencias admitidas. |
| `definition_sha256` | Hash de JSON canónico de la regla. |
| `activated_at` | UTC; nulo mientras está en draft. |

La primera implementación usaría reglas administradas y versionadas con el
despliegue. No se habilita un editor libre ni CRUD de reglas hasta especificar
autorización, firma, pruebas de regresión y activación.

Solo una versión `ACTIVE` de un `rule_code` participa en evaluación nueva.
Retirar una versión no altera matches históricos.

## 12. Factores y score

`CorrelationFactorResultV1` candidato:

- código y versión del factor;
- resultado booleano o valor numérico acotado;
- peso aplicado;
- contribución calculada;
- revision IDs que lo sustentan;
- código de explicación no localizado.

El score:

- usa escala entera 0–100;
- se calcula únicamente con factores versionados;
- es reproducible;
- no es una probabilidad;
- no es confianza de IA;
- no es severidad;
- no es riesgo.

Un match requiere factores obligatorios y umbral. Los pesos, umbrales y reglas
iniciales exactos permanecen pendientes de fixtures representativos y
aprobación; no se fijan en este DRAFT.

## 13. Evaluación y match

Contrato lógico candidato `CorrelationEvaluationV1`:

- identidad UUID;
- tenant;
- trigger event/correlation/causation IDs;
- regla, versión y hash;
- input fingerprint;
- ventana evaluada;
- cantidad de candidatos;
- resultado técnico;
- score y threshold;
- códigos de limitación/error;
- timestamps y versión de schema.

Resultados candidatos:

- `MATCHED`;
- `NO_MATCH`;
- `CANDIDATE_LIMIT_EXCEEDED`;
- `INPUT_REJECTED`;
- `RULE_UNAVAILABLE`;
- `FAILED_TRANSIENT`.

Solo `MATCHED` crea un registro durable de negocio y puede afectar un incidente.
Los no-match exitosos se conservan como métricas acotadas, no como filas
ilimitadas por finding. Los fallos técnicos permanecen en inbox/retry/DLQ y
observabilidad.

Contrato lógico candidato `CorrelationMatchV1`:

- identidad estable del match;
- evaluación y regla exactas;
- grouping key hash;
- score;
- explicación estructurada;
- incidente asociado;
- `is_simulated`;
- timestamps y schema.

## 14. Miembros

Cada miembro referencia una revisión exacta, no solamente la proyección mutable
de una alerta.

Roles candidatos:

- `TRIGGER`;
- `SUPPORTING`;
- `CONTEXT`.

Un miembro contiene:

- finding ID y revision ID;
- rol;
- orden estable;
- factores que sustenta;
- instante efectivo;
- integración y fuente para procedencia;
- marca simulada.

Los miembros son append-only. Una nueva revisión no reemplaza la revisión que
participó en un match histórico.

Una revisión puede participar en más de un match cuando reglas distintas
explican fenómenos diferentes. La UI debe mostrarlo; no se fuerza una falsa
exclusividad global.

## 15. Idempotencia

El input fingerprint se calcula sobre:

- tenant;
- rule code, version y definition hash;
- grouping key hash;
- revision IDs ordenados;
- effective times normalizados;
- versión del algoritmo de fingerprint.

La identidad durable candidata evita duplicar:

```text
(tenant, rule_code, rule_version, definition_sha256, input_fingerprint)
```

Redelivery del mismo evento no crea otro match, miembro, incidente, claim ni
evento. Concurrencia entre dos triggers equivalentes debe resolverse mediante
constraint/transacción, no mediante un lock solo en memoria.

## 16. Creación y ampliación de incidentes

Propuesta:

1. Un match nuevo solicita a Incident Management crear un incidente `new`.
2. Otro match con la misma grouping key y regla puede ampliar ese incidente
   únicamente si sigue activo y la política de regla lo permite.
3. Agregar miembros usa control optimista e idempotencia.
4. Un incidente `resolved`, `closed` o fuera de la ventana de agrupación nunca
   se reabre automáticamente.
5. En ese caso, un match posterior crea un incidente nuevo; relacionarlos o
   marcarlos duplicados queda para un contrato posterior.
6. Correlation nunca cambia estado, asignación, cierre, severidad revisada por
   humano ni decisiones de respuesta.

Se debe decidir antes de implementar qué estados se consideran “activos” y si
`contained` admite nuevos miembros automáticos.

La severidad y prioridad iniciales del incidente requieren una regla
determinista separada y versionada. Mientras no se apruebe, el primer slice no
debe derivarlas arbitrariamente del score de correlación.

## 17. Integración con Claim Ledger

Cada match materializa como máximo un `DERIVED_FACT`:

> La regla R versión V correlacionó N revisiones con score S.

El claim:

- referencia las revisiones miembro mediante los tipos de evidencia ya
  autorizados por Claim Ledger;
- identifica el match mediante origen, regla, versión, correlation ID y
  fingerprint, sin inventar un nuevo tipo de evidencia;
- es `SYSTEM` o `RULE`, nunca `AI`;
- no afirma ataque, atribución, riesgo ni técnica MITRE;
- conserva `is_simulated` si cualquier input o el trigger es simulado.

La evaluación humana reutiliza `ClaimAssessmentV1`:

- `VALIDATED`: el analista confirma que el resultado reproducible representa
  una agrupación útil;
- `REJECTED`: agrupación incorrecta;
- `INSUFFICIENT_EVIDENCE`: requiere más evidencia.

La evaluación no elimina miembros ni incidentes. Sus métricas pueden medir
precisión futura, pero no cambian pesos automáticamente.

## 18. Transacción

Para un `MATCHED`, la operación debe ser atómica o coordinada mediante un único
caso de uso dentro del monolito:

1. reclamar la identidad idempotente;
2. insertar match, miembros y factores;
3. pedir a Incident Management crear/ampliar;
4. registrar timeline;
5. crear el `DERIVED_FACT` y evidencia;
6. registrar eventos outbox.

Si no puede mantenerse una sola transacción sin violar bounded contexts, deberá
usarse una saga explícita y compensable aprobada antes de implementar. No se
acepta consistencia parcial silenciosa.

## 19. Eventos candidatos

Consumido:

```text
security.finding.normalized v1
```

Producidos candidatos:

```text
security.correlation.matched v1
security.correlation.member.added v1
```

Payload mínimo:

- match ID;
- incident ID;
- rule code/version;
- score;
- member count;
- schema version.

El envelope aporta tenant, event, correlation y causation IDs. No se incluyen
grouping keys, entidades, títulos, explicación, payload raw ni datos sensibles.

`member.added` solo se emite cuando un match posterior amplía un incidente.
Los nombres y payloads no son contratos hasta aprobar este documento.

## 20. API candidata

Lecturas tenant-scoped y paginadas:

- correlaciones de un incidente;
- detalle de match;
- miembros y factores autorizados;
- regla/versión aplicada y explicación;
- claim/evaluación asociada.

Un trigger manual o replay administrativo requeriría contrato separado con
idempotency key, ventana máxima, permiso, auditoría y límites. No se expone DSL
de reglas ni query OpenSearch.

La validación humana se realiza mediante la API aprobada de Claim Ledger; no se
duplica un endpoint de “verdad de correlación”.

## 21. Permisos candidatos

- `correlation.read`;
- `correlation.evaluate` para solicitar una evaluación manual acotada;
- `correlation.replay` reservado a operación administrativa futura.

La evaluación humana del resultado continúa usando `claim.assess`.

Propuesta inicial:

- `tenant-admin`: `correlation.read` y `correlation.evaluate`;
- worker: identidad técnica y funciones mínimas;
- ningún rol recibe `correlation.replay` hasta aprobar el runbook;
- no existe permiso cross-tenant implícito.

La matriz de analistas debe aprobarse antes de asignar permisos adicionales.

## 22. Persistencia lógica candidata

Se requieren conceptos persistentes para:

- versiones de regla;
- matches/evaluaciones exitosas;
- miembros;
- factores.

La implementación debe decidir si evoluciona `correlation_runs` o migra sus
filas sintéticas a nuevas relaciones. No se mantendrán dos fuentes de verdad.

Requisitos:

- tenant ID obligatorio y RLS forzada;
- FK/constraints tenant-aware;
- miembros y factores append-only;
- índices tenant-first derivados de consultas aprobadas;
- sin payload raw ni textos libres ilimitados;
- downgrade bloqueado cuando exista historia;
- datos demo existentes preservados y marcados como simulados.

Los nombres de tablas, columnas, tipos, índices y políticas definitivos se
presentarán después de aprobar este contrato lógico.

## 23. UI e i18n

Después de API y permisos:

- el incidente muestra regla y versión;
- score se etiqueta “score de correlación”, no “riesgo”;
- factores se presentan con códigos traducidos a español/inglés;
- miembros muestran fuente, tiempo, rol y marca simulada;
- un claim `PROPOSED`, `VALIDATED`, `REJECTED` o
  `INSUFFICIENT_EVIDENCE` conserva su etiqueta;
- truncamiento o evidencia parcial son visibles;
- color nunca es el único indicador.

No se implementa UI antes de persistencia y autorización backend.

## 24. Seguridad

- tenant proviene del envelope validado o contexto autenticado;
- RLS en toda relación tenant-owned;
- candidate queries siempre tenant-scoped, allowlisted y acotadas;
- no existe DSL controlada por usuario;
- referencias externas se tratan como datos no confiables;
- regex futuras requieren validación contra ReDoS o se prohíben inicialmente;
- límites antes de deserializar/consultar;
- logs sin entidades, títulos, explicaciones ni payload raw;
- DLQ protegida;
- reglas activas se validan y hashean;
- IA no participa en matching, score o autorización;
- findings simulados nunca producen incidentes presentados como reales.

## 25. Auditoría y observabilidad

Se auditan:

- activación/retiro futuro de reglas;
- evaluación manual/replay;
- evaluación humana mediante Claim Ledger;
- rechazo de tenant o permiso;
- cambios operativos de configuración.

La correlación automática de alto volumen usa registros de negocio, outbox e
inbox; no duplica un audit event por candidato.

Métricas mínimas:

- evaluaciones, matches y no-match por regla/version;
- candidatos y miembros;
- score y factores agregados sin cardinalidad sensible;
- latencia finding → match → incidente;
- duplicados/replays;
- límites excedidos;
- input `PARTIAL` por issue code;
- matches por combinación de fuentes;
- aceptación/rechazo humano;
- incidentes creados y ampliados;
- retries, DLQ y errores por código.

## 26. Pruebas obligatorias

### Dominio

- mismas entradas/versiones producen mismos factores, score y fingerprint;
- orden de entrada no cambia resultado;
- score no se presenta como riesgo/confianza;
- exact matching respeta kind y namespace;
- basis temporal y ventanas se aplican de forma reproducible;
- input parcial falla cerrado cuando no está allowlisted;
- límites de candidatos no producen match parcial.

### Persistencia

- match, miembros, incidente, claim y outbox son atómicos;
- redelivery/concurrencia no duplica efectos;
- revisiones históricas permanecen ancladas;
- RLS A/B y FK cross-tenant;
- downgrade no elimina historia;
- PostgreSQL no contiene payload raw.

### Eventos y worker

- `security.finding.normalized` activa evaluación tenant-scoped;
- duplicado ejecuta un efecto;
- correlation/causation se conservan;
- fallo transitorio recorre retry y permanente llega a DLQ;
- payload minimizado.

### Adaptadores y aceptación

- Wazuh y dos fixtures sintéticos producen el mismo contrato;
- dos fuentes distintas pueden participar en una regla que lo permita;
- el motor no importa módulos Wazuh;
- datos simulados permanecen visibles;
- replay histórico usa revisión y regla exactas.

### Incidentes y claims

- match crea o amplía según política y estado;
- nunca cierra/reabre automáticamente;
- claim es `DERIVED_FACT`, no `FACT`;
- evaluación humana no cambia tipo ni pesos;
- incidente cerrado recibe un incidente nuevo, no mutación silenciosa.

### API/UI

- paginación y límites;
- IDOR indistinguible de inexistente;
- permisos deny-by-default;
- traducciones español/inglés;
- accesibilidad y etiquetas no basadas solo en color.

## 27. Rollback

- consumidor de correlación desactivable sin detener ingesta;
- findings y eventos permanecen disponibles para replay autorizado;
- reglas nuevas se activan explícitamente;
- una versión defectuosa se retira, no se reescribe;
- incidentes y claims ya creados no se eliminan automáticamente;
- downgrade falla si existen matches/miembros/factores;
- RabbitMQ no elimina colas ni DLQ automáticamente;
- volver al escenario demo no presenta correlación real como validada.

## 28. Decisiones materiales pendientes

Antes del modelo físico se debe aprobar:

1. Correlation solicita comandos a Incident Management y no escribe su
   persistencia.
2. Matching inicial exclusivamente exacto, sin fuzzy/IA.
3. Semántica de ventana, bucket y grouping key.
4. Estados de incidente que admiten ampliación automática.
5. Regla determinista para severidad/prioridad inicial o su aplazamiento.
6. Catálogo inicial de factores, pesos y thresholds.
7. Límites de ventana, candidatos, miembros y evaluaciones concurrentes.
8. Tratamiento exacto de inputs `PARTIAL` y basis `INGESTED`.
9. Evolución/migración de `correlation_runs` sin doble fuente de verdad.
10. Dos fixtures sintéticos y muestra Wazuh de aceptación.
11. Permisos iniciales y matriz futura de analistas.
12. Si cada match se materializa siempre como `DERIVED_FACT`.
13. Persistencia limitada de no-match y métricas.
14. Estrategia transaccional única o saga explícita.
15. Retención futura; hasta aprobarla no habrá borrado automático.
16. Selectores de señal iniciales sin presentar categorías de proveedor como
    taxonomía neutral.
17. Tipos de entidad habilitados según perfiles de normalización disponibles.
18. Convivencia y migración del escenario demo legado hacia ingestión
    canónica.

### 28.1 Paquete recomendado para aprobación

Se recomienda resolver los puntos anteriores de la siguiente forma:

1. **Bounded contexts:** aprobar el puerto Correlation → Incident Management.
   Correlation no importa ni escribe persistencia de Incident Management.
2. **Matching:** exclusivamente exacto y determinista; sin fuzzy, embeddings,
   IA o equivalencias implícitas.
3. **Ventana:** primera versión con bucket UTC fijo, semiabierto y no
   solapado de diez minutos `[inicio, fin)`. El inicio se obtiene truncando
   `effective_at` al múltiplo UTC de diez minutos. La grouping key contiene
   regla/versión, bucket y entidad exacta. La limitación de borde se documenta;
   cambiarla exige nueva versión de regla.
4. **Incidentes ampliables:** `new`, `triaged`, `investigating`, `contained` y
   `reopened`. `resolved` y `closed` siempre producen otro incidente y nunca
   se reabren automáticamente.
5. **Severidad/prioridad inicial:** severidad máxima de los miembros. Mapeo
   determinista `critical → 1`, `high → 2`, `medium → 3`, `low → 4`,
   `informational → 5`. Una revisión humana posterior prevalece y Correlation
   no la recalcula.
6. **Factores v1:** entidad exacta `40` obligatorio; patrón de al menos dos
   selectores de señal distintos `25` obligatorio; misma ventana `20`
   obligatorio; diversidad de sistemas fuente `15` opcional. Threshold `85`.
   El score solo expresa factores satisfechos, no probabilidad, riesgo,
   confianza ni severidad.
7. **Límites v1:** hasta `500` candidatos, `32` miembros y `8` reglas
   aplicables por trigger. Una única evaluación concurrente por
   tenant/regla/versión/grouping key se reclama en PostgreSQL. Exceder un
   límite falla cerrado; la concurrencia global del worker continúa siendo
   configuración de despliegue.
8. **Inputs incompletos:** `PARTIAL` participa solo si sus `issue_codes` son
   subconjunto de la allowlist de la regla y todos los campos requeridos están
   presentes. Basis `INGESTED` queda rechazado en v1. Basis `DERIVED` requiere
   allowlist explícita de código de derivación.
9. **Persistencia legada:** evolucionar `correlation_runs` como raíz única del
   match y agregar relaciones normalizadas. Las filas demo existentes se
   marcan `LEGACY_SIMULATED_V0`, permanecen legibles y no adquieren miembros o
   factores inventados.
10. **Aceptación:** dos secuencias sintéticas canónicas y una secuencia Wazuh
    versionada, con IPs reservadas para documentación y tiempos UTC fijos.
    Deben atravesar normalización/persistencia y producir el mismo resultado
    lógico. Ningún fixture se presenta como telemetría real.
11. **Permisos:** `tenant-admin` recibe `correlation.read` y
    `correlation.evaluate`; la identidad técnica del worker recibe solo
    capacidades internas. `correlation.replay` no se asigna. El usuario demo,
    que es `tenant-admin`, puede ver y probar todo el slice.
12. **Claim:** cada match crea exactamente un `DERIVED_FACT` idempotente con
    evidencias `FINDING_REVISION`; no se crea un tipo nuevo de evidencia.
13. **No-match:** solo métricas agregadas acotadas. Fallos y reintentos usan
    inbox, retry, DLQ y observabilidad; no se crea una tabla ilimitada de
    evaluaciones negativas.
14. **Transacción:** una única unidad de trabajo PostgreSQL del monolito para
    match, miembros, factores, incidente, timeline, claim y outbox. Si el
    diseño físico demuestra que no es posible, se vuelve a revisión; no se
    introduce una saga silenciosamente.
15. **Retención:** ningún borrado automático en esta etapa. La política futura
    no podrá reescribir ni eliminar historia sin especificación separada.
16. **Selectores de señal:** la regla declara allowlists exactas y versionadas
    de `(source_system, rule_reference/category)`. Son datos de configuración,
    no imports de Wazuh ni una taxonomía universal. Una taxonomía semántica
    futura requerirá especificación propia.
17. **Entidades v1:** solo `IP_ADDRESS`, cuyo parser canónico ya normaliza el
    valor. `ASSET`, `ACCOUNT`, `DOMAIN`, `URL`, `HASH`, `PROCESS` y `FILE`
    permanecen deshabilitados hasta aprobar y probar sus perfiles de
    normalización por namespace.
18. **Demo:** el escenario actual continúa disponible como legado simulado.
    Un escenario canónico v2 entra por el servicio de ingestión y alimenta la
    correlación real; no se crean nuevas filas directas de demo en las
    relaciones de Etapa 4.

El paquete fue aprobado por instrucción humana el 2026-07-28 y queda registrado
en ADR 0012.

## 29. Criterios de aprobación

Para autorizar implementación se debe confirmar o enmendar:

1. límites de bounded context de sección 5;
2. semántica no autoritativa de sección 6;
3. inputs y selección de candidatos;
4. exact matching y política temporal;
5. reglas/factores/score versionados;
6. evaluación, match, miembros e idempotencia;
7. política de incidentes;
8. integración con Claim Ledger;
9. eventos y permisos candidatos;
10. persistencia lógica y migración del demo;
11. seguridad, pruebas y rollback;
12. decisiones y paquete recomendado de sección 28.

La aprobación humana fue registrada el 2026-07-28. La implementación debe
respetar el paquete completo y documentar cualquier enmienda técnica antes de
aplicarla.

## 30. Resultado de implementación

La Etapa 4 fue implementada y validada el 2026-07-28:

- el motor puro aplica matching exacto por IP, bucket UTC de diez minutos,
  factores, threshold y límites aprobados, sin imports de proveedor;
- las migraciones `0012_deterministic_correlation` y
  `0013_correlation_tenant_fks` evolucionan la raíz histórica, agregan reglas,
  miembros y factores, habilitan RLS y refuerzan relaciones con claves foráneas
  tenant-scoped;
- el worker consume `security.finding.normalized`, conserva idempotencia y
  confirma match, incidente, timeline, claim y outbox en la misma unidad de
  trabajo PostgreSQL;
- la API y la UI bilingüe permiten consultar explicación, miembros y factores;
- el escenario `credential-attack-v2` atraviesa la ingesta canónica y permanece
  marcado como simulado;
- la secuencia Wazuh versionada usa el mismo contrato normalizado y el mismo
  motor, sin presentar fixtures como telemetría real;
- se verificaron Ruff, mypy estricto, 71 pruebas backend, formato, ESLint,
  TypeScript, 6 pruebas frontend y build de producción;
- Docker Compose quedó saludable y PostgreSQL confirmó la revisión
  `0013_correlation_tenant_fks`.

No forman parte de este cierre el polling periódico Wazuh, la política de
retención ni replay administrativo: conservan sus puertas de aprobación
independientes.
