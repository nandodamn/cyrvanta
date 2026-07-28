# Fase 17 — Ledger de claims y clasificación epistemológica

**Estado:** DRAFT — pendiente de revisión y aprobación humana.
**Fecha:** 2026-07-28
**Implementación autorizada:** no.

## 1. Objetivo

Crear el contrato que permita distinguir de forma persistente, auditable y
visible:

- observaciones directas;
- resultados determinísticos;
- inferencias;
- hipótesis;
- recomendaciones;
- decisiones;
- acciones;
- resultados.

El ledger impedirá que una inferencia humana, de regla o IA se presente como un
hecho y permitirá reconstruir evidencia, procedencia, validación, contradicción
y supersesión sin guardar cadenas privadas de razonamiento.

Esta especificación no autoriza todavía migraciones, endpoints, eventos,
permisos ni cambios en el análisis actual.

## 2. Significado de “claim”

En este documento, un claim es una afirmación de conocimiento registrada por
Cyrvanta. No es un claim JWT de autenticación.

Un claim:

- pertenece exactamente a un tenant;
- tiene tipo epistemológico inmutable;
- conserva su texto y procedencia originales;
- referencia evidencia o claims previos cuando el tipo lo exige;
- puede recibir evaluaciones posteriores;
- nunca se edita para ocultar su historia;
- no concede autorización ni ejecuta acciones.

## 3. Estado actual

La base reutilizable incluye:

- findings Wazuh versionados con procedencia;
- alertas, incidentes, timeline y auditoría tenant-scoped;
- outbox/inbox y eventos con correlación/causalidad;
- análisis determinístico y resumen opcional mediante Ollama;
- permisos `analysis.request` y auditoría de solicitudes;
- respuesta compatible con resumen bilingüe, confianza, riesgo, técnicas y
  recomendaciones.

Brechas:

1. `AnalysisResponse` mezcla categorías epistemológicas.
2. `grounded=True` no demuestra evidencia por afirmación.
3. El análisis y sus recomendaciones no se persisten.
4. No hay validación, rechazo, retractación, contradicción o supersesión.
5. No se conserva regla, modelo, template de prompt ni schema por afirmación.
6. No existe permiso `analysis.read` implementado pese a estar documentado.
7. No existe separación entre contenido original y traducción.
8. Un resumen generado puede confundirse con una observación.

## 4. Alcance

### 4.1 Incluido

- taxonomía cerrada aprobada por D-003;
- invariantes por tipo de claim;
- procedencia humana, de fuente, regla, sistema o IA;
- enlaces a evidencia autorizada;
- relaciones entre claims;
- evaluaciones append-only;
- presentación bilingüe derivada;
- modelo lógico PostgreSQL, RLS, permisos, auditoría y eventos candidatos;
- adaptación compatible de `AnalysisResponse`;
- pruebas, observabilidad y rollback.

### 4.2 Fuera de alcance

- correlacionar automáticamente entidades o findings;
- calcular riesgo definitivo;
- importar MITRE ATT&CK;
- aprobar o ejecutar playbooks;
- definir políticas de doble control;
- memoria operacional;
- Decision Graph;
- reentrenar modelos;
- guardar chain-of-thought;
- crear claims a partir de cada evento histórico mediante backfill automático.

Los tipos `DECISION`, `ACTION` y `RESULT` forman parte de la taxonomía, pero sus
workflows de creación permanecen deshabilitados hasta las etapas de decisión y
ejecución.

## 5. Taxonomía vinculante si se aprueba

### 5.1 `FACT`

Observación registrada directamente y verificable en una fuente autorizada.

Ejemplo correcto:

```text
Wazuh registró la regla 60602 para el agente X a la hora T.
```

Ejemplo incorrecto:

```text
El usuario X realizó un ataque.
```

`FACT` afirma qué registró una fuente, no que la interpretación de seguridad sea
verdadera. Requiere evidencia directa. IA no puede originarlo.

### 5.2 `DERIVED_FACT`

Resultado reproducible de una transformación determinística sobre hechos o
datos autorizados. Requiere inputs, regla/código y versión.

Ejemplo:

```text
La IP normalizada pertenece al rango corporativo configurado.
```

### 5.3 `INFERENCE`

Conclusión no determinística o probabilística sustentada por evidencia.
Requiere confianza, explicación acotada y evidencia.

### 5.4 `HYPOTHESIS`

Proposición comprobable todavía no confirmada. Requiere evidencia inicial,
confianza, condiciones de validación y datos faltantes conocidos.

### 5.5 `RECOMMENDATION`

Propuesta de investigación o respuesta. Requiere fundamento, objetivo y
limitaciones. No representa decisión, aprobación ni autorización.

### 5.6 `DECISION`

Selección autorizada entre alternativas. IA no puede originarla ni validarla.
Su creación queda reservada hasta especificar política, actor y separación de
funciones.

### 5.7 `ACTION`

Registro de un intento de ejecución con parámetros exactos. No prueba éxito.
Reservado para la etapa de ejecución.

### 5.8 `RESULT`

Observación confirmada del resultado de una acción. No se deriva del estado
“enviado” de un adaptador. Reservado para callbacks/resultados persistentes.

## 6. Invariantes epistemológicos

1. El tipo de un claim es inmutable.
2. Validar una inferencia o hipótesis no la convierte en `FACT`.
3. Para afirmar un nuevo hecho se crea otro claim con evidencia directa.
4. Una traducción no altera tipo, evidencia ni validación.
5. Confianza no equivale a severidad, riesgo ni completitud de normalización.
6. Rechazo o contradicción no elimina el claim.
7. Una recomendación nunca autoriza una acción.
8. `ACTION` nunca implica `RESULT`.
9. IA no crea `FACT`, `DECISION`, `ACTION` ni `RESULT`.
10. IA no valida sus propios claims ni los de otro modelo.
11. Un claim cross-tenant es inválido aunque los IDs externos coincidan.
12. Fixtures y análisis demo conservan marca sintética visible.

## 7. Contrato lógico `ClaimV1`

| Campo | Tipo lógico | Regla |
|---|---|---|
| `claim_id` | UUID | Identidad inmutable. |
| `tenant_id` | UUID | Contexto seguro. |
| `incident_id` | UUID | Incidente propietario inicial. |
| `claim_type` | enum | Taxonomía de sección 5. |
| `statement` | texto acotado | Afirmación original, no localizada automáticamente. |
| `language_code` | código | `es`, `en` o `und`. |
| `confidence` | decimal/null | Obligatoria para tipos no determinísticos. |
| `origin_type` | enum | `SOURCE`, `HUMAN`, `RULE`, `SYSTEM` o `AI`. |
| `origin_reference` | procedencia | Actor/productor/regla/modelo según origen. |
| `explanation` | texto acotado/null | Justificación resumida y verificable. |
| `validation_criteria` | texto acotado/null | Obligatorio para hipótesis. |
| `missing_evidence` | colección acotada | Códigos/descripciones de brechas conocidas. |
| `is_simulated` | boolean | Nunca inferido solo desde la UI. |
| `created_at` | UTC | Tiempo del registro. |
| `correlation_id` | UUID | Correlación de extremo a extremo. |
| `causation_id` | UUID/null | Evento o solicitud causante. |
| `schema_version` | entero | Inicia en `1`. |

El claim es append-only. No posee un campo editable de “verdad actual”.

Los límites físicos de texto y colecciones se fijarán antes de implementar
usando análisis actuales, findings reales y pruebas de prompt injection.

## 8. Reglas por tipo

| Tipo | Evidencia | Confianza | Procedencia adicional |
|---|---|---|---|
| `FACT` | Al menos una fuente directa | Nula | Fuente y versión/snapshot |
| `DERIVED_FACT` | Inputs directos/claims | Nula | Regla/código y versión |
| `INFERENCE` | Al menos una referencia | Obligatoria | Método/modelo/regla |
| `HYPOTHESIS` | Al menos una referencia | Obligatoria | Criterio y faltantes |
| `RECOMMENDATION` | Al menos una referencia | Obligatoria | Objetivo y limitaciones |
| `DECISION` | Claims/evidencia/política | Nula | Reservado |
| `ACTION` | Decisión/autorización | Nula | Reservado |
| `RESULT` | Ejecución/evidencia directa | Nula | Reservado |

Una transacción rechaza el claim completo si no satisface su tipo.

## 9. Procedencia

`ClaimOriginV1` registra únicamente metadatos reproducibles.

### Humano

- `actor_user_id`;
- rol/permisos evaluados en el momento;
- canal (`api`, `ui`, importación autorizada).

### Fuente

- finding/revisión o evidencia directa;
- sistema e integración;
- versión de normalización.

### Regla o sistema

- código estable;
- versión;
- hash/configuración aprobada;
- componente productor.

### IA

- proveedor lógico;
- modelo configurado;
- versión de template de prompt;
- versión del schema de salida;
- parámetros no secretos relevantes;
- hash de inputs autorizados;
- modo `live`, `fallback` o `simulated`.

No se persisten:

- cadena privada de razonamiento;
- prompt con evidencia completa;
- telemetría raw;
- tokens, credenciales o respuestas sin validar;
- datos de otro tenant.

`explanation` contiene factores y referencias verificables, no razonamiento
interno paso a paso.

## 10. Evidencia

Tipos iniciales permitidos:

- `FINDING_REVISION`;
- `ALERT_REFERENCE`;
- `INCIDENT`;
- `INCIDENT_TIMELINE_ENTRY`;
- `AUDIT_EVENT`;
- `CLAIM`.

`ClaimEvidenceLinkV1` contiene claim, tipo/ID de evidencia, relación
(`SUPPORTS`, `REFUTES`, `CONTEXT`) y referencia de integridad cuando aplique.

Reglas:

- claim y evidencia pertenecen al mismo tenant;
- la evidencia existe y es autorizable al crear el enlace;
- el servicio nunca confía en tenant enviado en body;
- la lectura vuelve a evaluar autorización;
- una evidencia inaccesible puede mostrarse como referencia redactada, no
  filtrarse por contenido;
- OpenSearch se referencia; el documento raw no se copia a PostgreSQL;
- borrar/retener evidencia no reescribe silenciosamente el claim.

No se implementan enlaces polimórficos sin validación explícita en servicio y
pruebas RLS/IDOR.

## 11. Relaciones entre claims

Relaciones dirigidas:

- `SUPPORTS`;
- `CONTRADICTS`;
- `DERIVED_FROM`;
- `SUPERSEDES`;
- `RESPONDS_TO`.

Reglas:

- ambos claims son del mismo tenant e incidente;
- un claim no se enlaza consigo mismo;
- `DERIVED_FROM` y `SUPERSEDES` no admiten ciclos;
- `SUPERSEDES` no borra el claim anterior;
- `CONTRADICTS` puede coexistir con evaluaciones divergentes;
- las relaciones son append-only y tienen actor/productor, tiempo y
  correlación.

La resolución automática de contradicciones queda fuera de alcance.

## 12. Evaluaciones

`ClaimAssessmentV1` es append-only y registra:

- claim;
- outcome: `VALIDATED`, `REJECTED`, `INSUFFICIENT_EVIDENCE` o `RETRACTED`;
- evaluador humano o regla autorizada;
- explicación acotada;
- evidencia adicional;
- tiempo y correlation ID.

Reglas:

1. IA no evalúa claims.
2. El autor IA nunca puede ser evaluador.
3. Hipótesis e inferencias generadas por IA requieren evaluación humana para
   mostrarse como validadas.
4. Reglas allowlisted pueden validar únicamente `DERIVED_FACT` producido por
   una regla determinística distinta o mediante una verificación independiente.
5. El último outcome no destruye outcomes anteriores.
6. Evaluaciones concurrentes se conservan; una proyección explicita conflicto.
7. `RETRACTED` solo puede originarlo el autor humano o un permiso administrativo
   específico, con motivo.
8. Ningún outcome cambia `claim_type`.

Estado de presentación derivado:

- `PROPOSED`: sin evaluación concluyente;
- `VALIDATED`: existe validación vigente y no hay supersesión/retractación;
- `REJECTED`;
- `INSUFFICIENT_EVIDENCE`;
- `CONTESTED`: evaluaciones o contradicciones materiales incompatibles;
- `SUPERSEDED`;
- `RETRACTED`.

Este estado es una proyección, no la fuente de verdad.

## 13. Contenido bilingüe

El statement original se conserva con `language_code`.

Las traducciones se registran como `ClaimPresentationV1`:

- `claim_id`;
- locale `es` o `en`;
- texto traducido;
- origen humano, regla o IA;
- modelo/template cuando corresponda;
- timestamp y versión.

Una traducción:

- no es otro claim;
- no puede añadir hechos, certeza o recomendaciones;
- no sustituye el original;
- se marca como derivada;
- puede corregirse agregando una nueva versión.

La UI siempre traduce etiquetas, tipos, estados e incidencias mediante i18n,
aunque el contenido original solo exista en un idioma.

## 14. Modelo lógico PostgreSQL propuesto

Relaciones candidatas:

### `claims`

Registro inmutable del claim y su procedencia mínima.

### `claim_evidence_links`

Enlaces append-only a evidencia.

### `claim_relationships`

Relaciones append-only entre claims.

### `claim_assessments`

Evaluaciones append-only.

### `claim_presentations`

Versiones de traducción/presentación.

Todas:

- incluyen `tenant_id`;
- habilitan y fuerzan RLS;
- usan FK/constraints tenant-aware cuando sea posible;
- conceden `SELECT`/`INSERT`, no `UPDATE`/`DELETE`, al rol de aplicación;
- poseen índices tenant-first y consultas siempre paginadas;
- no almacenan payload raw ni chain-of-thought.

La migración candidata deberá resolver FK, longitudes, índices, constraints,
retención y downgrade no destructivo. Este DRAFT no aprueba nombres físicos
definitivos.

## 15. Transacciones

Crear un claim realiza atómicamente:

1. validar tenant, incidente, tipo y procedencia;
2. verificar evidencia;
3. insertar claim;
4. insertar enlaces/relaciones iniciales;
5. registrar auditoría cuando el origen sea humano o la operación sea
   relevante para seguridad;
6. registrar evento outbox.

Una evaluación o relación se registra de forma equivalente en una sola
transacción con su evento.

## 16. Eventos candidatos

```text
knowledge.claim.created
knowledge.claim.assessed
knowledge.claim.related
knowledge.claim.presentation.created
```

Payload mínimo:

- claim ID;
- incident ID;
- tipo;
- origin type;
- assessment/relationship code cuando corresponda;
- versión.

El envelope aporta tenant, correlación y causalidad. No se incluye statement,
explicación, traducción, evidencia raw, prompt ni datos sensibles.

Entrega at-least-once mediante la infraestructura de Fase 15. Los consumidores
son idempotentes.

## 17. Permisos candidatos

- `claim.read`;
- `claim.create`;
- `claim.assess`;
- `claim.translate`;
- `claim.retract`.

Reglas:

- tenant-admin recibe permisos iniciales solo mediante migración aprobada;
- analistas futuros requieren matriz explícita;
- `analysis.request` no implica automáticamente `claim.assess`;
- se debe implementar y asignar `analysis.read` o retirar la referencia de los
  documentos actuales;
- workers usan identidad técnica mínima y no permisos humanos simulados;
- la UI nunca sustituye autorización backend.

Los workflows de `DECISION`, `ACTION` y `RESULT` requerirán permisos separados
en sus etapas.

## 18. API candidata y compatibilidad

Recursos candidatos, siempre paginados y tenant-scoped:

- listar claims de un incidente;
- crear claim humano;
- evaluar claim;
- relacionar claims;
- listar evidencia autorizada;
- crear/corregir presentación.

No se fijan rutas ni DTO definitivos hasta aprobar esta especificación y el
catálogo físico.

Compatibilidad:

- el endpoint de análisis actual se conserva inicialmente;
- `AnalysisResponse` se convierte en proyección del ledger;
- resumen se presenta como contenido derivado, no `FACT`;
- técnicas propuestas son inferencias hasta validación MITRE posterior;
- recomendaciones se proyectan exclusivamente desde claims
  `RECOMMENDATION`;
- `grounded` solo es verdadero si cada claim proyectado satisface evidencia y
  reglas de su tipo;
- riesgo actual continúa como cálculo determinístico separado, no claim de
  verdad.

## 19. Integración inicial propuesta

Primer slice al implementar:

1. una solicitud de análisis genera claims determinísticos para inferencias y
   recomendaciones actuales;
2. si Ollama está disponible, su salida se valida contra schema estricto y crea
   claims `AI` propuestos;
3. fallback determinístico conserva origen y modo explícitos;
4. el análisis se reconstruye desde claims;
5. un analista autorizado puede validar/rechazar sin editar contenido;
6. el evento `security.finding.normalized` no crea automáticamente hechos hasta
   aprobar qué observaciones merecen materialización.

No se realiza backfill masivo de análisis históricos.

## 20. Seguridad

- texto, traducciones y explicaciones son datos no confiables;
- límites antes de persistir o enviar a IA;
- schema estricto con campos desconocidos rechazados;
- prompt injection tratada como contenido, nunca instrucción;
- evidencia minimizada y redactada antes del proveedor;
- Ollama configurable y on-premise; ningún egress implícito;
- allowlist de proveedores/modelos/templates;
- RLS y validación tenant en cada enlace;
- errores RFC 7807 sin filtrar existencia cross-tenant;
- logs sin statements, prompts completos ni evidencia raw;
- exportación futura requiere permiso y redacción específica.

## 21. Auditoría

Se auditan:

- creación humana;
- evaluación, retractación y traducción humana;
- relaciones `CONTRADICTS`/`SUPERSEDES`;
- rechazos de tenant, permisos o evidencia;
- cambios administrativos de reglas/templates.

La creación automática de alto volumen usa registros de negocio, eventos y
logs estructurados; no duplica necesariamente un audit event por fila.

Audit no sustituye el ledger.

## 22. Observabilidad

Métricas mínimas:

- claims por tipo, origen y estado derivado;
- claims sin evidencia o rechazados por invariantes;
- latencia solicitud → claim → evaluación;
- validaciones/rechazos/contradicciones;
- tasa de claims IA aceptados, rechazados o insuficientes;
- fallos de schema, provider, RLS e idempotencia;
- presentaciones ausentes por locale;
- backlog de análisis por tenant sin cardinalidad sensible.

Logs estructurados:

- claim/incident/tenant autorizados;
- tipo, origen, schema y versiones;
- correlation/event IDs;
- outcome y código de error;
- nunca statement, traducción, prompt o evidencia completa.

## 23. Pruebas obligatorias

### Dominio

- taxonomía cerrada;
- tipo inmutable;
- reglas de evidencia/confianza por tipo;
- IA rechazada para tipos prohibidos;
- validación no cambia tipo;
- traducción no cambia semántica;
- ciclos y self-links rechazados.

### Persistencia

- append-only efectivo por privilegios;
- claim, enlaces, auditoría y outbox atómicos;
- evaluaciones concurrentes preservadas;
- RLS real entre tenants;
- FK/enlaces cross-tenant rechazados;
- PostgreSQL sin raw payload ni chain-of-thought;
- downgrade bloqueado con filas.

### API y autorización

- paginación y límites;
- `claim.read/create/assess/translate/retract`;
- IDOR indistinguible de inexistente;
- usuario sin permiso falla cerrado;
- evidencia redactada según permiso;
- errores RFC 7807.

### IA y seguridad

- schema desconocido/incompleto rechazado;
- prompt injection no altera instrucciones;
- modelo no crea tipos prohibidos;
- output sin evidencia no queda grounded;
- indisponibilidad Ollama usa fallback explícito;
- logs no contienen prompts/evidencia.

### Compatibilidad

- respuesta de análisis mantiene contrato público aprobado;
- recomendaciones provienen de claims correctos;
- frontend español/inglés distingue tipo, estado y origen;
- lector de pantalla dispone de etiquetas textuales;
- incidentes y findings actuales no cambian.

## 24. Rollback

- creación de ledger detrás de configuración segura;
- endpoint actual puede volver temporalmente a proyección determinística;
- claims ya creados nunca se eliminan automáticamente;
- downgrade falla si existen filas;
- eventos/colas no se eliminan con rollback;
- salida IA puede desactivarse sin perder claims previos;
- una versión defectuosa de regla/template se retira creando versión nueva, no
  reescribiendo historia.

## 25. Información pendiente antes de implementar

1. límites físicos de statement, explicación, criterios y colecciones;
2. política de retención de claims, evaluaciones y traducciones;
3. qué roles además de tenant-admin podrán crear/evaluar/retractar;
4. si el creador humano puede validar su propio claim;
5. catálogo inicial de códigos de evidencia faltante;
6. schema estructurado exacto para salida Ollama;
7. versiones/tags reales permitidos para Gemma 4;
8. contenido mínimo del hash de inputs IA;
9. comportamiento cuando evidencia retenida ya no esté disponible;
10. umbral o política para mostrar claims IA no validados;
11. estrategia de migración de `AnalysisResponse.grounded`;
12. volúmenes esperados por incidente y límites de consulta.

## 26. Criterios de aprobación

Para autorizar implementación se debe confirmar:

1. semántica de los ocho tipos;
2. IA prohibida para `FACT`, `DECISION`, `ACTION` y `RESULT`;
3. claim y evaluaciones append-only;
4. validación nunca cambia tipo;
5. relaciones y estados derivados;
6. modelo de evidencia tenant-safe;
7. procedencia sin chain-of-thought;
8. traducciones como presentación derivada;
9. permisos candidatos;
10. eventos candidatos;
11. compatibilidad con `AnalysisResponse`;
12. `DECISION`, `ACTION` y `RESULT` deshabilitados inicialmente;
13. resolución de los pendientes materiales aplicables de sección 25.

Hasta registrar aprobación, no se crean migraciones, modelos, endpoints,
permisos, eventos ni cambios de worker para esta etapa.
